"""A股数据采集（akshare）。

由原 utils/download.py 等价迁移，仅做如下结构性调整：
    - 去掉 sys.path.append 与相对路径，统一走 quant.config.DATA_DIR
    - print 改为 logging
    - ETF 列表收敛到 quant.data.universe
    - all_a_stocks 的股票列表来源改为「自动取最新的 zcfz 季度文件」
      （原实现硬编码 zcfz_20230930.csv，该文件在数据目录中并不存在）

TODO(2.2): to_csv 统一补 index=False（会改变现有落盘格式，需与已下载数据一起迁移）
TODO(2.2): 收窄 except:（当前会静默吞掉一切异常）
"""

from __future__ import annotations

import datetime
import logging
import time
from collections.abc import Iterable, Iterator

import akshare as ak
import pandas as pd

from quant.config import DATA_DIR
from quant.data.universe import ETF_LIST

logger = logging.getLogger(__name__)

#: 季度基本面三表
JIBENMIAN_TYPES: dict[str, str] = {
    "zcfz": "stock_zcfz_em",   # 资产负债表
    "lrb": "stock_lrb_em",     # 利润表
    "xjll": "stock_xjll_em",   # 现金流量表
}

#: 默认季度日期模板
DEFAULT_SEASONS: list[str] = ["{year}0331", "{year}0630", "{year}0930", "{year}1231"]

JIBENMIAN_DIR = DATA_DIR / "a" / "jibenmian"
STOCK_DIR = DATA_DIR / "a" / "stock"
PRICE_DIR = STOCK_DIR / "price"
ETF_PRICE_DIR = DATA_DIR / "a" / "etf" / "price"


# --------------------------------------------------------------------------
# 股票代码 / 标的池
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


#: 兼容旧调用名
PlatformSymbol = platform_symbol


def latest_jibenmian_file(table: str = "zcfz") -> "Path":
    """返回 data/a/jibenmian 下最新的 <table>_YYYYMMDD.csv 路径。

    用于「取一份全市场股票列表」的场景（见 all_a_stocks）。
    """
    files = sorted(JIBENMIAN_DIR.glob(f"{table}_*.csv"))
    if not files:
        raise FileNotFoundError(f"未找到任何 {table}_*.csv，请先运行 quant download-jibenmian")
    return files[-1]


def all_a_stocks(list_file=None) -> list[str]:
    """获取全部 A 股代码，返回 6 位字符串列表。

    默认读取数据目录中最新的 zcfz 季度文件中的股票代码列。
    注意：这只包含该季度报表中出现的股票，因此应选取距拉取时间半年内的季度文件。
    """
    path = list_file or latest_jibenmian_file("zcfz")
    df = pd.read_csv(path)
    codes = [platform_symbol(code) for code in df["股票代码"]]
    logger.info("股票池来源 %s，共 %d 只", path, len(codes))
    return codes


# --------------------------------------------------------------------------
# 基本面：业绩快报（全市场，按季度落盘）
# --------------------------------------------------------------------------
def jibenmian_all_fast(type: str, yStart: int, yEnd: int, season: list[str] | None = None) -> None:
    """下载全市场季度基本面（业绩快报）。

    参数
    ----
    type    : 'zcfz'（资产负债）/ 'lrb'（利润表）/ 'xjll'（现金流量）
    yStart  : 起始年（含）
    yEnd    : 结束年（不含）
    season  : 季度模板列表，默认四个季度全下

    落盘：data/a/jibenmian/{type}_{YYYYMMDD}.csv
    """
    func_map = {
        "zcfz": ak.stock_zcfz_em,
        "lrb": ak.stock_lrb_em,
        "xjll": ak.stock_xjll_em,
    }
    if type not in func_map:
        raise ValueError(f"error type: {type}")
    func = func_map[type]

    seasons = season if season is not None else DEFAULT_SEASONS
    JIBENMIAN_DIR.mkdir(parents=True, exist_ok=True)

    for year in range(yStart, yEnd):
        for template in seasons:
            date = template.format(year=year)
            dest = JIBENMIAN_DIR / f"{type}_{date}.csv"
            df = func(date=date)
            df.to_csv(dest)
            logger.info("saved %s", dest)
            time.sleep(3)


def jibenmian_all() -> None:
    """下载所有 A 股的基本面详细数据（逐股票，较慢）。"""
    for stock_id in all_a_stocks():
        stock_jibenmian(stock_id, 0)


# --------------------------------------------------------------------------
# 基本面：单只股票明细
# --------------------------------------------------------------------------
def stock_jibenmian(symbol: str, delay: int, jbm_type: str | None = None) -> None:
    """下载单只股票的基本面明细。

    参数
    ----
    symbol   : 6 位代码
    delay    : 每个文件下载后的延迟秒数
    jbm_type : None 表示全部种类，否则只下载指定 type

    可用数据源（原代码中被注释，保留备查）::

        ak.stock_balance_sheet_by_report_em(symbol)   # 资产负债表-按报告期
        ak.stock_profit_sheet_by_report_em(symbol)    # 利润表-按报告期
        ak.stock_cash_flow_sheet_by_report_em(symbol) # 现金流量表-按报告期
        ak.stock_financial_analysis_indicator(symbol) # 主要财务指标（新浪）

    落盘：data/a/stock/{subdir}/{type}_{symbol}.csv
    """
    func_list = [
        {"type": "financial_report", "func": ak.stock_financial_analysis_indicator, "platform": "sina"},
    ]

    for item in func_list:
        type_ = item["type"]
        func = item["func"]
        platform = item["platform"]

        if jbm_type is not None and jbm_type != type_:
            continue

        subdir = type_.split("_")[0]
        dest = STOCK_DIR / subdir / f"{type_}_{symbol}.csv"

        if dest.exists():
            logger.info("skip: stock=%s, type=%s", symbol, type_)
            continue

        try:
            df = func(platform_symbol(symbol, platform))
        except Exception:  # TODO(2.2): 收窄异常并重试
            logger.exception("exec error: stock=%s, type=%s", symbol, type_)
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(dest)
        logger.info("write %s", dest)
        if delay > 0:
            time.sleep(delay)


