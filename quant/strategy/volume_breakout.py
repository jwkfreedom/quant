"""缩量买入 + 止盈止损策略（backtrader）。

由原 strategy/test1.py 迁移：策略逻辑未改动，仅把模块级执行包装为 run_backtest()。

策略要点：
    - 当日成交量低于 20 日均量的 40% 时买入
    - 相对买入价下跌 5% 或上涨 30% 时卖出

TODO(2.2): 原实现存在两个问题（保持原样迁移，未修改）：
    1. log(self, str) 的参数名拼写错误且遮蔽内置 str
    2. 第二次 self.order 判空后，buyprice 分支永远不会在同一天生效
"""

from __future__ import annotations

import logging
from datetime import datetime

import backtrader as bt
import pandas as pd

from quant.price.loader import get_stock_price

logger = logging.getLogger(__name__)


class VolumeBreakoutStrategy(bt.Strategy):
    """缩量买入策略（原名 MyStrategy）。"""

    def __init__(self):
        self.dataclose = self.datas[0].close
        self.dataopen = self.datas[0].open
        self.datavolume = self.datas[0].volume

        self.order = None
        self.buyprice = None
        self.buycomm = None

        self.avg_volume = bt.indicators.SMA(self.datavolume, period=20)

    def next(self):
        if self.order:
            return

        if self.datavolume[0] < 0.4 * self.avg_volume[0]:
            self.order = self.buy()

        if self.order:
            return

        if self.buyprice is not None and (
            self.dataclose[0] < self.buyprice * 0.95 or self.dataclose[0] > self.buyprice * 1.3
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

            self.order = None

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log("Order Canceled/Margin/Rejected")

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.log(f"OPERATION PROFIT, GROSS {trade.pnl:.2f}, NET {trade.pnlcomm:.2f}")

    def log(self, text):  # 原为 log(slef, str)
        logger.info("%s", text)


def run_backtest(stock_id: str = "000002", fromdate: datetime | None = None, plot: bool = False):
    """运行缩量买入策略回测。"""
    df = get_stock_price(stock_id)
    df = df.sort_values("date")
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d")

    data = bt.feeds.PandasData(
        dataname=df,
        datetime="date",
        open="open",
        high="high",
        low="low",
        close="close",
        volume="volumn",
        fromdate=fromdate or datetime(2022, 1, 1),
    )

    cerebro = bt.Cerebro()
    cerebro.adddata(data)
    cerebro.addstrategy(VolumeBreakoutStrategy)
    cerebro.run()

    if plot:
        import matplotlib.pyplot as plt

        plt.rcParams["figure.figsize"] = [15, 12]
        plt.rcParams.update({"font.size": 12})
        cerebro.plot(iplot=False)

    return cerebro


if __name__ == "__main__":  # pragma: no cover
    from quant.config import setup_logging

    setup_logging()
    run_backtest(plot=True)
