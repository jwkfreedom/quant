"""缩量买入 + 止盈止损策略（backtrader）。

由原 strategy/test1.py 迁移；阶段 2.4 起支持参数化与成交记录。
"""

from __future__ import annotations

import logging
from datetime import datetime

import backtrader as bt
import pandas as pd

from quant.price.loader import get_stock_price
from quant.strategy.runner import BacktestResult, benchmark_curve, build_cerebro, date_bounds, extract_result

logger = logging.getLogger(__name__)

#: 算法说明（界面「策略说明」区直接展示）
RULES: list[str] = [
    "数据：个股日线（前复权收盘价），取自数据库 daily_price 表",
    "指标 均量：过去 volume_ma 个交易日成交量的简单移动平均（SMA）",
    "买入：空仓 且 当日成交量 < 缩量阈值 × 均量 → 市价买入（即「缩量」时进场）",
    "卖出：持仓 且 满足任一条件 → 市价全部卖出",
    "    · 收盘价 < 买入价 × (1 - 止损比例)",
    "    · 收盘价 > 买入价 × (1 + 止盈比例)",
    "买入价取实际成交价；未触发止盈止损则一直持有",
    "仓位与费用：每次建仓最多使用可用资金的 95%（PercentSizer），"
    "手续费按「手续费率」收取，不计滑点",
    "基准：同区间「买入持有」净值曲线",
]

#: 可在界面上调整的参数
PARAMS_SPEC = [
    {"name": "volume_ratio", "label": "缩量阈值", "type": "float", "default": 0.4,
     "min": 0.05, "max": 1.0, "step": 0.05, "help": "当日量低于 N 倍均量时买入"},
    {"name": "volume_ma", "label": "均量周期", "type": "int", "default": 20, "min": 3, "max": 120},
    {"name": "stop_loss", "label": "止损比例", "type": "float", "default": 0.05,
     "min": 0.01, "max": 0.5, "step": 0.01, "help": "相对买入价下跌该比例卖出"},
    {"name": "take_profit", "label": "止盈比例", "type": "float", "default": 0.30,
     "min": 0.05, "max": 2.0, "step": 0.05, "help": "相对买入价上涨该比例卖出"},
]


class VolumeBreakoutStrategy(bt.Strategy):
    """缩量买入策略（原名 MyStrategy）。"""

    params = (
        ("volume_ratio", 0.4),
        ("volume_ma", 20),
        ("stop_loss", 0.05),
        ("take_profit", 0.30),
    )

    def __init__(self):
        self.dataclose = self.datas[0].close
        self.dataopen = self.datas[0].open
        self.datavolume = self.datas[0].volume

        self.order = None
        self.buyprice = None
        self.buycomm = None
        self.trade_log: list[dict] = []

        self.avg_volume = bt.indicators.SMA(self.datavolume, period=self.p.volume_ma)

    def next(self):
        if self.order:
            return

        # 只在空仓时买入（原实现没有这个判断，配合百分比仓位会反复加仓并把现金打成负数）
        if not self.position and self.datavolume[0] < self.p.volume_ratio * self.avg_volume[0]:
            self.order = self.buy()
            return

        if self.position and self.buyprice is not None and (
            self.dataclose[0] < self.buyprice * (1 - self.p.stop_loss)
            or self.dataclose[0] > self.buyprice * (1 + self.p.take_profit)
        ):
            self.order = self.sell()

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    f"BUY EXECUTED, Price: {order.executed.price:.2f}, "
                    f"Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}"
                )
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
            else:
                self.log(
                    f"SELL EXECUTED, Price: {order.executed.price:.2f}, "
                    f"Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}"
                )

            self.trade_log.append({
                "date": self.data.datetime.date(0).isoformat(),
                "side": "买入" if order.isbuy() else "卖出",
                "price": round(float(order.executed.price), 4),
                "size": float(order.executed.size),
                "value": round(float(abs(order.executed.value)), 2),
                "commission": round(float(order.executed.comm), 2),
            })
            self.order = None

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log("Order Canceled/Margin/Rejected")

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.log(f"OPERATION PROFIT, GROSS {trade.pnl:.2f}, NET {trade.pnlcomm:.2f}")

    def log(self, text):  # 原为 log(slef, str)
        logger.info("%s", text)


def run_backtest(
    stock_id: str = "000001",
    fromdate: datetime | None = None,
    cash: float = 100000.0,
    commission: float = 0.001,
    plot: bool = False,
    volume_ratio: float = 0.4,
    volume_ma: int = 20,
    stop_loss: float = 0.05,
    take_profit: float = 0.30,
) -> BacktestResult:
    """运行缩量买入策略回测，返回统一结果对象。"""
    df = get_stock_price(stock_id)
    if df.empty:
        raise FileNotFoundError(f"{stock_id} 无日线数据，请先运行 quant update-price --stock {stock_id}")

    params = {
        "volume_ratio": float(volume_ratio),
        "volume_ma": int(volume_ma),
        "stop_loss": float(stop_loss),
        "take_profit": float(take_profit),
    }

    df = df.sort_values("date")
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d")
    start_date = fromdate or datetime(2022, 1, 1)

    data = bt.feeds.PandasData(
        dataname=df,
        datetime="date",
        open="open",
        high="high",
        low="low",
        close="close",
        volume="volume",
        fromdate=start_date,
    )

    cerebro = build_cerebro(cash=cash, commission=commission)
    cerebro.adddata(data, name=stock_id)
    cerebro.addstrategy(VolumeBreakoutStrategy, **params)

    subset = df[df["date"] >= start_date]
    start, end = date_bounds(subset)
    result = extract_result(
        cerebro, "volume_breakout", stock_id, cash, bars=len(subset), start=start, end=end,
        params=params,
        benchmark=benchmark_curve(subset, cash, price_column="close"),
    )

    if plot:
        import matplotlib.pyplot as plt

        plt.rcParams["figure.figsize"] = [15, 12]
        plt.rcParams.update({"font.size": 12})
        cerebro.plot(iplot=False)

    logger.info("\n%s", result.report())
    return result