# --------------------------------------------------------------------------
# 行情：日线
# --------------------------------------------------------------------------
def copy_qfq_data(dfqfq: pd.DataFrame, df: pd.DataFrame) -> None:
    """把前复权数据的四个价格列拷贝进未复权表（原地修改 df）。"""
    for column in ["开盘", "收盘", "最高", "最低"]:
        df[f"{column}_qfq"] = dfqfq[column]


def stock_price(symbol: str, down_preyear: bool = False, force: bool = False) -> None:
    """下载单只股票的日线数据（不复权 + 前复权，合并到一张表）。

    落盘：
        data/a/stock/price/price_{symbol}_pre.csv  今年（含）以前的数据
        data/a/stock/price/price_{symbol}_cur.csv  今年的数据

    参数 down_preyear 表示是否下载今年以前的历史数据；force 强制重下当年数据。
    """
    thisyear = int(datetime.datetime.now().strftime("%Y"))
    preyear = thisyear - 1

    file_pre = PRICE_DIR / f"price_{symbol}_pre.csv"
    file_cur = PRICE_DIR / f"price_{symbol}_cur.csv"
    p_symbol = platform_symbol(symbol)

    PRICE_DIR.mkdir(parents=True, exist_ok=True)

    if file_pre.exists():
        logger.info("exec stock_price skip: stock=%s, type=pre", symbol)
    elif down_preyear:
        try:
            end_date = f"{preyear}1231"
            df_pre = ak.stock_zh_a_hist(symbol=p_symbol, period="daily", start_date="20100101", end_date=end_date, adjust="")
            df_pre_qfq = ak.stock_zh_a_hist(symbol=p_symbol, period="daily", start_date="20100101", end_date=end_date, adjust="qfq")
            copy_qfq_data(df_pre_qfq, df_pre)
            df_pre.to_csv(file_pre)
        except Exception:  # TODO(2.2): 收窄异常并重试
            logger.exception("exec stock_price error: stock=%s, type=pre", symbol)
        else:
            logger.info("exec stock_price ok: stock=%s, type=pre", symbol)

    if file_cur.exists() and not force:
        logger.info("exec stock_price skip: stock=%s, type=cur", symbol)
        return

    try:
        start_date = f"{thisyear}0101"
        end_date = datetime.datetime.now().strftime("%Y%m%d")
        df_cur = ak.stock_zh_a_hist(symbol=p_symbol, period="daily", start_date=start_date, end_date=end_date, adjust="")
        df_cur_qfq = ak.stock_zh_a_hist(symbol=p_symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
        copy_qfq_data(df_cur_qfq, df_cur)
        df_cur.to_csv(file_cur)
    except Exception:
        logger.exception("exec stock_price error: stock=%s, type=cur", symbol)
    else:
        logger.info("exec stock_price ok: stock=%s, type=cur", symbol)


def stock_price_all(down_pre: bool = False) -> None:
    """下载全市场日线数据。down_pre=True 时补齐今年以前的历史。"""
    for stock_id in all_a_stocks():
        stock_price(stock_id, down_pre)


# --------------------------------------------------------------------------
# 行情：ETF
# --------------------------------------------------------------------------
def download_etf(start_date: str = "20180101", end_date: str = "20230201", etf_list: Iterable[str] | None = None) -> None:
    """下载 ETF 日线（前复权）。

    落盘：data/a/etf/price/etf_{symbol}.csv
    """
    columns = {
        "开盘": "open", "日期": "date", "收盘": "close", "最高": "high", "最低": "low",
        "成交量": "volumn", "成交额": "turnover", "振幅": "amp",
        "涨跌幅": "percent_change", "涨跌额": "value_change", "换手率": "turnover_rate",
    }

    ETF_PRICE_DIR.mkdir(parents=True, exist_ok=True)
    for symbol in (etf_list if etf_list is not None else ETF_LIST):
        df = ak.fund_etf_hist_em(symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
        df.rename(columns=columns, inplace=True)
        df.to_csv(ETF_PRICE_DIR / f"etf_{symbol}.csv", index=False)
        logger.info("download etf_%s ok", symbol)


__all__ = [
    "platform_symbol",
    "PlatformSymbol",
    "all_a_stocks",
    "latest_jibenmian_file",
    "jibenmian_all_fast",
    "jibenmian_all",
    "stock_jibenmian",
    "stock_price",
    "stock_price_all",
    "copy_qfq_data",
    "download_etf",
]
