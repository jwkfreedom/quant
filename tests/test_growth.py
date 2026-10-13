"""单季增长计算单测（构造数据，不依赖磁盘）。"""

from __future__ import annotations

import pandas as pd
import pytest

from quant.foundation.growth import compute_growth, growth_score, rm_broken_stocks


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame({
        "symbol": ["600000", "600000"],
        "season": [20220331, 20220630],
        "total_revenue": [100.0, 250.0],
        "total_revenue_yoy": [0.0, 25.0],
        "net_profit": [20.0, 60.0],
        "net_profit_yoy": [0.0, 50.0],
    })


def test_compute_growth_income():
    result = compute_growth(_sample_df())
    first = result[result["season"] == 20220331].iloc[0]
    second = result[result["season"] == 20220630].iloc[0]

    # 一季度：单季值即累计值，同比即报表同比
    assert first["pre_year_income"] == pytest.approx(100.0)
    assert first["season_income"] == pytest.approx(100.0)
    assert first["season_income_growth"] == pytest.approx(0.0)

    # 二季度：单季 = 250 - 100 = 150；去年同季 = 200 - 100 = 100；同比 +50%
    assert second["pre_year_income"] == pytest.approx(200.0)
    assert second["season_income"] == pytest.approx(150.0)
    assert second["season_income_growth"] == pytest.approx(50.0)


def test_compute_growth_profit():
    result = compute_growth(_sample_df())
    second = result[result["season"] == 20220630].iloc[0]
    # 单季利润 = 60 - 20 = 40；去年同季 = 40 - 20 = 20；同比 +100%
    assert second["pre_year_profit"] == pytest.approx(40.0)
    assert second["season_profit"] == pytest.approx(40.0)
    assert second["season_profit_growth"] == pytest.approx(100.0)


def test_compute_growth_handles_missing_previous_season():
    df = _sample_df().iloc[[1]].copy()  # 只有二季度，缺上一季
    result = compute_growth(df)
    assert len(result) == 1
    assert pd.isna(result.iloc[0]["season_income"])


def test_growth_score_requires_q1_start():
    df = _sample_df().iloc[[1]].copy()
    assert growth_score(df) is None


def test_growth_score_on_valid_input():
    result = growth_score(_sample_df())
    assert result is not None
    for column in ("pre_year_income", "season_income", "season_income_growth",
                   "pre_year_profit", "season_profit", "season_profit_growth"):
        assert column in result.columns


def test_rm_broken_stocks_keeps_complete_symbols():
    df = pd.DataFrame({
        "symbol": ["A", "A", "B"],
        "season": [20220331, 20220630, 20220331],
    })
    result = rm_broken_stocks(df)
    assert set(result["symbol"]) == {"A"}
