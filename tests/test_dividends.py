"""分红逻辑测试：按除息日持股数计算金额、按年汇总、手动记入现金。

不联网：分红记录用手动登记的方式写入，验证的是计算与统计口径。
"""

from __future__ import annotations

import pytest

from quant.portfolio import Portfolio, dividends, init_db, open_db, schema, store


@pytest.fixture
def book(tmp_path):
    db = tmp_path / "portfolio.db"
    init_db(db)
    with open_db(db) as conn:
        yield Portfolio(conn)


@pytest.fixture
def scene(book):
    """华泰账户 + 1000 股 600519（2026-01-05 买入）."""
    owner = book.create_owner("王大")
    account = book.add_account(owner, "华泰证券", currency="CNY")
    book.deposit(account, 2_000_000, trade_date="2026-01-02")
    book.buy(account, kind="stock", market="CN", symbol="600519", name="贵州茅台",
             quantity=1000, price=1500, trade_date="2026-01-05")
    instrument = store.find_instrument(book.conn, "stock", "CN", "600519")
    return book, account, instrument["id"]


def _add(book, instrument_id, ex_date, cash_per_share, **kwargs):
    return dividends.add_manual_dividend(
        book.conn, instrument_id, ex_date=ex_date,
        cash_per_share=cash_per_share, **kwargs,
    )


def test_dividend_uses_quantity_on_ex_date(scene):
    book, account, iid = scene
    _add(book, iid, "2026-06-20", 2.0)

    frame = dividends.dividend_report(book.conn, account_id=account)
    assert len(frame) == 1
    row = frame.iloc[0]
    assert row["quantity"] == 1000
    assert row["amount"] == pytest.approx(2000.0)
    assert row["recorded"] == False  # noqa: E712


def test_dividend_before_position_is_ignored(scene):
    book, account, iid = scene
    _add(book, iid, "2025-06-20", 2.0)      # 建仓前

    frame = dividends.dividend_report(book.conn, account_id=account)
    assert frame.empty


def test_dividend_uses_position_on_that_day_after_partial_sell(scene):
    book, account, iid = scene
    book.sell(account, kind="stock", market="CN", symbol="600519",
              quantity=400, price=1600, trade_date="2026-03-01")
    _add(book, iid, "2026-04-01", 1.0)      # 此时只剩 600 股
    _add(book, iid, "2026-05-01", 1.0)

    frame = dividends.dividend_report(book.conn, account_id=account)
    assert len(frame) == 2
    assert set(frame["quantity"]) == {600.0}
    assert frame["amount"].sum() == pytest.approx(1200.0)


def test_initial_import_starts_the_clock(book):
    owner = book.create_owner("王大")
    account = book.add_account(owner, "华泰证券")
    book.adjust(account, kind="etf", market="CN", symbol="510300",
                name="沪深300ETF", quantity=10000, cost_price=3.9,
                trade_date="2026-01-01")
    iid = store.find_instrument(book.conn, "etf", "CN", "510300")["id"]

    _add(book, iid, "2025-12-15", 0.05)     # 导入之前
    _add(book, iid, "2026-06-15", 0.05)     # 导入之后

    frame = dividends.dividend_report(book.conn, account_id=account)
    assert len(frame) == 1
    assert frame.iloc[0]["ex_date"] == "2026-06-15"
    assert frame.iloc[0]["amount"] == pytest.approx(10000 * 0.05)


def test_dividend_summary_by_year(scene):
    book, account, iid = scene
    _add(book, iid, "2025-06-20", 1.0)
    _add(book, iid, "2026-06-20", 2.0)

    summary_2026 = dividends.dividend_summary(book.conn, account_id=account, year=2026)
    assert summary_2026["count"] == 1
    assert summary_2026["total"] == pytest.approx(2000.0)
    assert summary_2026["year"] == 2026

    # 2025 那笔发生时还没持仓，不计入
    summary_all = dividends.dividend_summary(book.conn, account_id=account)
    assert summary_all["total"] == pytest.approx(2000.0)


def test_summary_groups_by_account(scene, book):
    owner = book.create_owner("李四")
    other = book.add_account(owner, "国金证券", currency="CNY")
    book.deposit(other, 2_000_000, trade_date="2026-01-02")
    book.buy(other, kind="stock", market="CN", symbol="600519", name="贵州茅台",
             quantity=500, price=1500, trade_date="2026-01-06")

    _book, account, iid = scene
    _add(book, iid, "2026-06-20", 2.0)

    summary = dividends.dividend_summary(book.conn)
    assert summary["by_account"]["华泰证券"] == pytest.approx(2000.0)
    assert summary["by_account"]["国金证券"] == pytest.approx(1000.0)
    assert summary["total"] == pytest.approx(3000.0)


