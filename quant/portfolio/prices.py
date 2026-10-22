"""资产管理的取价：A股/ETF 走本地行情库，基金净值与汇率走 akshare。

分工
----
- **A股 / 场内 ETF**：直接查本地 quant.db，不联网（已经是全市场数据）。
- **场外基金**：用 akshare 的基金净值接口，把最新净值写回产品的 manual_price。
- **港股 / 美股**：保留接口（当前先做 A 股），取不到就返回 None，界面会标「缺价格」。
- **汇率**：中行牌价的「中行折算价」，单位是 100 外币兑人民币，除以 100 后入库。
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from quant.portfolio import schema, store

logger = logging.getLogger(__name__)

#: akshare 里中行牌价的列名（单位：100 外币）
BOC_COLUMN = "中行折算价"
#: 币种 -> akshare 的 symbol
FX_SYMBOLS = {"USD": "美元", "HKD": "港币"}


# --------------------------------------------------------------------------
# 本地行情库（A股 / ETF）
# --------------------------------------------------------------------------
def _quant_conn():
    """打开行情库；不存在时返回 None。"""
    from quant import config

    if not config.DB_PATH.exists():
        return None
    try:
        from quant.data import store as quant_store

        return quant_store.connect(config.DB_PATH)
    except Exception:  # pragma: no cover - 行情库损坏
        logger.warning("打开行情库失败", exc_info=True)
        return None


def local_latest(kind: str, market: str, symbol: str) -> tuple[float, str] | None:
    """从本地行情库取最新收盘价，返回 (价格, 日期)；取不到返回 None。"""
    if market != schema.MARKET_CN:
        return None
    if kind == schema.KIND_STOCK:
        table, column = "daily_price", "close"
    elif kind == schema.KIND_ETF:
        table, column = "etf_daily", "close_qfq"
    else:
        return None

    conn = _quant_conn()
    if conn is None:
        return None
    try:
        row = conn.execute(
            f"SELECT date, {column} FROM {table} WHERE symbol = ? AND {column} IS NOT NULL "
            f"ORDER BY date DESC LIMIT 1",
            (symbol,),
        ).fetchone()
        if row is None:
            return None
        return float(row[1]), str(row[0])
    except Exception:  # pragma: no cover - 表不存在等
        logger.debug("本地取价失败 %s %s", kind, symbol, exc_info=True)
        return None
    finally:
        conn.close()


def fetch_stock_price(symbol: str, market: str = "CN") -> tuple[float, str] | None:
    """A 股最新收盘价（本地库缺数据时的联网兜底）。"""
    try:
        import akshare as ak

        end = date.today()
        start = end - timedelta(days=30)
        frame = ak.stock_zh_a_hist(
            symbol=symbol, period="daily",
            start_date=start.strftime("%Y%m%d"), end_date=end.strftime("%Y%m%d"), adjust="",
        )
        if frame is None or frame.empty:
            return None
        last = frame.iloc[-1]
        return float(last["收盘"]), str(last["日期"])[:10]
    except Exception:
        logger.warning("联网取 A 股行情失败: %s", symbol, exc_info=True)
        return None


def fetch_etf_price(symbol: str) -> tuple[float, str] | None:
    """场内 ETF 最新收盘价（本地 etf_daily 只覆盖少数几只，其余联网取）。"""
    try:
        import akshare as ak

        end = date.today()
        start = end - timedelta(days=30)
        frame = ak.fund_etf_hist_em(
            symbol=symbol, period="daily",
            start_date=start.strftime("%Y%m%d"), end_date=end.strftime("%Y%m%d"), adjust="",
        )
        if frame is None or frame.empty:
            return None
        last = frame.iloc[-1]
        return float(last["收盘"]), str(last["日期"])[:10]
    except Exception:
        logger.warning("取 ETF 行情失败: %s", symbol, exc_info=True)
        return None


# --------------------------------------------------------------------------
# 场外基金净值
# --------------------------------------------------------------------------
def fetch_fund_nav(symbol: str) -> tuple[float, str] | None:
    """取基金最新单位净值，返回 (净值, 净值日期)。"""
    try:
        import akshare as ak

        frame = ak.fund_open_fund_info_em(symbol=symbol, indicator="单位净值走势")
        if frame is None or frame.empty:
            return None
        frame = frame.dropna(subset=["单位净值"])
        if frame.empty:
            return None
        last = frame.iloc[-1]
        return float(last["单位净值"]), str(last["净值日期"])[:10]
    except Exception:
        logger.warning("取基金净值失败: %s", symbol, exc_info=True)
        return None


# --------------------------------------------------------------------------
# 港股 / 美股（保留接口，暂不启用）
# --------------------------------------------------------------------------
def fetch_hk_price(symbol: str) -> tuple[float, str] | None:
    """港股最新收盘价（新浪源）。当前版本仅保留接口。"""
    try:
        import akshare as ak

        frame = ak.stock_hk_daily(symbol=symbol, adjust="")
        if frame is None or frame.empty:
            return None
        last = frame.iloc[-1]
        return float(last["close"]), str(last["date"])[:10]
    except Exception:
        logger.warning("取港股行情失败: %s", symbol, exc_info=True)
        return None


def fetch_us_price(symbol: str) -> tuple[float, str] | None:
    """美股最新收盘价。symbol 支持 "AAPL" 或东财格式 "105.AAPL"。"""
    try:
        import akshare as ak

        end = date.today()
        start = end - timedelta(days=30)
        frame = ak.stock_us_hist(
            symbol=symbol, period="daily",
            start_date=start.strftime("%Y%m%d"), end_date=end.strftime("%Y%m%d"),
            adjust="",
        )
        if frame is None or frame.empty:
            return None
        last = frame.iloc[-1]
        return float(last["收盘"]), str(last["日期"])[:10]
    except Exception:
        logger.warning("取美股行情失败: %s", symbol, exc_info=True)
        return None


# --------------------------------------------------------------------------
# 汇率
# --------------------------------------------------------------------------
def fetch_fx(currency: str, days: int = 30) -> list[tuple[str, float]]:
    """取最近 days 天的中行折算价，返回 [(日期, 1 外币兑人民币)]。"""
    akshare_symbol = FX_SYMBOLS.get(currency)
    if akshare_symbol is None:
        return []

    try:
        import akshare as ak

        end = date.today()
        start = end - timedelta(days=days)
        frame = ak.currency_boc_sina(
            symbol=akshare_symbol,
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
        )
        if frame is None or frame.empty or BOC_COLUMN not in frame.columns:
            return []

        rows = []
        for row in frame.itertuples(index=False, name=None):
            record = dict(zip(frame.columns, row))
            rate = record.get(BOC_COLUMN)
            day = record.get("日期")
            try:
                value = float(rate)
            except (TypeError, ValueError):
                continue
            if value != value or value <= 0:      # NaN
                continue
            rows.append((str(day)[:10], value / 100.0))
        return rows
    except Exception:
        logger.warning("取汇率失败: %s", currency, exc_info=True)
        return []


def update_fx(conn, currencies: tuple[str, ...] = ("USD", "HKD"), days: int = 30) -> dict:
    """把汇率写入资产库，返回 {币种: 写入天数}。"""
    summary = {}
    for currency in currencies:
        rows = fetch_fx(currency, days=days)
        for rate_date, rate in rows:
            store.upsert_fx(conn, rate_date, currency, rate, source="boc_sina")
        summary[currency] = len(rows)
    return summary


# --------------------------------------------------------------------------
# 批量刷新持仓价格
# --------------------------------------------------------------------------
def refresh_prices(conn, *, include_funds: bool = True, owner_id: int | None = None) -> dict:
    """刷新所有持仓产品的价格，写回产品表。

    返回 {"updated": n, "failed": [...], "skipped": n}
    """
    from quant.portfolio import service

    holdings = store.list_holdings(conn)
    accounts = {a["id"]: a for a in store.list_accounts(conn)}
    if owner_id is not None:
        holdings = [h for h in holdings
                    if accounts.get(h["account_id"], {}).get("owner_id") == owner_id]

    updated, failed, skipped = 0, [], 0
    for row in holdings:
        kind = row["kind"]
        if kind == schema.KIND_CASH:
            skipped += 1
            continue

        result = None
        if kind == schema.KIND_STOCK and row["market"] == schema.MARKET_CN:
            # 本地全市场库优先，缺了再联网
            result = local_latest(kind, row["market"], row["symbol"]) or fetch_stock_price(row["symbol"])
        elif kind == schema.KIND_ETF and row["market"] == schema.MARKET_CN:
            # etf_daily 只覆盖少数几只，绝大多数要联网取
            result = local_latest(kind, row["market"], row["symbol"]) or fetch_etf_price(row["symbol"])
        elif kind == schema.KIND_FUND and include_funds:
            result = fetch_fund_nav(row["symbol"])
        elif kind == schema.KIND_STOCK and row["market"] == schema.MARKET_HK:
            result = fetch_hk_price(row["symbol"])
        elif kind == schema.KIND_STOCK and row["market"] == schema.MARKET_US:
            result = fetch_us_price(row["symbol"])

        if result is None:
            failed.append(f"{row['symbol']}（{schema.KIND_NAMES.get(kind, kind)}）")
            continue

        price, price_date = result
        store.update_instrument(conn, row["instrument_id"],
                                manual_price=float(price), price_date=price_date)
        updated += 1

    return {"updated": updated, "failed": failed, "skipped": skipped}


def price_map(conn) -> dict:
    """把产品表里已保存的价格整理成 positions() 需要的覆盖表。"""
    result = {}
    for row in store.list_instruments(conn):
        if row["manual_price"] is None:
            continue
        result[(row["kind"], row["market"], row["symbol"])] = (
            float(row["manual_price"]), row["price_date"],
        )
    return result
