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
from quant.strategy.ma_obv import RULES as MA_OBV_RULES
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
from quant.strategy.volume_breakout import RULES as VOLUME_BREAKOUT_RULES
from quant.strategy.volume_breakout import run_backtest as _run_volume_breakout

logger = logging.getLogger(__name__)


@dataclass
class StrategyInfo:
    """策略元信息（UI 用它生成参数表单与策略说明）。"""

    name: str
    runner: Callable
    default_symbol: str
    description: str
    params: list[dict] = field(default_factory=list)
    category: str = ""
    #: 算法步骤说明（逐条），界面上原样展示
    rules: list[str] = field(default_factory=list)

    def explain(self) -> str:
        """生成「策略说明」文本：说明 + 参数表 + 算法步骤。"""
        lines = [f"【{self.name}】{self.description}", ""]

        lines.append("【参数】")
        if self.params:
            for param in self.params:
                label = param.get("label", param["name"])
                default = param.get("default")
                bounds = ""
                if param.get("min") is not None or param.get("max") is not None:
                    bounds = f"　范围 {param.get('min', '')}~{param.get('max', '')}"
                elif param.get("type") == "float":
                    bounds = "　取值 0~1 之间的小数"
                help_text = f"　— {param['help']}" if param.get("help") else ""
                lines.append(f"  {param['name']:<14}{label}（默认 {default}{bounds}）{help_text}")
        else:
            lines.append("  该策略没有可调参数")

        lines.append("")
        lines.append("【算法】")
        counter = 0
        for rule in (self.rules or ["（尚未填写算法说明）"]):
            if rule.startswith("    "):
                # 缩进的行作为上一条的子项，不参与编号
                lines.append(f"       {rule.strip()}")
            else:
                counter += 1
                lines.append(f"  {counter}. {rule}")

        lines.append("")
        lines.append("【默认标的】" + (self.default_symbol or "—"))
        if self.category:
            lines.append("【分类】" + self.category)
        return "\n".join(lines)


#: 策略注册表：名字 -> StrategyInfo
REGISTRY: dict[str, StrategyInfo] = {
    "ma_obv": StrategyInfo(
        name="ma_obv",
        runner=_run_ma_obv,
        default_symbol="512480",
        description="均线 + OBV：价格上穿均线且 OBV 为正买入，反向卖出（ETF）",
        params=MA_OBV_PARAMS,
        category="趋势",
        rules=MA_OBV_RULES,
    ),
    "volume_breakout": StrategyInfo(
        name="volume_breakout",
        runner=_run_volume_breakout,
        default_symbol="000001",
        description="缩量买入：成交量低于均量一定比例时买入，触及止盈/止损卖出（个股）",
        params=VOLUME_BREAKOUT_PARAMS,
        category="量价",
        rules=VOLUME_BREAKOUT_RULES,
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
