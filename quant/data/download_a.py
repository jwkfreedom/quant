"""A股数据采集（akshare）——纯取数层，不负责落库。

阶段 2.2 重构：
    - 拆成「取数」与「入库」两层：本模块只返回 DataFrame，落库由
      quant.data.update / quant.data.migrate 负责
    - 季度基本面原始 CSV 直接落在 data/original/jibenmian/（原始件归档区），
      再由 update 摄入数据库
    - 删除了旧的 price CSV 双文件（_pre/_cur）落盘逻辑
"""

from __future__ import annotations

import datetime
import logging
import time
from collections.abc import Iterable

import akshare as ak
import pandas as pd

from quant.config import DATA_DIR, ORIGINAL_DIR
from quant.data.frames import merge_adjusted
from quant.data.universe import ETF_LIST

logger = logging.getLogger(__name__)

#: 季度基本面三表 -> akshare 接口
JIBENMIAN_TYPES: dict[str, str] = {
    "zcfz": "stock_zcfz_em",
    "lrb": "stock_lrb_em",
    "xjll": "stock_xjll_em",
}

#: 季度日期模板
SEASON_SUFFIXES: tuple[str, ...] = ("0331", "0630", "0930", "1231")

#: 原始件归档目录（下载回来的 CSV 落在这里）
JIBENMIAN_DIR = ORIGINAL_DIR / "jibenmian"
ETF_DIR = ORIGINAL_DIR / "etf"

#: akshare 日线返回的中文列
_PRICE_COLUMNS = ["日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额", "振幅", "涨跌幅", "涨跌额", "换手率"]

#: ETF 接口返回的中文列 -> 归档 CSV 使用的英文列名（与旧 download_etf 落盘格式一致）
_ETF_RENAME = {
    "日期": "date", "开盘": "open", "收盘": "close", "最高": "high", "最低": "low",
    "成交量": "volumn", "成交额": "turnover", "振幅": "amp",
    "涨跌幅": "percent_change", "涨跌额": "value_change", "换手率": "turnover_rate",
}

#: 默认全历史起点
DEFAULT_START = "20100101"

#: 接口调用间隔（秒），避免被限流
DEFAULT_DELAY = 0.3


# --------------------------------------------------------------------------
# 股票代码
# --------------------------------------------------------------------------
def platform_symbol(stock_id, platform: str = "") -> str:
    """把数字股票代码规范化为各数据源要求的格式。

    eastmoney: 603339 -> 'SH603339'，2985 -> 'SZ002985'
    sinaprice: 603339 -> 'sh603339'，2985 -> 'sz002985'
    """
    stock_id = str(stock_id).zfill(6)
    if platform == "eastmoney":
        if stock_id.startswith(("0", "3")):
            return "SZ" + stock_id
        if stock_id.startswith("6"):
            return "SH" + stock_id
        logger.warning("not support stockId: %s", stock_id)
    elif platform == "sinaprice":
        if stock_id.startswith(("0", "3")):
            return "sz" + stock_id
        if stock_id.startswith("6"):
            return "sh" + stock_id
        logger.warning("not support stockId: %s", stock_id)
    return stock_id


PlatformSymbol = platform_symbol


# --------------------------------------------------------------------------
# 股票池
# --------------------------------------------------------------------------
def latest_jibenmian_file(table: str = "zcfz"):
    """返回 data/original/jibenmian 下最新的 <table>_YYYYMMDD.csv。"""
    files = sorted(JIBENMIAN_DIR.glob(f"{table}_*.csv"))
    if not files:
        raise FileNotFoundError(f"未找到任何 {table}_*.csv，请先运行 quant update-jibenmian")
    return files[-1]


def all_a_stocks(list_file=None) -> list[str]:
    """获取全部 A 股代码（6 位字符串列表）。

    默认读取归档区中最新的 zcfz 季度文件中的股票代码列。
    """
    path = list_file or latest_jibenmian_file("zcfz")
    df = pd.read_csv(path)
    codes = [platform_symbol(code) for code in df["股票代码"]]
    logger.info("股票池来源 %s，共 %d 只", path, len(codes))
    return codes


def fetch_stock_universe() -> pd.DataFrame:
    """从 akshare 拉取沪深 A 股实时快照（代码 + 名称），作为动态股票池。

    TODO(2.3): 用于替代基于季度报表文件的股票池来源。
    """
    df = ak.stock_zh_a_spot_em()
    df = df.rename(columns={"代码": "symbol", "名称": "name"})
    df["symbol"] = df["symbol"].astype(str).str.zfill(6)
    return df.loc[:, ["symbol", "name"]]


