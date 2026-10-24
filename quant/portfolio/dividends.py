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
import time
from datetime import date, timedelta

import pandas as pd

from quant.portfolio import schema, store

logger = logging.getLogger(__name__)

#: A股分红比例的单位是「每 10 股」
A_SHARE_LOT = 10.0

#: 港股分红文本里提取金额，例如「每股派港币5.3元」
_HK_AMOUNT = re.compile(r"派[^\d]{0,6}([0-9]+(?:\.[0-9]+)?)")

#: 东财接口偶尔会超时/返回空页，重试次数与退避秒数
FETCH_ATTEMPTS = 3
FETCH_RETRY_DELAY = 0.5


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


def _fetch_frame(func, *, attempts: int = FETCH_ATTEMPTS, **kwargs):
    """调用联网接口，失败时短暂重试，返回 (DataFrame, 最后一次异常)。"""
    last_error = None
    for attempt in range(max(1, attempts)):
        try:
            return func(**kwargs), None
        except Exception as exc:      # noqa: BLE001 - 需要把异常带回调用方
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(FETCH_RETRY_DELAY * (attempt + 1))
    return None, last_error


def _is_cn_fund_code(symbol: str) -> bool:
    """按代码前缀判断是不是场内 ETF / 基金（有些会被误录成 stock）。"""
    return str(symbol).startswith(("15", "16", "18", "50", "51", "56", "58"))


def _record_error(errors: list[str] | None, error: Exception) -> None:
    if errors is not None:
        errors.append(f"{type(error).__name__}: {error}")


def _date_text(value) -> str | None:
    """把日期列转成 YYYY-MM-DD；空值/NaT 返回 None。"""
    text = str(value)[:10]
    if not text or text in ("NaT", "nan", "None"):
        return None
    return text


def _cninfo_report_period(value) -> str | None:
    """把巨潮的「2025半年报 / 2025年报」转成报告期日期。"""
    text = str(value or "")
    match = re.search(r"(\d{4})", text)
    if not match:
        return None
    year = int(match.group(1))
    if "一季" in text:
        return f"{year}-03-31"
    if "半年" in text or "中报" in text:
        return f"{year}-06-30"
    if "三季" in text:
        return f"{year}-09-30"
    if "年报" in text:
        return f"{year}-12-31"
    return None


# --------------------------------------------------------------------------
# 自动拉取
# --------------------------------------------------------------------------
def _parse_stock_em_frame(frame) -> list[dict]:
    """把东财 stock_fhps_detail_em 的结果解析成每 1 股的现金/送转。"""
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
            "report_period": _date_text(row.get("报告期")),
            "cash_per_share": round(cash_per_share, 6),
            "stock_per_share": round(stock_per_share, 6),
            "note": str(row.get("现金分红-现金分红比例描述") or "")[:80],
        })
    return records


def fetch_stock_dividends_cninfo(symbol: str, *, errors: list[str] | None = None,
                                 attempts: int = FETCH_ATTEMPTS) -> list[dict]:
    """A股个股分红（巨潮资讯，东财失败时的兜底源）。"""
    try:
        import akshare as ak
    except Exception as exc:      # pragma: no cover - 依赖缺失
        logger.warning("导入 akshare 失败", exc_info=True)
        _record_error(errors, exc)
        return []

    frame, error = _fetch_frame(ak.stock_dividend_cninfo, attempts=attempts, symbol=symbol)
    if error is not None:
        logger.warning("取 A 股分红失败（巨潮）: %s", symbol,
                       exc_info=(type(error), error, error.__traceback__))
        _record_error(errors, error)
        return []
    if frame is None or frame.empty:
        return []

    records = []
    for row in frame.to_dict("records"):
        ex_date = row.get("除权日")
        if not ex_date or str(ex_date) in ("NaT", "nan", "None"):
            continue
        cash_per_share = _num(row.get("派息比例")) / A_SHARE_LOT
        stock_per_share = (_num(row.get("送股比例")) + _num(row.get("转增比例"))) / A_SHARE_LOT
        if cash_per_share <= 0 and stock_per_share <= 0:
            continue
        pay_date = row.get("派息日")
        records.append({
            "ex_date": str(ex_date)[:10],
            "pay_date": str(pay_date)[:10] if pay_date and str(pay_date) != "NaT" else None,
            "report_period": _cninfo_report_period(row.get("报告时间")),
            "cash_per_share": round(cash_per_share, 6),
            "stock_per_share": round(stock_per_share, 6),
            "note": str(row.get("实施方案分红说明") or "")[:80],
        })
    return records


