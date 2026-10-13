"""数据契约单测。"""

from __future__ import annotations

from quant.data import schema


def test_all_tables_listed():
    assert schema.TABLE_DAILY_PRICE in schema.ALL_TABLES
    assert schema.TABLE_FUNDAMENTAL in schema.ALL_TABLES
    assert schema.TABLE_FUNDAMENTAL_GROWTH in schema.ALL_TABLES


def test_fundamental_columns_are_partitioned():
    text = set(schema.FUNDAMENTAL_TEXT_COLUMNS)
    numeric = set(schema.FUNDAMENTAL_NUMERIC_COLUMNS)
    assert text.isdisjoint(numeric), "文本列与数值列不应重叠"
    assert set(schema.FUNDAMENTAL_VALUE_COLUMNS) == text | numeric
    assert "name" in text
    assert "total_revenue" in numeric


def test_price_value_columns_match_mapping():
    mapped = set(schema.PRICE_COLUMN_MAP.values())
    assert set(schema.PRICE_VALUE_COLUMNS) <= mapped
    assert "date" not in schema.PRICE_VALUE_COLUMNS


def test_price_frame_columns_cover_org_and_qfq():
    for base in ("open", "high", "low", "close"):
        assert base in schema.PRICE_FRAME_COLUMNS
        assert f"{base}_org" in schema.PRICE_FRAME_COLUMNS
        assert f"{base}_qfq" in schema.PRICE_FRAME_COLUMNS


def test_financial_columns_exclude_keys():
    assert "report_date" not in schema.FINANCIAL_VALUE_COLUMNS
    assert "eps_ttm" in schema.FINANCIAL_VALUE_COLUMNS
    assert "bvps_ttm" in schema.FINANCIAL_VALUE_COLUMNS


def test_growth_field_map_columns_exist():
    for _name, (cumulative, yoy, pre_year, season_value, season_growth) in schema.GROWTH_FIELD_MAP.items():
        assert cumulative in schema.FUNDAMENTAL_NUMERIC_COLUMNS
        assert yoy in schema.FUNDAMENTAL_NUMERIC_COLUMNS
        for column in (pre_year, season_value, season_growth):
            assert column in schema.GROWTH_VALUE_COLUMNS


def test_display_name():
    assert schema.display_name("total_revenue") == "营业总收入"
    assert schema.display_name("unknown_column") == "unknown_column"