def test_record_as_cash_moves_money_and_marks(scene):
    book, account, iid = scene
    dividend_id = _add(book, iid, "2026-06-20", 2.0)
    before = book.cash_balance(account)

    balance = dividends.record_as_cash(book.conn, dividend_id, account)
    assert balance == pytest.approx(before + 2000.0)
    assert book.cash_balance(account) == pytest.approx(before + 2000.0)

    frame = dividends.dividend_report(book.conn, account_id=account)
    assert bool(frame.iloc[0]["recorded"]) is True


def test_record_as_cash_rejects_without_position(scene, book):
    book, account, iid = scene
    owner = book.create_owner("李四")
    other = book.add_account(owner, "国金证券")
    dividend_id = _add(book, iid, "2026-06-20", 2.0)

    with pytest.raises(ValueError):
        dividends.record_as_cash(book.conn, dividend_id, other)


def test_upsert_is_idempotent(scene):
    book, account, iid = scene
    _add(book, iid, "2026-06-20", 2.0)
    _add(book, iid, "2026-06-20", 2.5)      # 同一除息日重复登记 -> 更新

    frame = dividends.dividend_report(book.conn, account_id=account)
    assert len(frame) == 1
    assert frame.iloc[0]["cash_per_share"] == pytest.approx(2.5)


def test_upsert_stores_and_preserves_report_period(scene):
    book, _account, iid = scene
    _add(book, iid, "2026-06-20", 2.0, report_period="2025-12-31")

    rows = store.list_dividends(book.conn)
    assert rows[0]["report_period"] == "2025-12-31"

    # 同一笔再登记但不带报告期时，保留原来的报告期
    _add(book, iid, "2026-06-20", 2.5)
    rows = store.list_dividends(book.conn)
    assert rows[0]["report_period"] == "2025-12-31"


def test_stock_dividend_parsing_offline():
    """A股分红比例是「每 10 股」，解析时要除以 10。"""
    assert dividends.A_SHARE_LOT == 10.0
    records = dividends.fetch_stock_dividends("__definitely_not_a_symbol__", attempts=1)
    assert records == []


def test_stock_dividends_falls_back_to_cninfo(monkeypatch):
    """东财失败时，用巨潮资讯兜底，000408 这类股票不能误报「没分红」。"""
    import pandas as pd

    def fake_fetch_frame(func, *, attempts=3, **kwargs):
        if func.__name__ == "stock_fhps_detail_em":
            return None, RuntimeError("eastmoney timeout")
        return pd.DataFrame([{
            "除权日": "2026-04-17",
            "派息日": "2026-04-17",
            "派息比例": 15.0,
            "送股比例": 0.0,
            "转增比例": 0.0,
            "报告时间": "2025年报",
            "实施方案分红说明": "10派15元(含税)",
        }]), None

    monkeypatch.setattr(dividends, "_fetch_frame", fake_fetch_frame)
    records = dividends.fetch_stock_dividends("000408")
    assert len(records) == 1
    assert records[0]["ex_date"] == "2026-04-17"
    assert records[0]["pay_date"] == "2026-04-17"
    assert records[0]["report_period"] == "2025-12-31"
    assert records[0]["cash_per_share"] == pytest.approx(1.5)
    assert records[0]["stock_per_share"] == pytest.approx(0.0)


def test_stock_dividends_reads_report_period_from_em(monkeypatch):
    """东财的「报告期」要一起存下来，预测才能按财报年度归集。"""
    import pandas as pd

    def fake_fetch_frame(func, *, attempts=3, **kwargs):
        assert func.__name__ == "stock_fhps_detail_em"
        return pd.DataFrame([{
            "报告期": "2025-12-31",
            "除权除息日": "2026-06-26",
            "现金分红-现金分红比例": 4.4,
            "送转股份-送转总比例": 0.0,
            "方案进度": "实施分配",
            "现金分红-现金分红比例描述": "10派4.40元",
        }]), None

    monkeypatch.setattr(dividends, "_fetch_frame", fake_fetch_frame)
    records = dividends.fetch_stock_dividends("601919")
    assert len(records) == 1
    assert records[0]["report_period"] == "2025-12-31"
    assert records[0]["cash_per_share"] == pytest.approx(0.44)


