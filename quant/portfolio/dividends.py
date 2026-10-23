"""分红：自动拉取、手动登记、按年统计、手动记入现金。

口径（与作者确认）
------------------
1. 金额 = 除权除息日的每股分红 × **当天持股数量**；持股数量按交易流水重建，
   期初导入（adjust）的持仓以导入日为起点，导入之前的分红不计。
2. 按**除息日**归属年度，**税前**金额，不扣红利税。
3. 分红不自动变成现金，需要手动「记入现金」。
4. 送股/转增只统计比例用于提示，不自动改持仓数量。
5. 美股无自动数据源，只能手动登记。
"""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta

import pandas as pd

from quant.portfolio import schema, store

logger = logging.getLogger(__name__)

#: A股分红比例的单位是「每 10 股」
A_SHARE_LOT = 10.0

#: 港股分红文本里提取金额，例如「每股派港币5.3元」
_HK_AMOUNT = re.compile(r"派[^\d]{0,6}([0-9]+(?:\.[0-9]+)?)")


def _num(value, default: float = 0.0) -> float:
    """把可能为 None/NaN/字符串的值转成 float。

    注意 NaN 在 Python 里是真值，直接写 value or 0 会漏掉它，
    而 NaN 写进 SQLite 会变成 NULL，触发 NOT NULL 约束。
    """
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if result != result:      # NaN
        return default
    return result


# --------------------------------------------------------------------------
# 自动拉取
# --------------------------------------------------------------------------
def fetch_stock_dividends(symbol: str) -> list[dict]:
    """A股个股分红（东财）。返回每 1 股对应的现金/送转。"""
    try:
        import akshare as ak

        frame = ak.stock_fhps_detail_em(symbol=symbol)
    except Exception:
        logger.warning("取 A 股分红失败: %s", symbol, exc_info=True)
        return []

    if frame is None or frame.empty:
        return []

    records = []
    for row in frame.to_dict("records"):
        ex_date = row.get("除权除息日")
        if not ex_date or str(ex_date) in ("NaT", "nan", "None"):
            continue
        progress = str(row.get("方案进度", ""))
        if progress and "实施" not in progress:
            continue

        cash_per_share = _num(row.get("现金分红-现金分红比例")) / A_SHARE_LOT
        stock_per_share = _num(row.get("送转股份-送转总比例")) / A_SHARE_LOT
        if cash_per_share <= 0 and stock_per_share <= 0:
            continue

        records.append({
            "ex_date": str(ex_date)[:10],
            "pay_date": None,
            "cash_per_share": round(cash_per_share, 6),
            "stock_per_share": round(stock_per_share, 6),
            "note": str(row.get("现金分红-现金分红比例描述") or "")[:80],
        })
    return records


def fetch_fund_dividends(symbols) -> dict[str, list[dict]]:
    """场内 ETF / 场外基金分红（东财一次拉全量，再按代码筛）。"""
    wanted = {str(s) for s in symbols}
    if not wanted:
        return {}
    try:
        import akshare as ak

        frame = ak.fund_fh_em()
    except Exception:
        logger.warning("取基金分红失败", exc_info=True)
        return {}
    if frame is None or frame.empty:
        return {}

    grouped: dict[str, list[dict]] = {}
    for row in frame.to_dict("records"):
        code = str(row.get("基金代码", "")).strip()
        if code not in wanted:
            continue
        ex_date = row.get("除息日期")
        if not ex_date or str(ex_date) in ("NaT", "nan", "None"):
            continue
        cash_per_share = _num(row.get("分红"))
        if cash_per_share <= 0:
            continue
        grouped.setdefault(code, []).append({
            "ex_date": str(ex_date)[:10],
            "pay_date": str(row.get("分红发放日"))[:10] if row.get("分红发放日") else None,
            "cash_per_share": round(cash_per_share, 6),
            "stock_per_share": 0.0,
            "note": str(row.get("基金简称", ""))[:80],
        })
    return grouped


def fetch_hk_dividends(symbol: str) -> list[dict]:
    """港股分红（东财，文本方案需解析）。当前版本仅保留接口。"""
    try:
        import akshare as ak

        frame = ak.stock_hk_dividend_payout_em(symbol=symbol)
    except Exception:
        logger.warning("取港股分红失败: %s", symbol, exc_info=True)
        return []
    if frame is None or frame.empty:
        return []

    records = []
    for row in frame.to_dict("records"):
        ex_date = row.get("除净日")
        if not ex_date or str(ex_date) in ("NaT", "nan", "None"):
            continue
        plan = str(row.get("分红方案", ""))
        match = _HK_AMOUNT.search(plan)
        if not match:
            continue
        records.append({
            "ex_date": str(ex_date)[:10],
            "pay_date": str(row.get("发放日"))[:10] if row.get("发放日") else None,
            "cash_per_share": round(_num(match.group(1)), 6),
            "stock_per_share": 0.0,
            "note": plan[:80],
        })
    return records