def fetch_stock_dividends(symbol: str, *, errors: list[str] | None = None,
                          attempts: int = FETCH_ATTEMPTS) -> list[dict]:
    """A股个股分红。优先东财，失败或没数据时用巨潮资讯兜底。"""
    try:
        import akshare as ak
    except Exception as exc:      # pragma: no cover - 依赖缺失
        logger.warning("导入 akshare 失败", exc_info=True)
        _record_error(errors, exc)
        return []

    frame, error = _fetch_frame(ak.stock_fhps_detail_em, attempts=attempts, symbol=symbol)
    records = _parse_stock_em_frame(frame)
    if records:
        return records

    # 东财偶发超时/空页时换巨潮再试一次，避免「明明有分红却提示没取到」
    fallback_errors: list[str] = []
    fallback = fetch_stock_dividends_cninfo(symbol, errors=fallback_errors,
                                           attempts=attempts)
    if fallback:
        return fallback

    if error is not None:
        logger.warning("取 A 股分红失败: %s", symbol,
                       exc_info=(type(error), error, error.__traceback__))
        _record_error(errors, error)
        if errors is not None:
            errors.extend(fallback_errors)
    # 东财返回了空表（没有分红）时，巨潮失败不影响结论：就是没有分红记录
    return []


def fetch_fund_dividends(symbols, *, errors: list[str] | None = None,
                         attempts: int = FETCH_ATTEMPTS) -> dict[str, list[dict]]:
    """场内 ETF / 场外基金分红（东财一次拉全量，再按代码筛）。"""
    wanted = {str(s) for s in symbols}
    if not wanted:
        return {}
    try:
        import akshare as ak
    except Exception as exc:      # pragma: no cover - 依赖缺失
        logger.warning("导入 akshare 失败", exc_info=True)
        _record_error(errors, exc)
        return {}

    frame, error = _fetch_frame(ak.fund_fh_em, attempts=attempts)
    if error is not None:
        logger.warning("取基金分红失败",
                       exc_info=(type(error), error, error.__traceback__))
        _record_error(errors, error)
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


def fetch_hk_dividends(symbol: str, *, errors: list[str] | None = None,
                       attempts: int = FETCH_ATTEMPTS) -> list[dict]:
    """港股分红（东财，文本方案需解析）。当前版本仅保留接口。"""
    try:
        import akshare as ak
    except Exception as exc:      # pragma: no cover - 依赖缺失
        logger.warning("导入 akshare 失败", exc_info=True)
        _record_error(errors, exc)
        return []

    frame, error = _fetch_frame(ak.stock_hk_dividend_payout_em, attempts=attempts,
                                symbol=symbol)
    if error is not None:
        logger.warning("取港股分红失败: %s", symbol,
                       exc_info=(type(error), error, error.__traceback__))
        _record_error(errors, error)
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
    store.ensure_schema(conn)
    holdings = store.list_holdings(conn)
    instruments = {}
    for row in holdings:
        if row["kind"] == schema.KIND_CASH:
            continue
        instruments[row["instrument_id"]] = row

    # 正常登记为 ETF/基金的产品；另外把「代码看起来像基金、却被录成 stock」
    # 的产品也一并走基金接口，避免 510300 / 161130 这类代码去股票接口报错。
    etf_fund_symbols = {
        row["symbol"] for row in instruments.values()
        if row["kind"] in (schema.KIND_ETF, schema.KIND_FUND)
        and row["market"] == schema.MARKET_CN
    }
    etf_like_stocks = {
        row["symbol"] for row in instruments.values()
        if row["kind"] == schema.KIND_STOCK and row["market"] == schema.MARKET_CN
        and _is_cn_fund_code(row["symbol"])
    }
    fund_candidates = sorted(etf_fund_symbols | etf_like_stocks)
    fund_errors: list[str] = []
    fund_map = (fetch_fund_dividends(fund_candidates, errors=fund_errors)
                if (include_funds and fund_candidates) else {})

    saved, failed = 0, []
    for row in instruments.values():
        kind, market, symbol = row["kind"], row["market"], row["symbol"]
        errors: list[str] = []
        if kind == schema.KIND_STOCK and market == schema.MARKET_CN:
            if symbol in etf_like_stocks:
                records = fund_map.get(symbol, [])
                errors = list(fund_errors)
            else:
                records = fetch_stock_dividends(symbol, errors=errors)
        elif kind in (schema.KIND_ETF, schema.KIND_FUND) and market == schema.MARKET_CN:
            records = fund_map.get(symbol, [])
            errors = list(fund_errors) if not records else []
        elif kind == schema.KIND_STOCK and market == schema.MARKET_HK:
            records = fetch_hk_dividends(symbol, errors=errors)
        else:
            failed.append(f"{symbol}（{schema.KIND_NAMES.get(kind, kind)}，暂无自动源）")
            continue

        if not records:
            if errors:
                detail = errors[0].replace("\n", " ")[:100]
                failed.append(f"{symbol}（拉取失败：{detail}）")
            else:
                failed.append(f"{symbol}（没有分红记录）")
            continue
        for record in records:
            store.upsert_dividend(
                conn, row["instrument_id"],
                ex_date=record["ex_date"], pay_date=record.get("pay_date"),
                report_period=record.get("report_period"),
                cash_per_share=record["cash_per_share"],
                stock_per_share=record.get("stock_per_share", 0.0),
                currency=row["currency"],
                source=schema.DIVIDEND_SOURCE_AUTO,
                note=record.get("note", ""),
            )
            saved += 1
    return {"saved": saved, "failed": failed}