# --------------------------------------------------------------------------
# 季度基本面
# --------------------------------------------------------------------------
def fetch_jibenmian(table: str, date: str) -> pd.DataFrame:
    """拉取某一季度的全市场基本面快照。

    参数 table 取 'zcfz' / 'lrb' / 'xjll'；date 形如 '20230930'。
    """
    funcs = {"zcfz": ak.stock_zcfz_em, "lrb": ak.stock_lrb_em, "xjll": ak.stock_xjll_em}
    if table not in funcs:
        raise ValueError(f"error type: {table}（可选 {sorted(funcs)}）")
    return funcs[table](date=date)


def save_jibenmian_raw(table: str, date: str, df: pd.DataFrame, *, overwrite: bool = True):
    """把季度快照落盘到归档区，返回文件路径。"""
    JIBENMIAN_DIR.mkdir(parents=True, exist_ok=True)
    dest = JIBENMIAN_DIR / f"{table}_{date}.csv"
    if dest.exists() and not overwrite:
        logger.info("已存在，跳过落盘: %s", dest)
        return dest
    df.to_csv(dest, index=False, encoding="utf_8_sig")
    logger.info("已写入 %s (%d 行)", dest, len(df))
    return dest


def fetch_jibenmian_season(table: str, date: str, *, force: bool = False) -> pd.DataFrame | None:
    """拉取并归档一个季度的快照；已存在且未强制时返回 None（表示无需更新）。"""
    dest = JIBENMIAN_DIR / f"{table}_{date}.csv"
    if dest.is_file() and not force:
        return None
    df = fetch_jibenmian(table, date)
    save_jibenmian_raw(table, date, df)
    return df


# --------------------------------------------------------------------------
# 日线
# --------------------------------------------------------------------------
def fetch_price_raw(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """拉取不复权日线。"""
    return ak.stock_zh_a_hist(symbol=platform_symbol(symbol), period="daily",
                              start_date=start_date, end_date=end_date, adjust="")


def fetch_price_qfq(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """拉取前复权日线。"""
    return ak.stock_zh_a_hist(symbol=platform_symbol(symbol), period="daily",
                              start_date=start_date, end_date=end_date, adjust="qfq")


def fetch_price(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """拉取并合并「不复权 + 前复权」日线，返回带 *_qfq 列的原始中文表。"""
    raw = fetch_price_raw(symbol, start_date, end_date)
    if raw is None or raw.empty:
        return pd.DataFrame(columns=_PRICE_COLUMNS)
    adjusted = fetch_price_qfq(symbol, start_date, end_date)
    return merge_adjusted(raw, adjusted)


# --------------------------------------------------------------------------
# ETF
# --------------------------------------------------------------------------
def fetch_etf(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """拉取 ETF 前复权日线。

    返回列名统一为归档 CSV 使用的英文名（date/open/close/high/low/volumn/turnover/...），
    便于直接交给 quant.data.frames.prepare_etf_frame 处理。
    """
    df = ak.fund_etf_hist_em(symbol, period="daily", start_date=start_date,
                             end_date=end_date, adjust="qfq")
    if df is None or df.empty:
        return pd.DataFrame()
    return df.rename(columns=_ETF_RENAME)


def fetch_etf_list() -> pd.DataFrame:
    """拉取全部 ETF 实时列表（用于筛选题材池）。"""
    return ak.fund_etf_spot_em()


def save_etf_list(df: pd.DataFrame, name: str = "etf_spot"):
    """把 ETF 列表落盘到归档区。"""
    ETF_DIR.mkdir(parents=True, exist_ok=True)
    dest = ETF_DIR / f"{name}.csv"
    df.to_csv(dest, index=False, encoding="utf_8_sig")
    return dest


def default_symbols() -> list[str]:
    """默认标的池（ETF）。"""
    return list(ETF_LIST)


def today_compact() -> str:
    """今天的 YYYYMMDD。"""
    return datetime.datetime.now().strftime("%Y%m%d")


def sleep(delay: float = DEFAULT_DELAY) -> None:
    if delay > 0:
        time.sleep(delay)


__all__ = [
    "JIBENMIAN_TYPES", "SEASON_SUFFIXES", "DEFAULT_START", "DEFAULT_DELAY",
    "JIBENMIAN_DIR", "ETF_DIR",
    "platform_symbol", "PlatformSymbol", "all_a_stocks", "latest_jibenmian_file",
    "fetch_stock_universe", "fetch_jibenmian", "save_jibenmian_raw",
    "fetch_jibenmian_season", "fetch_price", "fetch_price_raw", "fetch_price_qfq",
    "fetch_etf", "fetch_etf_list", "save_etf_list", "default_symbols",
    "today_compact", "sleep",
]
