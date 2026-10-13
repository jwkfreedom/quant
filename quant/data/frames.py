"""把各种来源的原始 DataFrame 规范化为「可直接写库」的形式。

来源有三种：
    1. 历史价格 CSV（data/original 迁移前的 price_XXXXXX_pre/cur.csv）
    2. akshare 实时拉取（stock_zh_a_hist 不复权 + qfq 合并）
    3. ETF CSV / akshare ETF 接口
统一在这里处理日期规范化、列名映射、去重排序与数值化，避免各处重复实现。
"""

from __future__ import annotations

import logging

import pandas as pd

from quant.data import schema

logger = logging.getLogger(__name__)

_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"


def _normalize_dates(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["date"] = df["date"].astype(str).str.strip()
    df = df[df["date"].str.match(_DATE_PATTERN, na=False)]
    df = df.drop_duplicates(subset=["date"], keep="last").sort_values("date")
    df["idate"] = df["date"].str.replace("-", "", regex=False).astype("int64")
    return df


def _to_numeric(df: pd.DataFrame, columns) -> pd.DataFrame:
    for column in columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def prepare_price_frame(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """原始价格表（中文列名，含 _qfq 后缀）-> daily_price 表结构。

    输入需包含 '日期' 列；缺失的数值列会补成 NaN。
    """
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.rename(columns=schema.PRICE_COLUMN_MAP)
    if "date" not in df.columns:
        logger.warning("%s 缺少日期列，跳过", symbol)
        return pd.DataFrame()

    df["symbol"] = str(symbol).zfill(6)
    df = _normalize_dates(df)
    for column in ("symbol", "date", "idate", *schema.PRICE_VALUE_COLUMNS):
        if column not in df.columns:
            df[column] = None
    df = _to_numeric(df, schema.PRICE_VALUE_COLUMNS)
    return df.loc[:, ["symbol", "date", "idate", *schema.PRICE_VALUE_COLUMNS]]


def prepare_etf_frame(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """ETF 原始表（英文列名，volumn/amp 为历史拼写）-> etf_daily 表结构。"""
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.rename(columns=schema.ETF_COLUMN_MAP)
    if "date" not in df.columns:
        return pd.DataFrame()

    df["symbol"] = str(symbol).zfill(6)
    df = _normalize_dates(df)

    columns = (
        "symbol", "date", "idate",
        "open_qfq", "high_qfq", "low_qfq", "close_qfq",
        "volume", "turnover", "amplitude", "pct_change", "price_change", "turnover_rate",
    )
    for column in columns:
        if column not in df.columns:
            df[column] = None
    df = _to_numeric(df, [c for c in columns if c not in ("symbol", "date", "idate")])
    return df.loc[:, list(columns)]


def merge_adjusted(raw: pd.DataFrame, adjusted: pd.DataFrame, date_column: str = "日期") -> pd.DataFrame:
    """把不复权表与前复权表按日期合并成一张带 *_qfq 列的表。

    二者来自同一个接口的同一次请求，日期集合一般一致；不一致时按左表对齐并告警。
    """
    if raw is None or raw.empty:
        return pd.DataFrame()

    merged = raw.copy()
    if adjusted is None or adjusted.empty:
        logger.warning("前复权数据为空，只保留不复权列")
        return merged

    price_columns = ["开盘", "收盘", "最高", "最低"]
    adjusted = adjusted.loc[:, [date_column, *price_columns]].rename(
        columns={c: f"{c}_qfq" for c in price_columns}
    )

    if len(adjusted) != len(raw):
        logger.warning("不复权 %d 行 / 前复权 %d 行，按日期对齐", len(raw), len(adjusted))

    return merged.merge(adjusted, on=date_column, how="left")
