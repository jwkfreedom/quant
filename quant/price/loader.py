"""行情：日线读取与估值（PE/PB）。

由原 stockdata.py 等价迁移，算法未改动。
"""

from __future__ import annotations

import logging

import pandas as pd

from quant.config import DATA_DIR
from quant.foundation.financial import calc_ttm, fix_financial_data, update_price_pe
from quant.foundation.season import get_season_iDATE

logger = logging.getLogger(__name__)

#: 原始中文列名 -> 内部英文列名
PRICE_COLUMN_MAP: dict[str, str] = {
    "开盘": "open",
    "日期": "date",
    "收盘": "close",
    "最高": "high",
    "最低": "low",
    "开盘_qfq": "open_qfq",
    "收盘_qfq": "close_qfq",
    "最高_qfq": "high_qfq",
    "最低_qfq": "low_qfq",
    "成交量": "volumn",
    "成交额": "turnover",
    "振幅": "amp",
    "涨跌幅": "percent_change",
    "涨跌额": "value_change",
    "换手率": "turnover_rate",
}

#: 前复权覆盖的四个价格列
PRICE_COLUMNS: tuple[str, ...] = ("open", "close", "high", "low")


def price_file(symbol: str, part: str) -> "Path":
    """返回某只股票的价格文件路径。part 取 'pre'（今年以前）或 'cur'（今年）。"""
    return DATA_DIR / "a" / "stock" / "price" / f"price_{symbol}_{part}.csv"


def get_stock_price(symbol: str) -> pd.DataFrame:
    """读取一只股票的日线数据（pre + cur 拼接，前复权覆盖未复权）。

    返回列：open/close/high/low（前复权）、*_org（未复权）、volumn、turnover、
    percent_change、turnover_rate、DATE、iDATE。
    """
    df_price = pd.concat([pd.read_csv(price_file(symbol, "pre")), pd.read_csv(price_file(symbol, "cur"))])

    df_price.rename(columns=PRICE_COLUMN_MAP, inplace=True)

    for column in PRICE_COLUMNS:
        df_price[f"{column}_org"] = df_price[column]

    for column in PRICE_COLUMNS:
        df_price[column] = df_price[f"{column}_qfq"]

    df_price["DATE"] = df_price["date"].str.replace("-", "")
    df_price["iDATE"] = pd.to_numeric(df_price["DATE"], errors="coerce")
    df_price = df_price.drop("DATE", axis=1)
    return df_price


def get_full_price(symbol: str) -> pd.DataFrame:
    """读取一只股票的完整数据：日线 + PE/PB，date 作为索引。

    步骤：
        1. 读 financial_report_{symbol}.csv，修补字段并计算 profitTTM / netassetTTM
        2. 读日线，按季度打 season 标记
        3. 合并计算 PE / PB
        4. 把 date 设为索引
    """
    df_financial = pd.read_csv(DATA_DIR / "a" / "stock" / "financial" / f"financial_report_{symbol}.csv")

    fix_financial_data(df_financial)
    df_financial = calc_ttm(df_financial, "摊薄每股收益(元)", "profitTTM")
    df_financial = calc_ttm(df_financial, "每股净资产_调整后(元)", "netassetTTM")

    df_financial.drop(df_financial[df_financial["profitTTM"] == "--"].index, inplace=True)

    df_price = get_stock_price(symbol)
    df_price["season"] = df_price["date"].apply(get_season_iDATE)
    df_price.reset_index(drop=True, inplace=True)

    df_price = update_price_pe(df_price, df_financial)

    df_price["date"] = pd.to_datetime(df_price["date"])
    df_price.set_index("date", inplace=True)
    return df_price
