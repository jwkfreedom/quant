"""美股数据采集（akshare / yfinance）。

由原 utils/download_us.py 迁移：
    - 删除模块级的 get_financial_data('MSFT') 调用（原实现 import 即联网）
    - 修正 get_financial_data 忽略入参、硬编码 'MSFT' 的问题
    - 输出路径统一走 DATA_DIR

TODO(2.3): 美股支持按项目决策重新设计（标的池、复权、落盘格式、增量更新）。
"""

from __future__ import annotations

import logging

import akshare as ak
import pandas as pd
import yfinance as yf

from quant.config import DATA_DIR
from quant.data.universe import US_FAMOUS_TYPES

logger = logging.getLogger(__name__)

US_DIR = DATA_DIR / "us"


def good_stocks(out_file=None) -> pd.DataFrame:
    """下载 ak 的「知名美股」清单并落盘。

    落盘：data/us/good_stocks.csv
    """
    frames = []
    for type_ in US_FAMOUS_TYPES:
        frames.append(ak.stock_us_famous_spot_em(symbol=type_))

    df_total = pd.concat(frames, ignore_index=False)
    dest = out_file or (US_DIR / "good_stocks.csv")
    dest.parent.mkdir(parents=True, exist_ok=True)
    df_total.to_csv(dest)
    logger.info("saved %s (%d rows)", dest, len(df_total))
    return df_total


def get_financial_data(symbol: str):
    """用 yfinance 读取单只美股的基本信息。

    TODO(2.3): 目前只打印 info，需要扩展为资产负债表/利润表/现金流的结构化读取。
    """
    ticker = yf.Ticker(symbol)
    logger.info("yfinance info for %s", symbol)
    print(ticker.info)
    return ticker.info
