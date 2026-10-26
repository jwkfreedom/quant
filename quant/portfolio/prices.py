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


def is_fund_like(kind: str, symbol: str, market: str = "CN") -> bool:
    """判断该产品是否该按「基金」处理（而不是只信 kind 字段）。

    录入时把 LOF / 封闭基金错选成「股票」很常见，所以除了 kind，
    再看代码段：6 位数字且以 1（深市 LOF/ETF）或 5（沪市 ETF/LOF）开头，
    一律当基金处理。
    """
    if market != schema.MARKET_CN:
        return False
    if kind in (schema.KIND_FUND, schema.KIND_ETF):
        return True
    code = str(symbol)
    return len(code) == 6 and code.isdigit() and code[0] in ("1", "5")


def fetch_fund_price(kind: str, symbol: str) -> tuple[float, str, str] | None:
    """取基金价格：主源按 kind 选，失败自动换另一个源。

    返回 (价格, 日期, 来源说明)，来源会用「净值」/「场内价」显示在进度里。
    """
    prefer_nav = kind == schema.KIND_FUND
    order = ("nav", "market") if prefer_nav else ("market", "nav")

    for source in order:
        if source == "nav":
            got = fetch_fund_nav(symbol)
            if got is not None:
                return got[0], got[1], "净值"
        else:
            got = fetch_etf_price(symbol)
            if got is not None:
                return got[0], got[1], "场内价"
    return None


def etf_sina_symbol(symbol: str) -> str:
    """把 6 位 ETF 代码转成新浪格式（沪市加 sh、深市加 sz）。"""
    code = str(symbol).zfill(6)
    if code.startswith(("50", "51", "52", "56", "58")):
        return f"sh{code}"
    return f"sz{code}"


def fetch_etf_price(symbol: str) -> tuple[float, str] | None:
    """场内 ETF 最新收盘价。

    东财的 fund_etf_hist_em 近期经常断连，所以先用新浪（一次全历史，取最后一根），
    失败再退回东财。
    """
    code = str(symbol).zfill(6)
    try:
        import akshare as ak

        frame = ak.fund_etf_hist_sina(symbol=etf_sina_symbol(code))
        if frame is not None and not frame.empty:
            frame = frame.dropna(subset=["close"])
            if not frame.empty:
                last = frame.iloc[-1]
                return float(last["close"]), str(last["date"])[:10]
    except Exception:
        logger.debug("新浪取 ETF 失败: %s", code, exc_info=True)

    try:
        import akshare as ak

        end = date.today()
        start = end - timedelta(days=30)
        frame = ak.fund_etf_hist_em(
            symbol=code, period="daily",
            start_date=start.strftime("%Y%m%d"), end_date=end.strftime("%Y%m%d"), adjust="",
        )
        if frame is None or frame.empty:
            return None
        last = frame.iloc[-1]
        return float(last["收盘"]), str(last["日期"])[:10]
    except Exception:
        logger.warning("取 ETF 行情失败: %s", code, exc_info=True)
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
# 渲染时取价（不联网）
# --------------------------------------------------------------------------
def resolve_price_map(conn, holdings=None) -> dict:
    """给持仓估值用的价格表：(kind, market, symbol) -> (价格, 日期)。

    两个来源二选一，**按日期取更新的那个**：
      1. 本地行情库的最新收盘价（A股 / 场内 ETF，不联网）
      2. 产品上保存的上次刷新价（场外基金净值、联网拉到的 ETF 价）

    之前固定「本地优先」，会出现刚拉完基金净值、市值却还用着半年
    前本地旧价的情况，所以这里改成比日期。
    都取不到就不放进表里，界面显示「缺价格」。
    """
    if holdings is None:
        holdings = store.list_holdings(conn)

    result: dict = {}
    for row in holdings:
        key = (row["kind"], row["market"], row["symbol"])
        if key in result:
            continue

        if row["kind"] == schema.KIND_CASH:
            result[key] = (1.0, None)
            continue

        latest = local_latest(row["kind"], row["market"], row["symbol"])
        saved = ((float(row["manual_price"]), row["price_date"])
                 if row["manual_price"] is not None else None)

        if latest and saved:
            # 日期都是 YYYY-MM-DD 字符串，可直接比较；空的当最旧
            result[key] = latest if (latest[1] or "") >= (saved[1] or "") else saved
        elif latest:
            result[key] = latest
        elif saved:
            result[key] = saved
    return result



