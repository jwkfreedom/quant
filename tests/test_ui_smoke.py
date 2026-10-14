"""UI 冒烟测试：模块可导入、图表能构建。

不创建窗口（无显示环境下会失败），只验证不依赖 GUI 的部分。
"""

from __future__ import annotations

import pandas as pd
import pytest

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")

from quant.ui import charts, viewmodels  # noqa: E402


def test_viewmodels_importable():
    assert hasattr(viewmodels, "data_status")
    assert hasattr(viewmodels, "query_table")
    assert hasattr(viewmodels, "run_screen")


def test_charts_handle_empty_input():
    empty = pd.DataFrame()
    for name, figure in (
        ("kline", charts.kline_figure(empty)),
        ("band", charts.valuation_band_figure(empty)),
        ("financial", charts.financial_figure(empty)),
        ("history", charts.valuation_history_figure(empty)),
        ("cap", charts.market_cap_figure(empty)),
        ("pe", charts.pe_distribution_figure(empty)),
    ):
        assert figure is not None, name


def test_kline_figure_from_sample(sample_db):
    from quant.data import store

    with store.open_db(sample_db) as conn:
        price = store.read_price(conn, "000001")
    figure = charts.kline_figure(price, title="测试")
    assert len(figure.axes) == 2       # K线 + 成交量
    assert "测试" in figure.axes[0].get_title()


def test_valuation_band_figure_needs_positive_pe():
    df = pd.DataFrame({
        "date": ["2023-01-03", "2023-01-04"],
        "close": [10.0, 11.0],
        "pe": [-1.0, -2.0],
        "eps_ttm": [1.0, 1.0],
    })
    figure = charts.valuation_band_figure(df)
    assert figure is not None


def test_equity_figure_without_data():
    class FakeResult:
        equity_curve = None
        benchmark_curve = None
        initial_cash = 100000.0
        strategy = "s"
        symbol = "000001"

    assert charts.equity_figure(FakeResult()) is not None
