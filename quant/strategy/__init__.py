"""backtrader 策略集合与统一回测入口。

```python
from quant.strategy import list_strategies, run_backtest

for info in list_strategies():
    print(info.name, info.default_symbol, info.description, info.params)

result = run_backtest("ma_obv", symbol="512480", cash=100000, ma_period=10)
print(result.report())
print(result.equity_curve.tail())      # 净值曲线
print(result.trade_list)               # 成交明细
```

命令行等价形式::

    quant backtest --list
    quant backtest --strategy ma_obv --symbol 512480
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

from quant.strategy.ma_obv import MAOBVStrategy, MyOBV
from quant.strategy.ma_obv import PARAMS_SPEC as MA_OBV_PARAMS
from quant.strategy.ma_obv import run_backtest as _run_ma_obv
from quant.strategy.runner import (
    BacktestResult,
    EquityCurveAnalyzer,
    benchmark_curve,
    build_cerebro,
    compute_metrics,
    extract_result,
)
from quant.strategy.volume_breakout import VolumeBreakoutStrategy
from quant.strategy.volume_breakout import PARAMS_SPEC as VOLUME_BREAKOUT_PARAMS
from quant.strategy.volume_breakout import run_backtest as _run_volume_breakout

logger = logging.getLogger(__name__)


@dataclass
class StrategyInfo:
    """策略元信息（UI 用它生成参数表单）。"""

    name: str
    runner: Callable
    default_symbol: str
    description: str
    params: list[dict] = field(default_factory=list)
    category: str = ""


#: 策略注册表：名字 -> StrategyInfo
REGISTRY: dict[str, StrategyInfo] = {
    "ma_obv": StrategyInfo(
        name="ma_obv",
        runner=_run_ma_obv,
        default_symbol="512480",
        description="均线 + OBV：价格上穿均线且 OBV 为正买入，反向卖出（ETF）",
        params=MA_OBV_PARAMS,
        category="趋势",
    ),
    "volume_breakout": StrategyInfo(
        name="volume_breakout",
        runner=_run_volume_breakout,
        default_symbol="000001",
        description="缩量买入：成交量低于均量一定比例时买入，触及止盈/止损卖出（个股）",
        params=VOLUME_BREAKOUT_PARAMS,
        category="量价",
    ),
}


def list_strategies() -> list[StrategyInfo]:
    """返回全部策略（按名字排序）。"""
    return [REGISTRY[name] for name in sorted(REGISTRY)]


def get_strategy(name: str) -> StrategyInfo:
    """按名字取策略信息，未注册时抛 KeyError。"""
    if name not in REGISTRY:
        raise KeyError(f"未注册的策略: {name}；可用: {sorted(REGISTRY)}")
    return REGISTRY[name]


def register_strategy(
    name: str,
    runner_fn: Callable,
    default_symbol: str = "",
    description: str = "",
    params: list[dict] | None = None,
    category: str = "",
) -> None:
    """注册自定义策略（runner_fn 需返回 BacktestResult）。"""
    REGISTRY[name] = StrategyInfo(
        name=name, runner=runner_fn, default_symbol=default_symbol,
        description=description, params=list(params or []), category=category,
    )


def default_params(name: str) -> dict:
    """取某策略的默认参数。"""
    return {p["name"]: p.get("default") for p in get_strategy(name).params}


def run_backtest(name: str, symbol: str | None = None, **kwargs) -> BacktestResult:
    """统一回测入口：`run_backtest("ma_obv", symbol="512480", cash=100000, ma_period=10)`。"""
    info = get_strategy(name)
    symbol = symbol or info.default_symbol
    logger.info("回测 %s @ %s", name, symbol)
    return info.runner(symbol, **kwargs)


__all__ = [
    "MyOBV",
    "MAOBVStrategy",
    "VolumeBreakoutStrategy",
    "BacktestResult",
    "StrategyInfo",
    "EquityCurveAnalyzer",
    "build_cerebro",
    "extract_result",
    "compute_metrics",
    "benchmark_curve",
    "REGISTRY",
    "list_strategies",
    "get_strategy",
    "register_strategy",
    "default_params",
    "run_backtest",
]
