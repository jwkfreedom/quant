"""原始表 -> 入库结构的规范化单测。"""

from __future__ import annotations

import pandas as pd
import pytest

from quant.data import frames


def _raw_price_frame():
    return pd.DataFrame({
        "日期": ["2023-01-04", "2023-01-03", "2023-01-03"],
        "开盘": [10.0, 9.0, 9.5],
        "收盘": [10.5, 9.2, 9.6],
        "最高": [10.6, 9.3, 9.7],
        "最低": [9.9, 8.9, 9.4],
        "成交量": [100, 200, 250],
        "成交额": [1000, 1800, 2400],
        "振幅": [1.0, 2.0, 2.1],
        "涨跌幅": [1.5, -0.5, -0.4],
        "涨跌额": [0.15, -0.05, -0.04],
        "换手率": [0.3, 0.6, 0.7],
        "开盘_qfq": [8.0, 7.0, 7.5],
        "收盘_qfq": [8.5, 7.2, 7.6],
        "最高_qfq": [8.6, 7.3, 7.7],
        "最低_qfq": [7.9, 6.9, 7.4],
    })


def test_prepare_price_frame_normalizes():
    df = frames.prepare_price_frame(_raw_price_frame(), "1")
    assert list(df.columns)[:3] == ["symbol", "date", "idate"]
    assert df["symbol"].iloc[0] == "000001"
    # 按日期升序且去重（同日保留最后一条 9.5/9.6）
    assert df["date"].tolist() == ["2023-01-03", "2023-01-04"]
    assert df["open"].tolist() == [9.5, 10.0]
    assert df["close_qfq"].tolist() == [7.6, 8.5]
    assert df["idate"].tolist() == [20230103, 20230104]


def test_prepare_price_frame_drops_bad_dates():
    raw = _raw_price_frame()
    raw.loc[0, "日期"] = "not-a-date"
    df = frames.prepare_price_frame(raw, "000001")
    assert "not-a-date" not in df["date"].tolist()


def test_prepare_price_frame_empty():
    assert frames.prepare_price_frame(pd.DataFrame(), "000001").empty


def test_prepare_etf_frame_maps_legacy_names():
    raw = pd.DataFrame({
        "date": ["2023-01-03"],
        "open": [1.0], "close": [1.1], "high": [1.2], "low": [0.9],
        "volumn": [1000], "turnover": [1100], "amp": [2.0],
        "percent_change": [1.0], "value_change": [0.01], "turnover_rate": [0.5],
    })
    df = frames.prepare_etf_frame(raw, "512480")
    assert df["symbol"].iloc[0] == "512480"
    assert df["volume"].iloc[0] == 1000
    assert df["amplitude"].iloc[0] == 2.0
    assert "volumn" not in df.columns


def test_merge_adjusted_aligns_on_date():
    raw = pd.DataFrame({"日期": ["2023-01-03", "2023-01-04"], "开盘": [1.0, 2.0],
                        "收盘": [1.1, 2.1], "最高": [1.2, 2.2], "最低": [0.9, 1.9]})
    qfq = pd.DataFrame({"日期": ["2023-01-03", "2023-01-04"], "开盘": [0.5, 1.0],
                        "收盘": [0.55, 1.05], "最高": [0.6, 1.1], "最低": [0.45, 0.95]})
    merged = frames.merge_adjusted(raw, qfq)
    assert merged["开盘_qfq"].tolist() == [0.5, 1.0]
    assert merged["开盘"].tolist() == [1.0, 2.0]


def test_merge_adjusted_without_qfq():
    raw = pd.DataFrame({"日期": ["2023-01-03"], "开盘": [1.0], "收盘": [1.1],
                        "最高": [1.2], "最低": [0.9]})
    merged = frames.merge_adjusted(raw, None)
    assert "开盘_qfq" not in merged.columns
