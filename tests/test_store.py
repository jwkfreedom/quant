"""SQLite 存储层单测（使用临时数据库）。"""

from __future__ import annotations

import pandas as pd

from quant.data import schema, store


def _price_frame():
    return pd.DataFrame({
        "symbol": ["000001", "000001"],
        "date": ["2023-01-03", "2023-01-04"],
        "idate": [20230103, 20230104],
        "open": [10.0, 10.2], "high": [10.6, 10.8], "low": [9.9, 10.0], "close": [10.5, 10.7],
        "open_qfq": [8.0, 8.2], "high_qfq": [8.6, 8.8], "low_qfq": [7.9, 8.0], "close_qfq": [8.5, 8.7],
        "volume": [100, 200], "turnover": [1000, 2000], "amplitude": [1.0, 1.1],
        "pct_change": [1.5, 1.2], "price_change": [0.15, 0.12], "turnover_rate": [0.3, 0.4],
    })


def test_init_and_stats(temp_dir):
    path = temp_dir / "test.db"
    store.init_db(path)
    with store.open_db(path) as conn:
        counts = store.stats(conn)
        assert counts[schema.TABLE_DAILY_PRICE] == 0
        assert store.get_meta(conn, "schema_version") == str(schema.SCHEMA_VERSION)


def test_write_and_read_price(temp_dir):
    path = temp_dir / "test.db"
    store.init_db(path)
    with store.open_db(path) as conn:
        written = store.write_price(conn, _price_frame())
        conn.commit()
        assert written == 2

        df = store.read_price(conn, "000001")
        assert df["date"].tolist() == ["2023-01-03", "2023-01-04"]
        assert df["close_qfq"].tolist() == [8.5, 8.7]

        assert store.last_price_date(conn, "000001") == "2023-01-04"
        assert store.last_price_date(conn, "999999") is None
        assert store.existing_symbols(conn, schema.TABLE_DAILY_PRICE) == {"000001"}


def test_write_price_is_idempotent(temp_dir):
    path = temp_dir / "test.db"
    store.init_db(path)
    with store.open_db(path) as conn:
        store.write_price(conn, _price_frame())
        store.write_price(conn, _price_frame())
        conn.commit()
        assert store.table_count(conn, schema.TABLE_DAILY_PRICE) == 2


def test_read_price_range(temp_dir):
    path = temp_dir / "test.db"
    store.init_db(path)
    with store.open_db(path) as conn:
        store.write_price(conn, _price_frame())
        conn.commit()
        df = store.read_price(conn, "000001", start=20230104)
        assert len(df) == 1


def test_write_growth_with_missing_optional_columns(temp_dir):
    path = temp_dir / "test.db"
    store.init_db(path)
    with store.open_db(path) as conn:
        df = pd.DataFrame({
            "symbol": ["000001"], "season": [20230331],
            "pre_year_income": [1.0], "season_income": [2.0], "season_income_growth": [3.0],
            "pre_year_profit": [4.0], "season_profit": [5.0], "season_profit_growth": [6.0],
        })
        assert store.write_growth(conn, df) == 1
        conn.commit()
        assert store.table_count(conn, schema.TABLE_FUNDAMENTAL_GROWTH) == 1
