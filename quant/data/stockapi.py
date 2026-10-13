"""外部行情接口封装（HTTP 直连）。

由原 utils/stockapi.py 迁移：
    - 删除 IEX 相关实现（含源码中的明文 API Key），按项目决策不再使用 IEX
    - 删除模块级的 print(iex_stocks(...)) 调用（原实现 import 本模块即发网络请求）
    - 统一使用 requests 并加超时
"""

from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

#_-----------------------------------------------------------------------
# 雪球
#_-----------------------------------------------------------------------
SNOWBALL_STOCK_URL = "https://stock.xueqiu.com/v5/stock/realtime/quotec.json?symbol={}"

SNOWBALL_HEADERS = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
    "Connection": "keep-alive",
    "host": "stock.xueqiu.com",
    "Referer": "https://stock.xueqiu.com/",
    "User-agent": (
        "Mozilla/5.0 (Windows NT 10.0; WOW 64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36 QIHU 360SE"
    ),
}

#_-----------------------------------------------------------------------
# 东方财富
#_-----------------------------------------------------------------------
EASTMONEY_CLIST_URL = "http://18.push2.eastmoney.com/api/qt/clist/get"

EASTMONEY_CLIST_PARAMS = {
    "pn": "1",
    "pz": "3000",
    "po": "1",
    "np": "1",
    "ut": "bd1d9ddb04089700cf9c27f6f7426281",
    "fltt": "2",
    "invt": "2",
    "fid": "f3",
    "fs": "m:1+t:2,m:1+t:23",
    "fields": (
        "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,f23,"
        "f24,f25,f26,f38,f39,f22,f11,f62,f128,f136,f115,f152,f297"
    ),
}


def _get_json(url: str, params: dict | None = None, headers: dict | None = None, timeout: int = 15):
    """发 GET 请求并返回 JSON；失败时返回 {'err': <状态码或异常名>}。"""
    try:
        response = requests.get(url, params=params, headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        logger.error("request failed: %s", exc)
        return {"err": type(exc).__name__}

    if response.status_code != 200:
        logger.error("Error: %s", response.status_code)
        return {"err": response.status_code}

    return response.json()


def stock_info(symbol: str):
    """雪球实时报价。symbol 形如 'SH600519' / 'SZ000001'。"""
    return _get_json(SNOWBALL_STOCK_URL.format(symbol), headers=SNOWBALL_HEADERS)


def eastmoney_stock():
    """东方财富沪深 A 股列表（按涨跌幅排序）。"""
    return _get_json(EASTMONEY_CLIST_URL, params=EASTMONEY_CLIST_PARAMS)
