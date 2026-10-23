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


def _div(book, kind, symbol, ex_date, cash_per_share):
    instrument = store.find_instrument(book.conn, kind, "CN", symbol)
    return dividends.add_manual_dividend(book.conn, instrument["id"],
                                         ex_date=ex_date, cash_per_share=cash_per_share)


def test_forecast_multiplies_per_unit_by_current_quantity(scene):
    book, account = scene
    _div(book, "stock", "600519", "2025-06-20", 20.0)
    _div(book, "stock", "600519", "2025-12-20", 15.0)

    detail, summary = dividends.dividend_forecast(book.conn, account_id=account, year=2025)

    row = detail[detail["symbol"] == "600519"].iloc[0]
    assert row["cash_per_share"] == pytest.approx(35.0)      # 两笔加总
    assert row["forecast_amount"] == pytest.approx(35000.0)  # 1000 股 × 35
    assert row["last_ex_date"] == "2025-12-20"

    assert summary["total_base"] == pytest.approx(35000.0)
    assert summary["with_dividend"] == 1
    assert summary["count"] == 2                             # 现金不算在内


def test_forecast_marks_products_without_dividend(scene):
    book, account = scene
    _div(book, "stock", "600519", "2025-06-20", 20.0)

    detail, summary = dividends.dividend_forecast(book.conn, account_id=account, year=2025)
    etf = detail[detail["symbol"] == "510300"].iloc[0]
    assert etf["cash_per_share"] == 0
    assert etf["forecast_amount"] == 0
    assert "没有分红" in etf["note"]
    assert summary["with_dividend"] == 1


def test_forecast_ignores_dividends_outside_window(scene):
    book, account = scene
    _div(book, "stock", "600519", "2024-06-20", 99.0)   # 窗口外
    _div(book, "stock", "600519", "2025-06-20", 10.0)   # 窗口内

    detail, summary = dividends.dividend_forecast(book.conn, account_id=account, year=2025)
    row = detail[detail["symbol"] == "600519"].iloc[0]
    assert row["cash_per_share"] == pytest.approx(10.0)
    assert summary["total_base"] == pytest.approx(10000.0)


def test_forecast_follows_current_quantity(scene):
    book, account = scene
    _div(book, "stock", "600519", "2025-06-20", 20.0)
    # 卖出一半后，预期应该跟着变
    book.sell(account, kind="stock", market="CN", symbol="600519",
              quantity=500, price=1600, trade_date="2025-07-01")

    detail, _summary = dividends.dividend_forecast(book.conn, account_id=account, year=2025)
    row = detail[detail["symbol"] == "600519"].iloc[0]
    assert row["quantity"] == 500
    assert row["forecast_amount"] == pytest.approx(10000.0)


def test_forecast_excludes_cash(scene):
    book, account = scene
    _div(book, "stock", "600519", "2025-06-20", 20.0)
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
    # 用「最近 12 个月」口径：放两笔，一笔今天附近，一笔两年前
    from datetime import date, timedelta

    today = date.today()
    _div(book, "stock", "600519", (today - timedelta(days=30)).isoformat(), 5.0)
    _div(book, "stock", "600519", (today - timedelta(days=800)).isoformat(), 99.0)

    detail, summary = dividends.dividend_forecast(book.conn, account_id=account, months=12)
    row = detail[detail["symbol"] == "600519"].iloc[0]
    assert row["cash_per_share"] == pytest.approx(5.0)
    assert summary["total_base"] == pytest.approx(5000.0)


def test_forecast_yield_uses_market_value(scene):
    """股息率 = 预期分红 / 当前市值；取不到价格时为 None。"""
    book, account = scene
    _div(book, "stock", "600519", "2025-06-20", 20.0)

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