def test_stock_dividends_empty_em_does_not_report_fallback_error(monkeypatch):
    """东财明确返回空表（确实没分红）时，巨潮失败不应误报为整体拉取失败。"""
    import pandas as pd

    def fake_fetch_frame(func, *, attempts=3, **kwargs):
        if func.__name__ == "stock_fhps_detail_em":
            return pd.DataFrame(), None
        return None, RuntimeError("cninfo timeout")

    monkeypatch.setattr(dividends, "_fetch_frame", fake_fetch_frame)
    errors: list[str] = []
    records = dividends.fetch_stock_dividends("000408", errors=errors)
    assert records == []
    assert errors == []


def test_refresh_dividends_saves_stock_records(book, monkeypatch):
    owner = book.create_owner("王大")
    account = book.add_account(owner, "华泰证券")
    book.buy(account, kind="stock", market="CN", symbol="000408",
             name="藏格矿业", quantity=400, price=70, trade_date="2026-04-24")

    def fake_fetch(symbol, *, errors=None, attempts=3):
        assert symbol == "000408"
        return [{
            "ex_date": "2026-09-04",
            "pay_date": None,
            "report_period": "2025-12-31",
            "cash_per_share": 1.0,
            "stock_per_share": 0.0,
            "note": "10派10.00元",
        }]

    monkeypatch.setattr(dividends, "fetch_stock_dividends", fake_fetch)
    result = dividends.refresh_dividends(book.conn)
    assert result == {"saved": 1, "failed": []}

    rows = store.list_dividends(book.conn)
    assert len(rows) == 1
    assert rows[0]["symbol"] == "000408"
    assert rows[0]["ex_date"] == "2026-09-04"
    assert rows[0]["cash_per_share"] == pytest.approx(1.0)

    detail, summary = dividends.dividend_forecast(book.conn, account_id=account,
                                                  as_of="2026-10-24")
    assert summary["with_dividend"] == 1
    assert detail.iloc[0]["symbol"] == "000408"
    assert detail.iloc[0]["cash_per_share"] == pytest.approx(1.0)
    assert detail.iloc[0]["forecast_amount"] == pytest.approx(400.0)


def test_refresh_dividends_reports_fetch_error(book, monkeypatch):
    owner = book.create_owner("王大")
    account = book.add_account(owner, "华泰证券")
    book.buy(account, kind="stock", market="CN", symbol="000408",
             name="藏格矿业", quantity=400, price=70, trade_date="2026-04-24")

    def fake_fetch(symbol, *, errors=None, attempts=3):
        if errors is not None:
            errors.append("ReadTimeout: timed out")
        return []

    monkeypatch.setattr(dividends, "fetch_stock_dividends", fake_fetch)
    result = dividends.refresh_dividends(book.conn)
    assert result["saved"] == 0
    assert "000408" in result["failed"][0]
    assert "拉取失败" in result["failed"][0]
    assert "ReadTimeout" in result["failed"][0]


def test_refresh_dividends_uses_fund_data_for_etf_like_stock(book, monkeypatch):
    """510300 这类 ETF 被误录成 stock 时，也要走基金分红接口。"""
    owner = book.create_owner("王大")
    account = book.add_account(owner, "华泰证券")
    book.buy(account, kind="stock", market="CN", symbol="510300",
             name="沪深300ETF", quantity=1000, price=4, trade_date="2026-04-24")

    called = {}

    def fake_fund(symbols, *, errors=None, attempts=3):
        called["symbols"] = set(symbols)
        return {"510300": [{
            "ex_date": "2026-09-04",
            "pay_date": None,
            "cash_per_share": 0.05,
            "stock_per_share": 0.0,
            "note": "沪深300ETF",
        }]}

    def fake_stock(symbol, *, errors=None, attempts=3):
        raise AssertionError("ETF 不应再走股票分红接口")

    monkeypatch.setattr(dividends, "fetch_fund_dividends", fake_fund)
    monkeypatch.setattr(dividends, "fetch_stock_dividends", fake_stock)
    result = dividends.refresh_dividends(book.conn)

    assert called["symbols"] == {"510300"}
    assert result == {"saved": 1, "failed": []}
    rows = store.list_dividends(book.conn)
    assert rows[0]["symbol"] == "510300"

