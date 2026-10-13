"""选股 / 交易记录读写。

由原 trade/trade.py 迁移：
    - 删除模块级的 pd.read_csv + doStrategy 调用（原实现 import 即执行）
    - 删除逐行 print 调试残留
    - 数据文件随包存放在 quant/trade/records.csv

TODO(2.2): 记录表迁入 SQLite（data/quant.db），本模块改为读写数据库。
TODO(2.3): 补齐真实的策略执行与模拟盘逻辑。
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from quant.data import update
from quant.price.loader import get_stock_price

logger = logging.getLogger(__name__)

#: 默认记录文件（随包分发）
DEFAULT_RECORDS_PATH = Path(__file__).resolve().parent / "records.csv"

#: 交易策略参数：涨幅大于 win_sell 或跌幅大于 lose_sell 卖出，最大持股 max_hold 天（第一天为第 0 天）
STRATEGY = {"win_sell": 0.03, "lose_sell": 0.05, "max_hold": 5}


def load_records(path=None) -> pd.DataFrame:
    """读取选股/交易记录，返回 DataFrame。

    列：stockId, date, fitler
    """
    return pd.read_csv(path or DEFAULT_RECORDS_PATH)


def prepare_price_data(df: pd.DataFrame) -> dict:
    """按记录中的股票代码补齐/刷新日线数据（写入 SQLite）。"""
    symbol_column = "symbol" if "symbol" in df.columns else "stockId"
    symbols = [str(value).zfill(6) for value in df[symbol_column]]
    return update.update_price(symbols=sorted(set(symbols)), mode="incremental")


def collect_closes(stock_id: str, startdate: str) -> list[float]:
    """取某只股票从 startdate 起的未复权收盘价序列。

    startdate 格式：'2023/11/28'
    """
    idate = int(startdate.replace("/", ""))
    df = get_stock_price(stock_id)
    df = df[df["iDATE"] >= idate]

    prices = [float(row["close_org"]) for _index, row in df.iterrows()]
    logger.info("stock=%s, days=%d", stock_id, len(prices))
    return prices


if __name__ == "__main__":  # pragma: no cover
    from quant.config import setup_logging

    setup_logging()
    records = load_records()
    print(records.head())
