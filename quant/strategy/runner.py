"""回测公共设施：统一的 cerebro 装配、结果对象与指标提取。

所有策略都通过 `run_backtest(...) -> BacktestResult` 暴露，
命令行 `quant backtest` 与 notebook 走同一条路径。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import backtrader as bt
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

#: A 股一年约 244 个交易日（用于年化与夏普）
TRADING_DAYS = 244


class EquityCurveAnalyzer(bt.Analyzer):
    """逐日记录组合市值，用于画净值曲线与计算年化/夏普。"""

    def start(self):
        self.dates: list[str] = []
        self.values: list[float] = []

    def next(self):
        self.dates.append(self.strategy.datetime.date(0).isoformat())
        self.values.append(float(self.strategy.broker.getvalue()))

    def get_analysis(self):
        return {"dates": self.dates, "values": self.values}


@dataclass
class BacktestResult:
    """回测结果。"""

    strategy: str
    symbol: str
    initial_cash: float
    final_value: float
    start: str | None = None
    end: str | None = None
    bars: int = 0
    trades: int = 0
    win_trades: int = 0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    annual_return: float = 0.0
    sharpe: float = 0.0
    params: dict = field(default_factory=dict)
    equity_curve: pd.DataFrame | None = None
    benchmark_curve: pd.DataFrame | None = None
    trade_list: list[dict] = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    @property
    def return_pct(self) -> float:
        """总收益率（%）。"""
        if not self.initial_cash:
            return 0.0
        return (self.final_value / self.initial_cash - 1) * 100

    @property
    def win_rate(self) -> float:
        """胜率（%）。"""
        return (self.win_trades / self.trades * 100) if self.trades else 0.0

    def report(self) -> str:
        lines = [
            f"策略      : {self.strategy}",
            f"标的      : {self.symbol}",
            f"区间      : {self.start} ~ {self.end}（{self.bars} 根 K 线）",
        ]
        if self.params:
            lines.append(f"参数      : {self.params}")
        lines += [
            "-" * 46,
            f"初始资金  : {self.initial_cash:>14,.2f}",
            f"最终市值  : {self.final_value:>14,.2f}",
            f"总收益率  : {self.return_pct:>14.2f}%",
            f"年化收益  : {self.annual_return:>14.2f}%",
            f"夏普比率  : {self.sharpe:>14.2f}",
            f"最大回撤  : {self.max_drawdown:>14,.2f} ({self.max_drawdown_pct:.2f}%)",
            f"交易次数  : {self.trades:>14d}",
            f"胜率      : {self.win_rate:>14.2f}%",
        ]
        return "\n".join(lines)

    def metrics(self) -> dict:
        """供 UI / 表格展示的一行摘要。"""
        return {
            "strategy": self.strategy,
            "symbol": self.symbol,
            "return_pct": round(self.return_pct, 2),
            "annual_return": round(self.annual_return, 2),
            "sharpe": round(self.sharpe, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "trades": self.trades,
            "win_rate": round(self.win_rate, 2),
        }


def build_cerebro(
    cash: float = 100000.0,
    commission: float = 0.001,
    sizer_percent: float = 95.0,
) -> bt.Cerebro:
    """创建一个配置好资金 / 手续费 / 仓位 / 分析器的 cerebro。

    .. note::
       backtrader 默认 sizer 是「每次 1 股」，会让回测结果几乎恒等于初始资金。
       这里统一使用 `PercentSizer`（默认每次最多用 95% 资金建仓）。
    """
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(cash)
    cerebro.broker.setcommission(commission=commission)
    if sizer_percent:
        cerebro.addsizer(bt.sizers.PercentSizer, percents=sizer_percent)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
    cerebro.addanalyzer(EquityCurveAnalyzer, _name="equity")
    return cerebro


def compute_metrics(equity: pd.Series, initial_cash: float) -> dict:
    """由净值序列计算年化收益与夏普比率。"""
    result = {"annual_return": 0.0, "sharpe": 0.0}
    if equity is None or len(equity) < 2 or initial_cash <= 0:
        return result

    total = float(equity.iloc[-1]) / initial_cash
    days = len(equity)
    if days > 0 and total > 0:
        result["annual_return"] = (total ** (TRADING_DAYS / days) - 1) * 100

    returns = equity.pct_change().dropna()
    if len(returns) > 1 and returns.std() > 0:
        result["sharpe"] = float(returns.mean() / returns.std() * np.sqrt(TRADING_DAYS))
    return result


def benchmark_curve(df: pd.DataFrame, initial_cash: float, date_column: str = "date",
                    price_column: str = "close") -> pd.DataFrame:
    """买入持有基准净值曲线。"""
    if df is None or df.empty or price_column not in df.columns:
        return pd.DataFrame(columns=["date", "value"])
    data = df.loc[:, [date_column, price_column]].dropna().copy()
    if data.empty:
        return pd.DataFrame(columns=["date", "value"])
    first = float(data[price_column].iloc[0])
    if first <= 0:
        return pd.DataFrame(columns=["date", "value"])
    data["value"] = data[price_column] / first * initial_cash
    return data.rename(columns={date_column: "date"}).loc[:, ["date", "value"]].reset_index(drop=True)


def extract_result(
    cerebro: bt.Cerebro,
    strategy_name: str,
    symbol: str,
    initial_cash: float,
    *,
    bars: int = 0,
    start: str | None = None,
    end: str | None = None,
    params: dict | None = None,
    benchmark: pd.DataFrame | None = None,
) -> BacktestResult:
    """跑完回测后，从 cerebro / 分析器里提取统一结果。"""
    strategies = cerebro.run()
    strategy = strategies[0] if strategies else None

    result = BacktestResult(
        strategy=strategy_name,
        symbol=symbol,
        initial_cash=initial_cash,
        final_value=cerebro.broker.getvalue(),
        bars=bars,
        start=start,
        end=end,
        params=dict(params or {}),
    )

    if strategy is not None:
        equity = getattr(strategy.analyzers, "equity", None)
        if equity is not None:
            try:
                analysis = equity.get_analysis()
                curve = pd.DataFrame({"date": analysis["dates"], "value": analysis["values"]})
                if not curve.empty:
                    result.equity_curve = curve
                    metrics = compute_metrics(curve.set_index("date")["value"], initial_cash)
                    result.annual_return = metrics["annual_return"]
                    result.sharpe = metrics["sharpe"]
            except Exception:  # pragma: no cover
                logger.debug("未能提取净值曲线", exc_info=True)

        trade_analyzer = getattr(strategy.analyzers, "trades", None)
        if trade_analyzer is not None:
            try:
                analysis = trade_analyzer.get_analysis()
                result.trades = int(analysis.get("total", {}).get("closed", 0))
                result.win_trades = int(analysis.get("won", {}).get("total", 0))
            except Exception:  # pragma: no cover
                pass

    if strategy is not None:
        drawdown = getattr(strategy.analyzers, "drawdown", None)
        if drawdown is not None:
            try:
                # DrawDown 分析器的字段是 moneydown（金额）与 drawdown（百分比）
                worst = drawdown.get_analysis()["max"]
                result.max_drawdown = float(worst["moneydown"])
                result.max_drawdown_pct = float(worst["drawdown"])
            except Exception:  # pragma: no cover - 无交易时分析器可能没有值
                logger.debug("未能从 DrawDown 分析器取到回撤", exc_info=True)

    result.trade_list = list(getattr(strategy, "trade_log", []) if strategy is not None else [])
    if benchmark is not None and not benchmark.empty:
        result.benchmark_curve = benchmark

    return result


def date_bounds(df, date_column: str = "date") -> tuple[str | None, str | None]:
    """从数据里取首尾日期（字符串）。"""
    if df is None or df.empty:
        return None, None
    values = df[date_column].astype(str)
    return values.iloc[0], values.iloc[-1]
