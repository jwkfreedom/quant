"""回测冒烟测试（使用合成数据库里的日线数据）。

这里直接把合成数据库的日线喂给 backtrader，验证「取数 -> 回测 -> 结果提取」整条链路。
"""

from __future__ import annotations

import backtrader as bt
import pandas as pd
import pytest

from quant.data import store
from quant.strategy.runner import build_cerebro, date_bounds, extract_result

from conftest import DATES, SYMBOLS


@pytest.fixture
def price_frame(sample_db):
    with store.open_db(sample_db) as conn:
        return store.read_price(conn, SYMBOLS[0])


def test_build_cerebro_configures_cash_and_sizer():
    cerebro = build_cerebro(cash=50000.0, commission=0.002)
    assert cerebro.broker.getcash() == pytest.approx(50000.0)
    # 必须注册了 sizer，否则默认每次只买 1 股，回测结果没有意义
    assert cerebro.sizers


def test_extract_result_returns_metrics(price_frame):
    data = price_frame.rename(columns={
        "date": "datetime", "open_qfq": "open", "high_qfq": "high",
        "low_qfq": "low", "close_qfq": "close",
    })
    data["datetime"] = pd.to_datetime(data["datetime"])
    data = data.set_index("datetime").sort_index()

    class BuyAndHold(bt.Strategy):
        def next(self):
            if not self.position:
                self.buy()

    cerebro = build_cerebro(cash=100000.0, commission=0.0)
    cerebro.adddata(bt.feeds.PandasData(dataname=data))
    cerebro.addstrategy(BuyAndHold)

    start, end = date_bounds(price_frame)
    result = extract_result(cerebro, "buy_and_hold", SYMBOLS[0], 100000.0,
                            bars=len(price_frame), start=start, end=end)

    assert result.symbol == SYMBOLS[0]
    assert result.start == DATES[0]
    assert result.end == DATES[-1]
    assert result.bars == len(DATES)
    # 合成数据是单调上涨的，买入持有应该盈利
    assert result.final_value > 100000.0
    assert result.return_pct > 0
