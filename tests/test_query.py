"""查询 API 单测（使用合成数据库）。"""

from __future__ import annotations

import pandas as pd
import pytest

from quant import query
from quant.data import store

from conftest import DATES, SEASONS, SYMBOLS


@pytest.fixture
def conn(sample_db):
    with store.open_db(sample_db) as connection:
        yield connection


def test_latest_trading_date(conn):
    assert query.latest_trading_date(conn) == DATES[-1]


def test_latest_season(conn):
    assert query.latest_season(conn) == max(SEASONS)


def test_summary(conn):
    result = query.summary(conn)
    assert result["price"]["symbols"] == len(SYMBOLS)
    assert result["price"]["rows"] == len(SYMBOLS) * len(DATES)
    assert result["fundamental"]["seasons"] == len(SEASONS)


def test_snapshot_shape_and_columns(conn):
    df = query.snapshot(conn=conn)
    assert len(df) == len(SYMBOLS)
    for column in ("symbol", "name", "close", "close_org", "market_cap", "pe", "pb"):
        assert column in df.columns
    # 快照取的是每只股票的最后一天
    assert set(df["date"]) == {DATES[-1]}


def test_snapshot_valuation(conn):
    df = query.snapshot(conn=conn).set_index("symbol")
    row = df.loc["000001"]

    # 股本 = 净利润(TTM) / 每股收益(TTM)
    expected_shares = row["net_profit_ttm"] / row["eps_ttm"]
    assert row["shares"] == pytest.approx(expected_shares)
    assert row["market_cap"] == pytest.approx(row["close_org"] * expected_shares)
    assert row["pe"] == pytest.approx(row["close_org"] / row["eps_ttm"])
    assert row["pb"] == pytest.approx(row["close_org"] / row["bvps_ttm"])
    assert row["ps"] == pytest.approx(row["market_cap"] / row["revenue_ttm"])


def test_snapshot_includes_valuation_percentiles(conn):
    df = query.snapshot(conn=conn).set_index("symbol")
    row = df.loc["000001"]
    # conftest 里写入的分位：pe_pct=5, pb_pct=15, ps_pct=25
    assert row["pe_pct_10y"] == pytest.approx(5.0)
    assert row["pe_pct_3y"] == pytest.approx(5.0)
    assert row["pb_pct_10y"] == pytest.approx(15.0)
    assert row["ps_pct_10y"] == pytest.approx(25.0)


def test_snapshot_as_of(conn):
    # 快照取「不晚于 as_of 的最后一个交易日」
    as_of = int(DATES[9].replace("-", ""))
    df = query.snapshot(as_of=as_of, conn=conn)
    assert set(df["date"]) == {DATES[9]}
    assert set(df["season"]) == {20221231}


def test_snapshot_season_max_limits_disclosure(conn):
    # season_max 用来模拟「当时还没披露的季度不能用」
    df = query.snapshot(as_of=int(DATES[-1].replace("-", "")), season_max=20221001, conn=conn)
    assert set(df["season"]) == {20220930}


def test_snapshot_before_any_data(conn):
    assert query.snapshot(as_of=20220101, conn=conn).empty


def test_prices_filters(conn):
    df = query.prices(["000001"], start=int(DATES[5].replace("-", "")), conn=conn)
    assert set(df["symbol"]) == {"000001"}
    assert df["date"].min() == DATES[5]

    all_rows = query.prices(conn=conn)
    assert len(all_rows) == len(SYMBOLS) * len(DATES)


def test_prices_limit_per_symbol(conn):
    df = query.prices(SYMBOLS, limit_per_symbol=5, conn=conn)
    assert len(df) == len(SYMBOLS) * 5
    assert df["date"].max() == DATES[-1]


def test_price_wide(conn):
    wide = query.price_wide(SYMBOLS, conn=conn)
    assert wide.shape == (len(DATES), len(SYMBOLS))
    assert list(wide.columns) == list(SYMBOLS)


def test_price_history(conn):
    hist = query.price_history(SYMBOLS, 10, conn=conn)
    assert len(hist) == len(SYMBOLS) * 10
    assert hist["date"].max() == DATES[-1]


def test_growth_and_fundamentals(conn):
    growth = query.growth(seasons=[20221231], conn=conn)
    assert len(growth) == len(SYMBOLS)
    assert set(growth["season_income_growth"]) == {40.0}

    fund = query.fundamentals(symbols=["000001"], conn=conn)
    assert len(fund) == len(SEASONS)


def test_universe_min_bars(conn):
    assert len(query.universe(min_bars=10, conn=conn)) == len(SYMBOLS)
    assert query.universe(min_bars=1000, conn=conn) == []


def test_stock_names(conn):
    names = query.stock_names(conn=conn)
    assert set(names["symbol"]) == set(SYMBOLS)


def test_to_display(conn):
    df = query.snapshot(conn=conn).head(1)
    displayed = query.to_display(df)
    assert "股票代码" in displayed.columns
    assert "收盘" in displayed.columns or "收盘(不复权)" in displayed.columns