def refresh_dividends(conn, *, include_funds: bool = True) -> dict:
    """刷新所有持仓产品的分红记录（幂等，按除息日去重）。"""
    holdings = store.list_holdings(conn)
    instruments = {}
    for row in holdings:
        if row["kind"] == schema.KIND_CASH:
            continue
        instruments[row["instrument_id"]] = row

    fund_symbols = [row["symbol"] for row in instruments.values()
                    if row["kind"] in (schema.KIND_ETF, schema.KIND_FUND)
                    and row["market"] == schema.MARKET_CN]
    fund_map = fetch_fund_dividends(fund_symbols) if (include_funds and fund_symbols) else {}

    saved, failed = 0, []
    for row in instruments.values():
        kind, market, symbol = row["kind"], row["market"], row["symbol"]
        if kind == schema.KIND_STOCK and market == schema.MARKET_CN:
            records = fetch_stock_dividends(symbol)
        elif kind in (schema.KIND_ETF, schema.KIND_FUND) and market == schema.MARKET_CN:
            records = fund_map.get(symbol, [])
        elif kind == schema.KIND_STOCK and market == schema.MARKET_HK:
            records = fetch_hk_dividends(symbol)
        else:
            failed.append(f"{symbol}（{schema.KIND_NAMES.get(kind, kind)}，暂无自动源）")
            continue

        if not records:
            failed.append(f"{symbol}（没有取到分红记录）")
            continue
        for record in records:
            store.upsert_dividend(
                conn, row["instrument_id"],
                ex_date=record["ex_date"], pay_date=record.get("pay_date"),
                cash_per_share=record["cash_per_share"],
                stock_per_share=record.get("stock_per_share", 0.0),
                currency=row["currency"],
                source=schema.DIVIDEND_SOURCE_AUTO,
                note=record.get("note", ""),
            )
            saved += 1
    return {"saved": saved, "failed": failed}


def add_manual_dividend(conn, instrument_id: int, *, ex_date: str, cash_per_share: float,
                        pay_date: str | None = None, currency: str = "CNY",
                        stock_per_share: float = 0.0, note: str = "") -> int:
    """手动登记一笔分红（美股或数据源缺漏时用）。"""
    if cash_per_share < 0:
        raise ValueError("每股分红不能为负")
    return store.upsert_dividend(
        conn, instrument_id, ex_date=ex_date, pay_date=pay_date,
        cash_per_share=cash_per_share, stock_per_share=stock_per_share,
        currency=currency, source=schema.DIVIDEND_SOURCE_MANUAL, note=note,
    )


# --------------------------------------------------------------------------
# 统计
# --------------------------------------------------------------------------
def _quantity_at(conn, account_id: int, instrument_id: int, as_of: str) -> float:
    """按流水重建某日收盘后的持仓数量。"""
    rows = conn.execute(
        f"SELECT action, quantity FROM {schema.TABLE_TXN} "
        f"WHERE account_id = ? AND instrument_id = ? AND trade_date <= ? "
        f"ORDER BY trade_date, id",
        (account_id, instrument_id, as_of),
    ).fetchall()
    total = 0.0
    for row in rows:
        if row["action"] in (schema.ACTION_BUY, schema.ACTION_ADJUST):
            total += row["quantity"]
        elif row["action"] == schema.ACTION_SELL:
            total -= row["quantity"]
    return round(max(total, 0.0), 6)


