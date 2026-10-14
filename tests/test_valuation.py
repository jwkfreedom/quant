"""估值历史分位单测（合成数据）。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quant.data import store
from quant.foundation.valuation import (
    VALUATION_METRICS,
    compute_percentiles,
    compute_symbol_valuation,
    percentile_rank,
)

from conftest import DATES, SYMBOLS


@pytest.fixture
def conn(sample_db):
    with store.open_db(sample_db) as connection:
        yield connection


def test_percentile_rank_basic():
    values = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    assert percentile_rank(values, 3.0) == pytest.approx(40.0)   # 有 2 个比 3 小
    assert percentile_rank(values, 1.0) == pytest.approx(0.0)
    assert percentile_rank(values, 6.0) == pytest.approx(100.0)


def test_percentile_rank_ignores_non_positive():
    values = pd.Series([-5.0, -1.0, 1.0, 2.0, 3.0])
    # 负 PE 与 0 被剔除，只剩 1/2/3 三个有效样本
    assert percentile_rank(values, 2.0) == pytest.approx(1 / 3 * 100)


def test_percentile_rank_invalid_current():
    values = pd.Series([1.0, 2.0])
    assert np.isnan(percentile_rank(values, float("nan")))
    assert np.isnan(percentile_rank(values, -3.0))
    assert np.isnan(percentile_rank(pd.Series([], dtype=float), 1.0))


def test_compute_symbol_valuation_columns(conn):
    series = compute_symbol_valuation(SYMBOLS[0], conn)
    assert not series.empty
    for column in ("date", "close", "eps_ttm", "bvps_ttm", "revenue_ttm", "pe", "pb", "ps", "shares"):
        assert column in series.columns


def test_compute_symbol_valuation_values(conn):
    series = compute_symbol_valuation(SYMBOLS[0], conn).set_index("date")
    last = series.iloc[-1]
    # 合成数据：close 单调上升，eps_ttm 固定为 1.0（index 0）
    assert last["pe"] == pytest.approx(last["close"] / last["eps_ttm"])
    assert last["pb"] == pytest.approx(last["close"] / last["bvps_ttm"])
    assert last["shares"] == pytest.approx(last["net_profit_ttm"] / last["eps_ttm"])


def test_compute_symbol_valuation_unknown_symbol(conn):
    assert compute_symbol_valuation("999999", conn).empty


def test_compute_percentiles_windows(conn):
    series = compute_symbol_valuation(SYMBOLS[0], conn)
    rows = compute_percentiles(series, windows=(3, 5, 10, 0))
    assert len(rows) == 4
    for row in rows:
        assert row["symbol"] == SYMBOLS[0]
        assert row["sample_days"] > 0
        for metric in VALUATION_METRICS:
            assert f"current_{metric}" in row
            assert f"{metric}_pct" in row


def test_compute_percentiles_uses_only_window(conn):
    series = compute_symbol_valuation(SYMBOLS[0], conn)
    all_rows = {row["window_years"]: row for row in compute_percentiles(series, windows=(3, 0))}
    # 全历史窗口的样本数不可能少于 3 年窗口
    assert all_rows[0]["sample_days"] >= all_rows[3]["sample_days"]
    assert all_rows[3]["window_start"] >= all_rows[0]["window_start"]


def test_compute_percentiles_empty():
    assert compute_percentiles(pd.DataFrame(), windows=(10,)) == []
