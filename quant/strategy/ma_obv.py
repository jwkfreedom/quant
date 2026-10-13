"""MA + OBV 策略（backtrader）。

由原 strategy/bt_ova.py 迁移：指标与策略逻辑未改动，仅把模块级的回测执行
包装为 run_backtest()，使其可被 CLI 调用而不产生导入副作用。
"""

from __future__ import annotations

import logging

import backtrader as bt
import pandas as pd

from quant.price.loader import get_etf_price

logger = logging.getLogger(__name__)

#: 默认回测标的（半导体 ETF）
DEFAULT_ETF = "512480"


class MyOBV(bt.Indicator):
    """自研 OBV 指标：收盘涨则加成交量，跌则减，平则不变。"""

    lines = ("obv",)
    params = (("period", 14),)

    def __init__(self):
        self.addminperiod(self.params.period)

    def next(self):
        if self.data.close[0] > self.data.close[-1]:
            self.lines.obv[0] = self.lines.obv[-1] + self.data.volume[0]
        elif self.data.close[0] < self.data.close[-1]:
            self.lines.obv[0] = self.lines.obv[-1] - self.data.volume[0]
        else:
            self.lines.obv[0] = self.lines.obv[-1]


class MAOBVStrategy(bt.Strategy):
    """均线 + OBV 同向策略：价上均线且 OBV>0 买入；价下均线且 OBV<0 卖出。"""

    params = (
        ("ma_period", 20),   # 均线周期
        ("obv_period", 1),   # OBV 周期（保留原参数，当前未使用）
    )

    def __init__(self):
        self.ma = bt.indicators.SMA(self.data.close, period=self.p.ma_period)
        self.obv = MyOBV(self.data, period=14)

        self.buy_signal = bt.And(self.data.close > self.ma, self.obv > 0)
        self.sell_signal = bt.And(self.data.close < self.ma, self.obv < 0)

    def next(self):
        if not self.position and self.buy_signal:
            self.buy()
        elif self.position and self.sell_signal:
            self.sell()


def run_backtest(
    etf_symbol: str = DEFAULT_ETF,
    cash: float = 100000.0,
    commission: float = 0.001,
    plot: bool = False,
) -> float:
    """运行 MA+OBV 回测，返回最终组合市值。数据来自 SQLite 的 etf_daily 表。"""
    df = get_etf_price(etf_symbol)
    if df.empty:
        raise FileNotFoundError(
            f"ETF {etf_symbol} 无数据，请先运行 quant update-etf --symbol {etf_symbol}"
        )

    data = df.rename(columns={
        "date": "datetime", "open_qfq": "open", "high_qfq": "high",
        "low_qfq": "low", "close_qfq": "close",
    })
    data["datetime"] = pd.to_datetime(data["datetime"])
    data = data.set_index("datetime").sort_index()

    cerebro = bt.Cerebro()
    cerebro.adddata(bt.feeds.PandasData(dataname=data))
    cerebro.addstrategy(MAOBVStrategy)
    cerebro.broker.setcash(cash)
    cerebro.broker.setcommission(commission=commission)

    cerebro.run()

    final_value = cerebro.broker.getvalue()
    logger.info("etf       : %s", etf_symbol)
    logger.info("final value: %.2f", final_value)
    logger.info("return     : %.2f%%", (final_value / cash - 1) * 100)

    if plot:
        cerebro.plot()

    return final_value


if __name__ == "__main__":  # pragma: no cover
    from quant.config import setup_logging

    setup_logging()
    run_backtest(plot=True)