# --------------------------------------------------------------------------
# 只刷新持有中的基金（场外基金 + 场内 ETF）
# --------------------------------------------------------------------------
#: 金融产品的类型集合（用于「只更新基金」）
FUND_KINDS = (schema.KIND_FUND, schema.KIND_ETF)


def refresh_fund_prices(conn, *, include_etf: bool = True,
                        progress=None) -> dict:
    """只拉**持仓里持有**的基金价格，不碰全市场。

    - 场外基金：akshare 的 fund_open_fund_info_em，逐只拉最新净值
    - 场内 ETF / LOF / 封闭基金：新浪 fund_etf_hist_sina，逐只拉最新收盘价
    - **判定不只看 kind**：6 位数字且以 1 或 5 开头的代码一律当基金处理，
      因为录入时把 LOF 错选成「股票」很常见
    - 主源失败自动换另一个源（净值 ↔ 场内价）
    - 同一只基金被多个账户持有时只拉一次

    progress: 可选 progress(已完成, 总数, 说明)
    返回 {"updated", "failed", "skipped", "total"}
    """
    holdings = store.list_holdings(conn)

    def wanted(row: dict) -> bool:
        if not is_fund_like(row["kind"], row["symbol"], row["market"]):
            return False
        # 只刷场外基金时，场内可交易的（ETF/LOF/代码 1、5 开头）仍跳过
        if not include_etf and not row["kind"] == schema.KIND_FUND:
            return False
        return True

    unique: dict[int, dict] = {}
    for row in holdings:
        if wanted(row):
            unique.setdefault(row["instrument_id"], row)

    targets = list(unique.values())
    skipped = len(holdings) - len(targets)
    total = len(targets)

    if callable(progress):
        progress(0, total, "准备刷新基金净值…" if total else "没有持有中的基金")

    updated, failed = 0, []
    for index, row in enumerate(targets, start=1):
        kind = row["kind"]
        label = f"{row['symbol']} {row['name'] or ''}".strip()

        # 本地行情库有就用本地的（快且不联网），否则按基金多源兜底
        local = local_latest(kind, row["market"], row["symbol"])
        if local is not None:
            price, price_date = local
            source = "本地行情"
        else:
            got = fetch_fund_price(kind, row["symbol"])
            if got is None:
                failed.append(label)
                if callable(progress):
                    progress(index, total, f"{label}（取不到）")
                continue
            price, price_date, source = got

        if callable(progress):
            progress(index, total, f"{label}（{source} {price_date}）")

        store.update_instrument(conn, row["instrument_id"],
                                manual_price=float(price), price_date=price_date)
        updated += 1

    return {"updated": updated, "failed": failed, "skipped": skipped, "total": total}


# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# 批量刷新持仓价格
# --------------------------------------------------------------------------
def refresh_prices(conn, *, include_funds: bool = True, owner_id: int | None = None,
                   progress=None) -> dict:
    """刷新所有持仓产品的价格，写回产品表。

    progress: 可选回调 progress(已完成, 总数, 说明文字)，用来显示进度。
    返回 {"updated": n, "failed": [...], "skipped": n, "total": n}
    """
    holdings = store.list_holdings(conn)
    accounts = {a["id"]: a for a in store.list_accounts(conn)}
    if owner_id is not None:
        holdings = [h for h in holdings
                    if accounts.get(h["account_id"], {}).get("owner_id") == owner_id]

    # 同一只产品可能被多个账户持有，按产品去重，避免重复联网
    unique: dict[int, dict] = {}
    for row in holdings:
        unique.setdefault(row["instrument_id"], row)

    targets = [row for row in unique.values() if row["kind"] != schema.KIND_CASH]
    skipped = len(unique) - len(targets)
    total = len(targets)

    updated, failed = 0, []
    for index, row in enumerate(targets, start=1):
        if callable(progress):
            label = row["name"] or row["symbol"]
            progress(index, total, f"{row['symbol']} {label}".strip())

        kind = row["kind"]
        result = None
        if is_fund_like(kind, row["symbol"], row["market"]) and include_funds:
            # 基金类（含被误录成股票的 LOF/封闭基金）：本地库优先，缺了多源兜底
            local = local_latest(kind, row["market"], row["symbol"])
            if local is not None:
                result = local
            else:
                got = fetch_fund_price(kind, row["symbol"])
                result = (got[0], got[1]) if got else None
        elif kind == schema.KIND_STOCK and row["market"] == schema.MARKET_CN:
            # 本地全市场库优先，缺了再联网
            result = local_latest(kind, row["market"], row["symbol"]) or fetch_stock_price(row["symbol"])
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

    return {"updated": updated, "failed": failed, "skipped": skipped, "total": total}


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