def dividend_report(conn, *, account_id: int | None = None, year: int | None = None,
                    start: str | None = None, end: str | None = None,
                    as_of: str | None = None) -> pd.DataFrame:
    """逐笔分红明细：按「除息日持股数 × 每股分红」计算金额。

    只统计**该账户在除息日确实持有**的产品。
    """
    from quant.portfolio.service import Portfolio

    book = Portfolio(conn)

    if year is not None:
        start, end = f"{year}-01-01", f"{year}-12-31"
    dividends = store.list_dividends(conn, start=start, end=end)

    accounts = {a["id"]: a for a in store.list_accounts(conn)}
    owners = {o["id"]: o for o in store.list_owners(conn)}

    # 每个产品被哪些账户持有（包括已清仓但历史上持有过的）
    holders: dict[int, set[int]] = {}
    for row in conn.execute(
        f"SELECT DISTINCT account_id, instrument_id FROM {schema.TABLE_TXN}"
    ).fetchall():
        holders.setdefault(row["instrument_id"], set()).add(row["account_id"])

    records = []
    for dividend in dividends:
        instrument_id = dividend["instrument_id"]
        cash_per_share = float(dividend["cash_per_share"] or 0)
        if cash_per_share <= 0:
            continue
        for holder in sorted(holders.get(instrument_id, set())):
            if account_id is not None and holder != account_id:
                continue
            quantity = _quantity_at(conn, holder, instrument_id, dividend["ex_date"])
            if quantity <= 0:
                continue
            amount = round(quantity * cash_per_share, 2)
            account = accounts.get(holder, {})
            owner = owners.get(account.get("owner_id"), {})
            currency = dividend["currency"] or account.get("currency", "CNY")
            records.append({
                "id": dividend["id"],
                "account_id": holder,
                "account": account.get("name", ""),
                "owner": owner.get("name", ""),
                "symbol": dividend["symbol"],
                "name": dividend["name"],
                "kind": dividend["kind"],
                "ex_date": dividend["ex_date"],
                "pay_date": dividend["pay_date"],
                "cash_per_share": cash_per_share,
                "stock_per_share": float(dividend["stock_per_share"] or 0),
                "quantity": quantity,
                "amount": amount,
                "currency": currency,
                "amount_base": round(book.to_base(amount, currency, as_of), 2),
                "recorded": bool(dividend["recorded"]),
                "source": dividend["source"],
                "note": dividend["note"],
            })
    frame = pd.DataFrame(records)
    if not frame.empty:
        frame = frame.sort_values(["ex_date", "account"], ascending=[False, True])
    return frame


def dividend_summary(conn, *, account_id: int | None = None, year: int | None = None,
                     start: str | None = None, end: str | None = None) -> dict:
    """分红汇总：总数、按账户、按币种、按产品。"""
    frame = dividend_report(conn, account_id=account_id, year=year, start=start, end=end)
    if frame.empty:
        return {"count": 0, "total": 0.0, "total_base": 0.0,
                "by_account": {}, "by_currency": {}, "by_symbol": {}, "year": year}

    by_account = (frame.groupby("account")["amount_base"].sum()
                  .round(2).sort_values(ascending=False).to_dict())
    by_currency = frame.groupby("currency")["amount"].sum().round(2).to_dict()
    by_symbol = (frame.groupby("symbol")["amount_base"].sum()
                 .round(2).sort_values(ascending=False).to_dict())

    return {
        "count": int(len(frame)),
        "total": round(float(frame["amount_base"].sum()), 2),
        "total_base": round(float(frame["amount_base"].sum()), 2),
        "by_account": by_account,
        "by_currency": by_currency,
        "by_symbol": by_symbol,
        "year": year,
    }




# --------------------------------------------------------------------------
# 年度分红预期（按当前持仓估算）
# --------------------------------------------------------------------------
def _window(year: int | None, months: int | None, as_of: str | None) -> tuple[str, str]:
    """把「年份」或「最近 N 个月」折算成 [start, end] 区间。"""
    if year is not None:
        return f"{year}-01-01", f"{year}-12-31"

    end_date = date.fromisoformat(as_of) if as_of else date.today()
    span = months if months and months > 0 else 12
    start_date = end_date - timedelta(days=int(round(365 * span / 12)))
    return start_date.isoformat(), end_date.isoformat()


