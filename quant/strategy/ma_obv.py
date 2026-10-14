"""MA + OBV 策略（backtrader）。

由原 strategy/bt_ova.py 迁移；阶段 2.4 起支持参数化与成交记录，供 UI 的回测页使用。
"""

from __future__ import annotations

import logging

import backtrader as bt
import pandas as pd

from quant.price.loader import get_etf_price
from quant.strategy.runner import BacktestResult, benchmark_curve, build_cerebro, date_bounds, extract_result

logger = logging.getLogger(__name__)

#: 默认回测标的（半导体 ETF）
DEFAULT_ETF = "512480"

#: 可在界面上调整的参数
PARAMS_SPEC = [
    {"name": "ma_period", "label": "均线周期", "type": "int", "default": 20, "min": 2, "max": 250,
     "help": "收盘价上穿该均线才考虑买入"},
    {"name": "obv_period", "label": "OBV 周期", "type": "int", "default": 14, "min": 2, "max": 60,
     "help": "OBV 指标的最小周期"},
]


class MyOBV(bt.Indicator):
    """自研 OBV 指标：收盘涨则加成交量，跌则减，平则不变。

    .. note::
       原实现只写了 `next()`，起始值一直是 NaN，导致 `obv > 0` 永远为假、
       策略从不买入（0 笔交易）。这里补一个 `nextstart()` 给 OBV 播种，
       指标口径本身不变。
    """

    lines = ("obv",)
    params = (("period", 14),)

    def __init__(self):
        self.addminperiod(self.params.period)

    def nextstart(self):
        """第一个可用 bar：OBV 从 0 起算（标准口径）。"""
        self.lines.obv[0] = 0.0

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
        ("ma_period", 20),
        ("obv_period", 14),
    )

    def __init__(self):
        self.ma = bt.indicators.SMA(self.data.close, period=self.p.ma_period)
        self.obv = MyOBV(self.data, period=self.p.obv_period)

        self.buy_signal = bt.And(self.data.close > self.ma, self.obv > 0)
        self.sell_signal = bt.And(self.data.close < self.ma, self.obv < 0)
        self.trade_log: list[dict] = []

    def next(self):
        if not self.position and self.buy_signal:
            self.buy()
        elif self.position and self.sell_signal:
            self.sell()

    def notify_order(self, order):
        if order.status != order.Completed:
            return
        self.trade_log.append({
            "date": self.data.datetime.date(0).isoformat(),
            "side": "买入" if order.isbuy() else "卖出",
            "price": round(float(order.executed.price), 4),
            "size": float(order.executed.size),
            "value": round(float(abs(order.executed.value)), 2),
            "commission": round(float(order.executed.comm), 2),
        })


def run_backtest(
    etf_symbol: str = DEFAULT_ETF,
    cash: float = 100000.0,
    commission: float = 0.001,
    plot: bool = False,
    ma_period: int = 20,
    obv_period: int = 14,
) -> BacktestResult:
    """运行 MA+OBV 回测，返回统一结果对象。数据来自 SQLite 的 etf_daily 表。"""
    df = get_etf_price(etf_symbol)
    if df.empty:
        raise FileNotFoundError(
            f"ETF {etf_symbol} 无数据，请先运行 quant update-etf --symbol {etf_symbol}"
        )

    params = {"ma_period": int(ma_period), "obv_period": int(obv_period)}

    data = df.rename(columns={
        "date": "datetime", "open_qfq": "open", "high_qfq": "high",
        "low_qfq": "low", "close_qfq": "close",
    })
    data["datetime"] = pd.to_datetime(data["datetime"])
    data = data.set_index("datetime").sort_index()

    cerebro = build_cerebro(cash=cash, commission=commission)
    cerebro.adddata(bt.feeds.PandasData(dataname=data), name=etf_symbol)
    cerebro.addstrategy(MAOBVStrategy, **params)

    start, end = date_bounds(df)
    result = extract_result(
        cerebro, "ma_obv", etf_symbol, cash, bars=len(df), start=start, end=end,
        params=params,
        benchmark=benchmark_curve(df, cash, price_column="close_qfq"),
    )

    if plot:
        cerebro.plot()

    logger.info("\n%s", result.report())
    return result