def add_manual_dividend(conn, instrument_id: int, *, ex_date: str, cash_per_share: float,
                        pay_date: str | None = None, report_period: str | None = None,
                        currency: str = "CNY",
                        stock_per_share: float = 0.0, note: str = "") -> int:
    """手动登记一笔分红（美股或数据源缺漏时用）。"""
    if cash_per_share < 0:
        raise ValueError("每股分红不能为负")
    return store.upsert_dividend(
        conn, instrument_id, ex_date=ex_date, pay_date=pay_date,
        report_period=report_period,
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
                "report_period": dividend.get("report_period"),
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


def _report_year(record) -> int | None:
    """从报告期取财报年度，例如 2025-06-30 -> 2025。"""
    period = str(record.get("report_period") or "")
    if len(period) >= 4 and period[:4].isdigit():
        return int(period[:4])
    return None


def _is_annual(record) -> bool:
    """报告期是否年报（12-31）。"""
    return str(record.get("report_period") or "").endswith("12-31")


def _year_complete(year: int, records: list[dict], as_of: date) -> bool:
    """判断一个财报年度是否已经完整。

    - 有年报（12-31）分红记录：完整；
    - 没有年报记录：如果已经到了下一年 6 月底，仍没有年报分红，
      就认为该年度已经结束（只有中报/季度分红也算完整）。
    """
    if any(_is_annual(record) for record in records):
        return True
    return as_of >= date(year + 1, 6, 30)


def _forecast_units(records, *, year: int | None, start: str, end: str,
                    as_of: date, allow_ex_date_fallback: bool = True
                    ) -> tuple[float, str, int | None, int, str]:
    """按一个完整财报年度汇总每单位现金分红。

    返回 (每股分红合计, 最近除息日, 使用的财报年度, 分红笔数, 备注)。

    规则：
    - 优先取最近一个完整财报年度；
    - 最近年度只有中报时，回退到上一年度；
    - 一个年度内不管分红几次都全部加总；
    - 没有报告期数据时，基金等产品可以退回按除息日窗口统计；
      A 股个股不允许退回，避免把不同财报年度混在一起。
    """
    with_period = [record for record in records if _report_year(record) is not None]
    if not with_period:
        if not allow_ex_date_fallback:
            if records:
                return 0.0, "", None, 0, "缺少报告期（请重新拉取分红）"
            return 0.0, "", None, 0, "没有分红记录"
        selected = [record for record in records if start <= str(record["ex_date"]) <= end]
        cash_records = [record for record in selected
                        if float(record["cash_per_share"] or 0) > 0]
        cash = sum(float(record["cash_per_share"] or 0) for record in cash_records)
        last_ex = max((str(record["ex_date"]) for record in cash_records), default="")
        note = f"窗口内 {len(cash_records)} 次" if cash_records else "窗口内没有分红"
        return round(cash, 6), last_ex, None, len(cash_records), note

    if year is not None:
        selected = [record for record in with_period if _report_year(record) == year]
        if not selected:
            return 0.0, "", year, 0, f"{year} 年度没有分红"
        cash_records = [record for record in selected
                        if float(record["cash_per_share"] or 0) > 0]
        cash = sum(float(record["cash_per_share"] or 0) for record in cash_records)
        last_ex = max((str(record["ex_date"]) for record in cash_records), default="")
        complete = _year_complete(year, selected, as_of)
        note = f"{year} 年度 {len(cash_records)} 次"
        if not complete:
            note += "（未完整）"
        elif not any(_is_annual(record) for record in selected):
            note += "（无年报）"
        elif not cash_records:
            note += "（无现金分红）"
        return round(cash, 6), last_ex, year, len(cash_records), note

    grouped: dict[int, list[dict]] = {}
    for record in with_period:
        grouped.setdefault(_report_year(record), []).append(record)

    complete_years = [y for y, items in grouped.items()
                      if _year_complete(y, items, as_of)]
    selected_year = max(complete_years) if complete_years else max(grouped)
    selected = grouped[selected_year]
    cash_records = [record for record in selected
                    if float(record["cash_per_share"] or 0) > 0]
    cash = sum(float(record["cash_per_share"] or 0) for record in cash_records)
    last_ex = max((str(record["ex_date"]) for record in cash_records), default="")
    note = f"{selected_year} 年度 {len(cash_records)} 次"
    if not _year_complete(selected_year, selected, as_of):
        note += "（未完整）"
    elif not any(_is_annual(record) for record in selected):
        note += "（无年报）"
    elif not cash_records:
        note += "（无现金分红）"
    return round(cash, 6), last_ex, selected_year, len(cash_records), note


def dividend_forecast(conn, *, account_id: int | None = None,
                      owner_id: int | None = None, year: int | None = None,
                      months: int | None = 12, as_of: str | None = None) -> tuple:
    """按当前持仓估算一年的分红。

    口径：取每个产品**最近一个完整财报年度**的每单位现金分红合计，
    乘以**当前持股数量**。如果最近年度只披露了中报，则回退到上一年度；
    一个年度内无论分红几次都会全部加总。基金等没有报告期的产品仍按除息日窗口统计。

    返回 (明细 DataFrame, 汇总 dict)。
    """
    from quant.portfolio import prices as portfolio_prices
    from quant.portfolio.service import Portfolio

    book = Portfolio(conn)
    # 用本地行情库的最新价，股息率才不是空的
    frame = book.positions(account_id=account_id, owner_id=owner_id,
                           prices=portfolio_prices.resolve_price_map(conn))

    start, end = _window(year, months, as_of)
    as_of_date = date.fromisoformat(as_of) if as_of else date.today()
    scope = f"{year} 年度" if year is not None else "各产品最近完整财报年度"

    columns = ["account", "symbol", "name", "kind", "risk", "quantity", "currency",
               "fiscal_year", "dividend_count", "cash_per_share", "last_ex_date",
               "forecast_amount", "forecast_base", "market_value", "yield_pct", "note"]
    if frame.empty:
        return (pd.DataFrame(columns=columns),
                {"scope": scope, "year": year, "count": 0, "total_base": 0.0,
                 "market_value": 0.0, "yield_pct": 0.0, "with_dividend": 0,
                 "missing_price": 0, "missing_report_period": 0})

    # 一次取出所有分红记录，按产品分组；财报年度口径需要完整历史，不能只看窗口。
    # 送转（cash_per_share=0）也保留，用来判断某个年度是否已经分过年报。
    grouped: dict[int, list[dict]] = {}
    for record in store.list_dividends(conn):
        grouped.setdefault(record["instrument_id"], []).append(record)

    rows = []
    total_base = 0.0
    total_value = 0.0
    with_dividend = 0
    missing_price = 0
    missing_report_period = 0

    for row in frame.itertuples():
        if row.kind == schema.KIND_CASH:
            continue                     # 现金不产生分红

        instrument_id = getattr(row, "instrument_id", None)
        records = grouped.get(instrument_id, [])
        is_cn_stock = (row.kind == schema.KIND_STOCK
                       and getattr(row, "market", None) == schema.MARKET_CN)
        if is_cn_stock and any(_report_year(record) is None for record in records):
            missing_report_period += 1
        cash_per_share, last_ex_date, fiscal_year, dividend_count, note = _forecast_units(
            records, year=year, start=start, end=end, as_of=as_of_date,
            allow_ex_date_fallback=not is_cn_stock)
        quantity = float(row.quantity)
        amount = round(quantity * cash_per_share, 2)
        amount_base = round(book.to_base(amount, row.currency, as_of), 2)

        has_price = row.market_value is not None and not pd.isna(row.market_value)
        market_value = float(row.market_value) if has_price else None
        if not has_price:
            missing_price += 1

        if cash_per_share > 0:
            with_dividend += 1
        elif not note:
            note = "没有分红"

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
            "fiscal_year": fiscal_year,
            "dividend_count": dividend_count,
            "cash_per_share": round(cash_per_share, 6),
            "last_ex_date": last_ex_date,
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
        "year": year,
        "start": start,
        "end": end,
        "count": int(len(detail)),
        "with_dividend": with_dividend,
        "missing_price": missing_price,
        "missing_report_period": missing_report_period,
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
