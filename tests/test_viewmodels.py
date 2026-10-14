"""UI 视图模型单测（合成数据库，不依赖 GUI）。"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from quant import config
from quant.data import store
from quant.ui import viewmodels as vm

from conftest import DATES, SYMBOLS


@pytest.fixture
def conn(sample_db):
    with store.open_db(sample_db) as connection:
        yield connection


# --------------------------------------------------------------------------
# 数据总览
# --------------------------------------------------------------------------
def test_data_status(conn):
    status = vm.data_status(conn)
    assert status.price_latest == DATES[-1]
    assert status.price_symbols == len(SYMBOLS)
    assert status.fundamental_latest == 20221231
    assert status.financial_latest == "2022-12-31"
    assert status.counts["daily_price"] == len(SYMBOLS) * len(DATES)


def test_data_status_report_rows(conn):
    rows = vm.data_status(conn).report()
    assert [row[0] for row in rows] == ["行情日线", "季度基本面", "财务指标", "估值分位"]
    assert all(isinstance(row[2], bool) for row in rows)


def test_available_updates_shape():
    actions = vm.available_updates()
    assert {"price", "jibenmian", "financial", "valuation"} == {a["key"] for a in actions}
    for action in actions:
        assert action["label"] and action["command"] and action["desc"]


# --------------------------------------------------------------------------
# 数据浏览器
# --------------------------------------------------------------------------
def test_table_columns(conn):
    columns = dict(vm.table_columns(conn, "financial_indicator"))
    assert columns["eps_ttm"] == "每股收益(TTM)"
    assert columns["symbol"] == "股票代码"


def test_query_table_pagination(conn):
    page1, total = vm.query_table("daily_price", symbols=["000001"], page=1, page_size=10, conn=conn)
    assert total == len(DATES)
    assert len(page1) == 10
    # 默认按日期倒序
    assert page1["date"].iloc[0] == DATES[-1]

    page2, _ = vm.query_table("daily_price", symbols=["000001"], page=2, page_size=10, conn=conn)
    assert page2["date"].iloc[0] == DATES[-11]


def test_query_table_date_filter(conn):
    df, total = vm.query_table("daily_price", symbols=["000001"],
                               date_start=DATES[0], date_end=DATES[4], conn=conn)
    assert total == 5


def test_query_table_extra_conditions(conn):
    df, total = vm.query_table("financial_indicator", extra_conditions=[("eps_ttm", ">", 1.05)], conn=conn)
    assert total == len(df)
    assert (df["eps_ttm"] > 1.05).all()


def test_query_table_rejects_unknown_table(conn):
    with pytest.raises(ValueError):
        vm.query_table("sqlite_master", conn=conn)


def test_query_table_rejects_unknown_column(conn):
    with pytest.raises(ValueError):
        vm.query_table("daily_price", extra_conditions=[("nope", ">", 1)], conn=conn)


def test_query_table_rejects_bad_operator(conn):
    with pytest.raises(ValueError):
        vm.query_table("daily_price", extra_conditions=[("close", "DROP", 1)], conn=conn)


def test_query_table_like_operator(conn):
    df, total = vm.query_table("stock_list", extra_conditions=[("name", "like", "测试1")], conn=conn)
    assert total == 1


def test_export_frame_csv(temp_dir):
    df = pd.DataFrame({"symbol": ["000001"], "close": [10.0]})
    path = vm.export_frame(df, temp_dir / "out.csv", display_names=True)
    assert path.is_file()
    text = path.read_text(encoding="utf-8-sig")
    assert "股票代码" in text


def test_export_frame_excel(temp_dir):
    df = pd.DataFrame({"symbol": ["000001"], "close": [10.0]})
    path = vm.export_frame(df, temp_dir / "out.xlsx")
    assert path.is_file()
    # Excel 会把纯数字字符列读成整数，这里按补零后比较
    loaded = pd.read_excel(path)
    assert str(loaded["symbol"].iloc[0]).zfill(6) == "000001"
    assert loaded["close"].iloc[0] == pytest.approx(10.0)


# --------------------------------------------------------------------------
# 选股
# --------------------------------------------------------------------------
def test_run_screen(conn):
    summary = vm.run_screen(["exclude_st", "market_cap:max=100000"], conn=conn)
    assert summary.count == len(SYMBOLS)
    assert summary.step_text().startswith("初始")
    assert len(summary.steps) == 2


def test_run_screen_with_columns_and_limit(conn):
    summary = vm.run_screen(["exclude_st"], columns=["symbol", "pe"], limit=2, conn=conn)
    assert list(summary.frame.columns) == ["symbol", "pe"]
    assert len(summary.frame) == 2


def test_run_screen_as_of_defaults_to_latest(conn):
    summary = vm.run_screen(["exclude_st"], conn=conn)
    assert summary.as_of == int(DATES[-1].replace("-", ""))


# --------------------------------------------------------------------------
# 筛选方案
# --------------------------------------------------------------------------
def test_screen_save_load_delete(temp_dir, monkeypatch):
    monkeypatch.setattr(config, "SCREENS_DIR", temp_dir / "screens")
    assert vm.list_screens() == []

    path = vm.save_screen("低估值高ROE", ["pe:max=20", "roe:min=10"], note="测试")
    assert path.is_file()
    assert vm.list_screens() == ["低估值高ROE"]

    payload = vm.load_screen("低估值高ROE")
    assert payload["specs"] == ["pe:max=20", "roe:min=10"]
    assert payload["note"] == "测试"

    assert vm.delete_screen("低估值高ROE") is True
    assert vm.list_screens() == []


def test_screen_name_validation(temp_dir, monkeypatch):
    monkeypatch.setattr(config, "SCREENS_DIR", temp_dir / "screens")
    with pytest.raises(ValueError):
        vm.save_screen("bad/name", [])
    with pytest.raises(ValueError):
        vm.save_screen("", [])
    with pytest.raises(FileNotFoundError):
        vm.load_screen("不存在的方案")


def test_screen_payload_is_json(temp_dir, monkeypatch):
    monkeypatch.setattr(config, "SCREENS_DIR", temp_dir / "screens")
    path = vm.save_screen("abc", ["exclude_st"])
    json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# 个股
# --------------------------------------------------------------------------
def test_stock_detail(conn):
    detail = vm.stock_detail("000001", conn=conn)
    assert detail.symbol == "000001"
    assert detail.name == "测试1"
    assert not detail.price.empty
    assert not detail.financial.empty
    assert not detail.fundamental.empty
    assert not detail.percentiles.empty
    assert detail.metrics["close"] is not None
    assert detail.metrics["pe"] is not None
    assert detail.metrics["pe_pct_10y"] == pytest.approx(5.0)


def test_stock_detail_unknown_symbol(conn):
    detail = vm.stock_detail("999999", conn=conn)
    assert detail.price.empty
    assert detail.metrics == {}


def test_stock_list_search(conn):
    assert len(vm.stock_list(conn=conn)) == len(SYMBOLS)
    assert len(vm.stock_list(conn=conn, keyword="测试")) == len(SYMBOLS)
    assert len(vm.stock_list(conn=conn, keyword="000002")) == 1
