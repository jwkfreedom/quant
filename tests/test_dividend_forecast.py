"""分红预期测试：按当前持仓 × 最近一个年度的每单位分红估算。

不联网：分红记录用手动登记写入，验证的是计算口径。
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
    """华泰账户：600519 1000 股、510300 10000 份，另有现金。"""
    owner = book.create_owner("王大")
    account = book.add_account(owner, "华泰证券")
    book.deposit(account, 1_000_000, trade_date="2024-01-02")
    book.adjust(account, kind="stock", market="CN", symbol="600519", name="贵州茅台",
                quantity=1000, cost_price=1500, trade_date="2024-01-05")
    book.adjust(account, kind="etf", market="CN", symbol="510300", name="沪深300ETF",
                quantity=10000, cost_price=3.9, trade_date="2024-01-05")
    return book, account


def _div(book, kind, symbol, ex_date, cash_per_share, report_period=None):
    instrument = store.find_instrument(book.conn, kind, "CN", symbol)
    return dividends.add_manual_dividend(book.conn, instrument["id"],
                                         ex_date=ex_date, cash_per_share=cash_per_share,
                                         report_period=report_period)


def test_forecast_multiplies_per_unit_by_current_quantity(scene):
    book, account = scene
    _div(book, "stock", "600519", "2025-06-20", 20.0, report_period="2025-06-30")
    _div(book, "stock", "600519", "2025-12-20", 15.0, report_period="2025-12-31")

    detail, summary = dividends.dividend_forecast(book.conn, account_id=account, year=2025)

    row = detail[detail["symbol"] == "600519"].iloc[0]
    assert row["cash_per_share"] == pytest.approx(35.0)      # 两笔加总
    assert row["forecast_amount"] == pytest.approx(35000.0)  # 1000 股 × 35
    assert row["last_ex_date"] == "2025-12-20"
    assert row["fiscal_year"] == 2025
    assert row["dividend_count"] == 2

    assert summary["total_base"] == pytest.approx(35000.0)
    assert summary["with_dividend"] == 1
    assert summary["count"] == 2                             # 现金不算在内


def test_forecast_marks_products_without_dividend(scene):
    book, account = scene
    _div(book, "stock", "600519", "2025-06-20", 20.0, report_period="2025-06-30")

    detail, summary = dividends.dividend_forecast(book.conn, account_id=account, year=2025)
    etf = detail[detail["symbol"] == "510300"].iloc[0]
    assert etf["cash_per_share"] == 0
    assert etf["forecast_amount"] == 0
    assert "没有分红" in etf["note"]
    assert summary["with_dividend"] == 1


def test_forecast_ignores_dividends_outside_selected_year(scene):
    book, account = scene
    _div(book, "stock", "600519", "2024-06-20", 99.0, report_period="2024-12-31")
    _div(book, "stock", "600519", "2025-06-20", 10.0, report_period="2025-06-30")

    detail, summary = dividends.dividend_forecast(book.conn, account_id=account, year=2025)
    row = detail[detail["symbol"] == "600519"].iloc[0]
    assert row["cash_per_share"] == pytest.approx(10.0)
    assert summary["total_base"] == pytest.approx(10000.0)


def test_forecast_follows_current_quantity(scene):
    book, account = scene
    _div(book, "stock", "600519", "2025-06-20", 20.0, report_period="2025-06-30")
    # 卖出一半后，预期应该跟着变
    book.sell(account, kind="stock", market="CN", symbol="600519",
              quantity=500, price=1600, trade_date="2025-07-01")

    detail, _summary = dividends.dividend_forecast(book.conn, account_id=account, year=2025)
    row = detail[detail["symbol"] == "600519"].iloc[0]
    assert row["quantity"] == 500
    assert row["forecast_amount"] == pytest.approx(10000.0)


def test_forecast_excludes_cash(scene):
    book, account = scene
    _div(book, "stock", "600519", "2025-06-20", 20.0, report_period="2025-06-30")
    detail, _summary = dividends.dividend_forecast(book.conn, account_id=account, year=2025)
    assert schema.CASH_SYMBOL not in set(detail["symbol"])


def test_forecast_empty_when_no_holdings(book):
    owner = book.create_owner("李四")
    account = book.add_account(owner, "空账户")
    detail, summary = dividends.dividend_forecast(book.conn, account_id=account, year=2025)
    assert detail.empty
    assert summary["count"] == 0
    assert summary["total_base"] == 0


def test_forecast_by_months_recent_window(scene):
    book, account = scene
    # 基金没有报告期，仍按「最近 N 个月」的除息日窗口统计
    from datetime import date, timedelta

    today = date.today()
    _div(book, "etf", "510300", (today - timedelta(days=30)).isoformat(), 5.0)
    _div(book, "etf", "510300", (today - timedelta(days=800)).isoformat(), 99.0)

    detail, summary = dividends.dividend_forecast(book.conn, account_id=account, months=12)
    row = detail[detail["symbol"] == "510300"].iloc[0]
    assert row["cash_per_share"] == pytest.approx(5.0)
    assert summary["total_base"] == pytest.approx(50000.0)


def test_forecast_stock_without_report_period_is_not_calculated(scene):
    """A 股个股缺报告期时不能退回按除息日窗口，避免混用不同财报年度。"""
    book, account = scene
    _div(book, "stock", "600519", "2025-06-20", 20.0)   # 没有 report_period

    detail, summary = dividends.dividend_forecast(book.conn, account_id=account, year=2025)
    row = detail[detail["symbol"] == "600519"].iloc[0]
    assert row["cash_per_share"] == 0
    assert "缺少报告期" in row["note"]
    assert summary["with_dividend"] == 0
    assert summary["missing_report_period"] == 1


def test_forecast_yield_uses_market_value(scene):
    """股息率 = 预期分红 / 当前市值；取不到价格时为 None。"""
    book, account = scene
    _div(book, "stock", "600519", "2025-06-20", 20.0, report_period="2025-06-30")

    # 先用注入价格验证 positions 的市值口径
    from quant.portfolio.service import Portfolio

    prices = {("stock", "CN", "600519"): (2000.0, "2025-12-31")}
    frame = Portfolio(book.conn).positions(prices=prices)
    row = frame[frame["symbol"] == "600519"].iloc[0]
    assert row["market_value"] == pytest.approx(2_000_000.0)

    detail, summary = dividends.dividend_forecast(book.conn, account_id=account, year=2025)
    row = detail[detail["symbol"] == "600519"].iloc[0]
    assert summary["total_base"] == pytest.approx(20000.0)

    # 价格来自本地行情库：有数据就算得出股息率，没有就是 None
    if row["market_value"] is None:
        assert row["yield_pct"] is None
        assert summary["yield_pct"] == 0.0
    else:
        assert row["yield_pct"] == pytest.approx(
            row["forecast_amount"] / row["market_value"] * 100, abs=0.01)


def test_forecast_includes_instrument_id_column(scene):
    book, account = scene
    frame = book.positions()
    assert "instrument_id" in frame.columns
    assert int(frame.iloc[0]["instrument_id"]) > 0


def test_forecast_uses_latest_complete_fiscal_year(scene):
    """2025 年两次、2026 年只有中报时，应完整使用 2025 年数据。"""
    book, account = scene
    _div(book, "stock", "600519", "2025-06-20", 1.0, report_period="2024-12-31")
    _div(book, "stock", "600519", "2025-12-20", 0.6, report_period="2025-06-30")
    _div(book, "stock", "600519", "2026-06-20", 0.4, report_period="2025-12-31")
    _div(book, "stock", "600519", "2026-10-20", 0.3, report_period="2026-06-30")

    detail, _summary = dividends.dividend_forecast(book.conn, account_id=account)
    row = detail[detail["symbol"] == "600519"].iloc[0]
    # 2026 年只有中报，回退到完整的 2025 年（0.6 + 0.4），而不是 1.3
    assert row["fiscal_year"] == 2025
    assert row["dividend_count"] == 2
    assert row["cash_per_share"] == pytest.approx(1.0)
    assert row["last_ex_date"] == "2026-06-20"
    assert row["forecast_amount"] == pytest.approx(1000.0)

    # 2026 年报也分红后，改用完整的 2026 年（0.3 + 0.5）
    _div(book, "stock", "600519", "2027-06-20", 0.5, report_period="2026-12-31")
    detail, _summary = dividends.dividend_forecast(book.conn, account_id=account)
    row = detail[detail["symbol"] == "600519"].iloc[0]
    assert row["fiscal_year"] == 2026
    assert row["dividend_count"] == 2
    assert row["cash_per_share"] == pytest.approx(0.8)
    assert row["forecast_amount"] == pytest.approx(800.0)


def test_forecast_explicit_year_uses_report_period(scene):
    """指定年度时按报告期归年，而不是按除息日归年。"""
    book, account = scene
    _div(book, "stock", "600519", "2025-12-20", 0.6, report_period="2025-06-30")
    _div(book, "stock", "600519", "2026-06-20", 0.4, report_period="2025-12-31")
    _div(book, "stock", "600519", "2026-10-20", 0.3, report_period="2026-06-30")

    detail, summary = dividends.dividend_forecast(book.conn, account_id=account, year=2025)
    row = detail[detail["symbol"] == "600519"].iloc[0]
    assert summary["scope"] == "2025 年度"
    assert row["fiscal_year"] == 2025
    assert row["cash_per_share"] == pytest.approx(1.0)
    assert row["last_ex_date"] == "2026-06-20"

    detail, _summary = dividends.dividend_forecast(book.conn, account_id=account, year=2026)
    row = detail[detail["symbol"] == "600519"].iloc[0]
    assert row["fiscal_year"] == 2026
    assert row["dividend_count"] == 1
    assert "未完整" in row["note"]
    assert row["cash_per_share"] == pytest.approx(0.3)


def test_forecast_uses_latest_year_when_no_annual_dividend(scene):
    """从来没有年报分红时（只按中报/季度分红），取最近一个财报年度。"""
    book, account = scene
    _div(book, "stock", "600519", "2024-12-20", 0.9, report_period="2024-06-30")
    _div(book, "stock", "600519", "2025-06-20", 0.2, report_period="2025-06-30")
    _div(book, "stock", "600519", "2025-10-20", 0.1, report_period="2025-09-30")

    detail, _summary = dividends.dividend_forecast(book.conn, account_id=account)
    row = detail[detail["symbol"] == "600519"].iloc[0]
    assert row["fiscal_year"] == 2025
    assert row["dividend_count"] == 2
    assert row["cash_per_share"] == pytest.approx(0.3)
    assert "无年报" in row["note"]


def test_forecast_stock_only_annual_still_completes_the_year(scene):
    """年报只送转、不派现，也算该年度分红已经完整。"""
    book, account = scene
    instrument = store.find_instrument(book.conn, "stock", "CN", "600519")
    iid = instrument["id"]
    dividends.add_manual_dividend(book.conn, iid, ex_date="2025-12-20",
                                  cash_per_share=0.5, report_period="2025-06-30")
    dividends.add_manual_dividend(book.conn, iid, ex_date="2026-06-20",
                                  cash_per_share=0.0, stock_per_share=0.1,
                                  report_period="2025-12-31")
    dividends.add_manual_dividend(book.conn, iid, ex_date="2026-10-20",
                                  cash_per_share=0.6, report_period="2026-06-30")

    detail, _summary = dividends.dividend_forecast(book.conn, account_id=account)
    row = detail[detail["symbol"] == "600519"].iloc[0]
    assert row["fiscal_year"] == 2025
    assert row["dividend_count"] == 1       # 只数现金分红
    assert row["cash_per_share"] == pytest.approx(0.5)
    assert row["forecast_amount"] == pytest.approx(500.0)
