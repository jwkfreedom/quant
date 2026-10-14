"""策略注册表里的策略能否跑通（需要数据库里有对应数据）。

数据库里没有标的时自动跳过，因此在 CI / 新环境上不会失败。
"""

from __future__ import annotations

import pytest

from quant.data import store
from quant.price.loader import get_etf_price, get_stock_price
from quant.strategy import run_backtest


def _has_etf() -> bool:
    try:
        return not get_etf_price("512480").empty
    except Exception:
        return False


def _has_stock(code: str) -> bool:
    try:
        return not get_stock_price(code).empty
    except Exception:
        return False


@pytest.mark.skipif(not _has_etf(), reason="数据库中没有 512480 的 ETF 数据")
def test_ma_obv_runs():
    result = run_backtest("ma_obv", symbol="512480")
    assert result.strategy == "ma_obv"
    assert result.bars > 0
    assert result.final_value > 0


@pytest.mark.skipif(not _has_stock("000001"), reason="数据库中没有 000001 的日线")
def test_volume_breakout_runs():
    result = run_backtest("volume_breakout", symbol="000001", fromdate=None)
    assert result.strategy == "volume_breakout"
    assert result.final_value > 0
