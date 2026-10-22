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


def test_stock_dividend_parsing_offline():
    """A股分红比例是「每 10 股」，解析时要除以 10。"""
    assert dividends.A_SHARE_LOT == 10.0
    records = dividends.fetch_stock_dividends("__definitely_not_a_symbol__")
    assert records == []
