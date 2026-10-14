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


def test_price_columns_supports_both_naming_schemes():
    import pandas as pd

    query_style = pd.DataFrame(columns=["open", "high", "low", "close",
                                         "open_qfq", "high_qfq", "low_qfq", "close_qfq"])
    assert charts.price_columns(query_style, "qfq")["close"] == "close_qfq"
    assert charts.price_columns(query_style, "raw")["close"] == "close"

    loader_style = pd.DataFrame(columns=["open", "high", "low", "close",
                                          "open_org", "high_org", "low_org", "close_org"])
    assert charts.price_columns(loader_style, "qfq")["close"] == "close"
    assert charts.price_columns(loader_style, "raw")["close"] == "close_org"


def test_resample_ohlc():
    import numpy as np
    import pandas as pd

    dates = pd.bdate_range("2023-01-02", periods=20).strftime("%Y-%m-%d")
    df = pd.DataFrame({
        "date": dates,
        "open": np.arange(20, dtype=float),
        "high": np.arange(20, dtype=float) + 1,
        "low": np.arange(20, dtype=float) - 1,
        "close": np.arange(20, dtype=float) + 0.5,
        "close_qfq": np.arange(20, dtype=float),
        "volume": np.ones(20) * 100,
    })

    weekly = charts.resample_ohlc(df, "W")
    assert 4 <= len(weekly) <= 5          # 20 个交易日约 4 周
    assert weekly["volume"].sum() == 2000 # 成交量应当被加总
    assert weekly["high"].max() == df["high"].max()

    monthly = charts.resample_ohlc(df, "M")
    assert len(monthly) == 1

    assert charts.resample_ohlc(df, "D") is df


def test_kline_with_indicators(sample_db):
    from quant.data import store

    with store.open_db(sample_db) as conn:
        price = store.read_price(conn, "000001")

    plain = charts.kline_figure(price, adjust="qfq")
    assert len(plain.axes) == 2                      # K线 + 成交量

    full = charts.kline_figure(price, adjust="raw", macd=True, rsi=True)
    assert len(full.axes) == 4                       # + MACD + RSI

    weekly = charts.resample_ohlc(price, "W")
    assert charts.kline_figure(weekly, adjust="qfq") is not None


def test_macd_and_rsi_series(sample_db):
    from quant.data import store

    with store.open_db(sample_db) as conn:
        price = store.read_price(conn, "000001")

    dif, dea, hist = charts.macd_series(price["close_qfq"])
    assert len(dif) == len(price)
    assert (hist == (dif - dea) * 2).all()

    rsi = charts.rsi_series(price["close_qfq"])
    valid = rsi.dropna()
    assert not valid.empty
    assert valid.between(0, 100).all()


def test_sweep_figure():
    import pandas as pd

    table = pd.DataFrame({
        "ma_period": [5, 10, 20],
        "return_pct": [1.0, 3.0, 2.0],
        "max_drawdown_pct": [30.0, 20.0, 25.0],
        "sharpe": [0.1, 0.4, 0.2],
    })
    figure = charts.sweep_figure(table, x_column="ma_period")
    assert len(figure.axes) == 3
    assert charts.sweep_figure(pd.DataFrame(), x_column="x") is not None


def test_equity_figure_without_data():
    class FakeResult:
        equity_curve = None
        benchmark_curve = None
        initial_cash = 100000.0
        strategy = "s"
        symbol = "000001"

    assert charts.equity_figure(FakeResult()) is not None