def dividend_forecast(conn, *, account_id: int | None = None,
                      owner_id: int | None = None, year: int | None = None,
                      months: int | None = 12, as_of: str | None = None) -> tuple:
    """按当前持仓估算一年的分红。

    口径：取窗口内（默认最近 12 个月）该产品的**每单位现金分红合计**，
    乘以**当前持股数量**。这是「照最近一年的分红水平，未来一年大概能收多少」的估算，
    不是承诺——公司少分红、减仓、清仓都会让实际金额变化。

    返回 (明细 DataFrame, 汇总 dict)。
    """
    from quant.portfolio import prices as portfolio_prices
    from quant.portfolio.service import Portfolio

    book = Portfolio(conn)
    # 用本地行情库的最新价，股息率才不是空的
    frame = book.positions(account_id=account_id, owner_id=owner_id,
                           prices=portfolio_prices.resolve_price_map(conn))

    start, end = _window(year, months, as_of)
    scope = f"{year} 年度" if year is not None else f"{start} ~ {end}"

    columns = ["account", "symbol", "name", "kind", "risk", "quantity", "currency",
               "cash_per_share", "last_ex_date", "forecast_amount", "forecast_base",
               "market_value", "yield_pct", "note"]
    if frame.empty:
        return (pd.DataFrame(columns=columns),
                {"scope": scope, "count": 0, "total_base": 0.0, "market_value": 0.0,
                 "yield_pct": 0.0, "with_dividend": 0, "missing_price": 0})

    # 一次取出窗口内所有分红记录，按产品汇总每单位分红
    records = store.list_dividends(conn, start=start, end=end)
    per_unit: dict[int, float] = {}
    last_ex: dict[int, str] = {}
    for record in records:
        instrument_id = record["instrument_id"]
        cash = float(record["cash_per_share"] or 0)
        if cash <= 0:
            continue
        per_unit[instrument_id] = per_unit.get(instrument_id, 0.0) + cash
        ex_date = record["ex_date"]
        if ex_date and ex_date > last_ex.get(instrument_id, ""):
            last_ex[instrument_id] = ex_date

    rows = []
    total_base = 0.0
    total_value = 0.0
    with_dividend = 0
    missing_price = 0

    for row in frame.itertuples():
        if row.kind == schema.KIND_CASH:
            continue                     # 现金不产生分红

        instrument_id = getattr(row, "instrument_id", None)
        cash_per_share = per_unit.get(instrument_id, 0.0)
        quantity = float(row.quantity)
        amount = round(quantity * cash_per_share, 2)
        amount_base = round(book.to_base(amount, row.currency, as_of), 2)

        has_price = row.market_value is not None and not pd.isna(row.market_value)
        market_value = float(row.market_value) if has_price else None
        if not has_price:
            missing_price += 1

        if cash_per_share > 0:
            with_dividend += 1
            note = ""
        else:
            note = "窗口内没有分红"

        total_base += amount_base
        if market_value:
            total_value += book.to_base(market_value, row.currency, as_of)

        rows.append({
            "account": row.account,
            "symbol": row.symbol,
            "name": row.name,
            "kind": row.kind,
            "risk": row.risk,
            "quantity": quantity,
            "currency": row.currency,
            "cash_per_share": round(cash_per_share, 6),
            "last_ex_date": last_ex.get(instrument_id, ""),
            "forecast_amount": amount,
            "forecast_base": amount_base,
            "market_value": market_value,
            "yield_pct": (round(amount / market_value * 100, 2)
                          if market_value else None),
            "note": note,
        })

    detail = pd.DataFrame(rows, columns=columns)
    if not detail.empty:
        detail = detail.sort_values("forecast_base", ascending=False)

    summary = {
        "scope": scope,
        "start": start,
        "end": end,
        "count": int(len(detail)),
        "with_dividend": with_dividend,
        "missing_price": missing_price,
        "total_base": round(total_base, 2),
        "market_value": round(total_value, 2),
        "yield_pct": round(total_base / total_value * 100, 2) if total_value else 0.0,
    }
    return detail, summary


def record_as_cash(conn, dividend_id: int, account_id: int, *,
                   trade_date: str | None = None) -> float:
    """把某笔分红记入指定账户的现金，并标记为已入账。"""
    from quant.portfolio.service import Portfolio

    dividend = conn.execute(
        f"SELECT * FROM {schema.TABLE_DIVIDEND} WHERE id = ?", (dividend_id,)
    ).fetchone()
    if dividend is None:
        raise ValueError(f"分红记录不存在: {dividend_id}")

    quantity = _quantity_at(conn, account_id, dividend["instrument_id"], dividend["ex_date"])
    if quantity <= 0:
        raise ValueError("该账户在除息日没有持仓，无法记入这笔分红")

    amount = round(quantity * float(dividend["cash_per_share"] or 0), 2)
    if amount <= 0:
        raise ValueError("这笔分红金额为 0")

    instrument = store.get_instrument(conn, dividend["instrument_id"]) or {}
    symbol = instrument.get("symbol", "")
    book = Portfolio(conn)
    balance = book.record_dividend(
        account_id, amount, trade_date=trade_date or dividend["ex_date"],
        note=f"分红 {symbol} {dividend['ex_date']}",
    )
    store.mark_dividend_recorded(conn, dividend_id, True)
    return balance
