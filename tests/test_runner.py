"""回测指标计算单测（不需要行情数据）。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quant.strategy.runner import TRADING_DAYS, benchmark_curve, compute_metrics


def test_compute_metrics_annual_return():
    # 244 个交易日翻倍 -> 年化 100%
    equity = pd.Series(np.linspace(100000, 200000, TRADING_DAYS))
    result = compute_metrics(equity, 100000.0)
    assert result["annual_return"] == pytest.approx(100.0, rel=1e-6)


def test_compute_metrics_sharpe_positive_for_steady_growth():
    equity = pd.Series(np.linspace(100000, 120000, 244))
    result = compute_metrics(equity, 100000.0)
    assert result["sharpe"] > 0


def test_compute_metrics_handles_degenerate_input():
    assert compute_metrics(pd.Series([100000.0]), 100000.0) == {"annual_return": 0.0, "sharpe": 0.0}
    assert compute_metrics(pd.Series(dtype=float), 100000.0) == {"annual_return": 0.0, "sharpe": 0.0}
    flat = pd.Series([100000.0] * 50)
    assert compute_metrics(flat, 100000.0)["sharpe"] == 0.0


def test_benchmark_curve_normalises_to_initial_cash():
    df = pd.DataFrame({"date": ["2023-01-03", "2023-01-04"], "close": [10.0, 20.0]})
    curve = benchmark_curve(df, 100000.0)
    assert curve["value"].tolist() == [100000.0, 200000.0]


def test_benchmark_curve_handles_empty():
    assert benchmark_curve(pd.DataFrame(), 100000.0).empty
    assert benchmark_curve(pd.DataFrame({"date": [], "close": []}), 100000.0).empty
