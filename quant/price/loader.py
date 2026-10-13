"""行情：日线读取与估值（PE/PB）。

阶段 2.2 起数据源由「每只股票两个 CSV」改为 **SQLite**（`data/quant.db`）：
    - 不再有 pre/cur 文件缺失导致 FileNotFoundError 的问题
    - 读取结果按日期升序，修掉了旧实现「拼接顺序即行序」的隐患

返回的 DataFrame 列（与重构前兼容）：
    date, idate
    open/high/low/close            -> **前复权**（回测默认口径，沿用旧语义）
    open_qfq/high_qfq/...          -> 前复权（显式名）
    open_org/high_org/low_org/close_org -> **不复权**（沿用旧语义）
    volume, turnover, amplitude, pct_change, price_change, turnover_rate
"""

from __future__ import annotations

import logging
import sqlite3

import pandas as pd

from quant.data import schema, store
from quant.foundation.financial import compute_pe_pb, financial_to_ttm
from quant.foundation.season import get_season_iDATE

logger = logging.getLogger(__name__)

#: 需要同时给出「前复权 / 不复权」两套的字段
_OHLC = ("open", "high", "low", "close")


def _price_frame_from_db(df_db: pd.DataFrame) -> pd.DataFrame:
    """把数据库行转换为对外的行情 DataFrame。"""
    if df_db.empty:
        return pd.DataFrame(columns=list(schema.PRICE_FRAME_COLUMNS))

    df = df_db.copy()
    # 数据库里 open/close... 是不复权，*_qfq 是前复权
    for column in _OHLC:
        df[f"{column}_org"] = df[column]
        df[column] = df[f"{column}_qfq"]

    return df.loc[:, [c for c in schema.PRICE_FRAME_COLUMNS if c in df.columns]]


def get_stock_price(
    symbol: str,
    start: int | None = None,
    end: int | None = None,
    *,
    conn: sqlite3.Connection | None = None,
) -> pd.DataFrame:
    """读取一只股票的日线数据（按日期升序）。

    参数 start/end 为 YYYYMMDD 整数边界，可选。
    """
    symbol = str(symbol).zfill(6)
    if conn is not None:
        return _price_frame_from_db(store.read_price(conn, symbol, start, end))
    with store.open_db() as own_conn:
        return _price_frame_from_db(store.read_price(own_conn, symbol, start, end))


def get_etf_price(symbol: str, *, conn: sqlite3.Connection | None = None) -> pd.DataFrame:
    """读取一只 ETF 的日线（ETF 数据本身已是前复权）。"""
    if conn is not None:
        return store.read_etf_price(conn, symbol)
    with store.open_db() as own_conn:
        return store.read_etf_price(own_conn, symbol)


def get_financial(symbol: str, *, conn: sqlite3.Connection | None = None) -> pd.DataFrame:
    """读取一只股票的财务指标（已补 TTM）。"""
    symbol = str(symbol).zfill(6)
    if conn is not None:
        return financial_to_ttm(store.read_financial(conn, symbol))
    with store.open_db() as own_conn:
        return financial_to_ttm(store.read_financial(own_conn, symbol))


def _get_full_price(conn: sqlite3.Connection, symbol: str) -> pd.DataFrame:
    df_price = get_stock_price(symbol, conn=conn)
    if df_price.empty:
        raise FileNotFoundError(
            f"数据库中没有 {symbol} 的日线数据，请先运行 quant update-price --stock {symbol}"
        )

    df_financial = get_financial(symbol, conn=conn)

    df_price = df_price.copy()
    df_price["season"] = df_price["date"].apply(get_season_iDATE)

    if df_financial.empty:
        logger.warning("%s 没有财务指标数据，PE/PB 置 0", symbol)
        df_price["PE"] = 0.0
        df_price["PB"] = 0.0
    else:
        df_price = compute_pe_pb(df_price, df_financial)

    df_price["date"] = pd.to_datetime(df_price["date"])
    return df_price.set_index("date").sort_index()


def get_full_price(symbol: str, *, conn: sqlite3.Connection | None = None) -> pd.DataFrame:
    """读取一只股票的完整数据：日线 + PE / PB，date 作为索引。"""
    symbol = str(symbol).zfill(6)
    if conn is not None:
        return _get_full_price(conn, symbol)
    with store.open_db() as own_conn:
        return _get_full_price(own_conn, symbol)
