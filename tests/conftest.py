"""pytest 公共 fixture。"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from quant.data import schema, store


@pytest.fixture
def temp_dir():
    """自建临时目录。

    不使用 pytest 的 tmp_path：在受限环境下 pytest 的临时根目录可能不可写，
    这里直接用 tempfile.mkdtemp（必要时由 sitecustomize 放宽权限）。
    """
    path = Path(tempfile.mkdtemp(prefix="quant-test-"))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


# --------------------------------------------------------------------------
# 合成数据：3 只股票 × 60 个交易日
# --------------------------------------------------------------------------
SYMBOLS = ("000001", "000002", "600000")
DATES = pd.bdate_range("2023-01-03", periods=60).strftime("%Y-%m-%d").tolist()
SEASONS = (20220930, 20221231)
FINANCIAL_DATES = ("2022-09-30", "2022-12-31")


def _price_frame() -> pd.DataFrame:
    rows = []
    for index, symbol in enumerate(SYMBOLS):
        base = 10.0 * (index + 1)
        for offset, date in enumerate(DATES):
            close = base + offset * 0.1
            rows.append({
                "symbol": symbol,
                "date": date,
                "idate": int(date.replace("-", "")),
                "open": close - 0.05, "high": close + 0.1, "low": close - 0.1, "close": close,
                "open_qfq": close - 0.05, "high_qfq": close + 0.1,
                "low_qfq": close - 0.1, "close_qfq": close,
                "volume": 1_000_000 + offset * 1000,
                "turnover": (1_000_000 + offset * 1000) * close,
                "amplitude": 2.0, "pct_change": 0.5, "price_change": 0.05,
                "turnover_rate": 1.0 + index,
            })
    return pd.DataFrame(rows)


def _fundamental_frame() -> pd.DataFrame:
    rows = []
    for index, symbol in enumerate(SYMBOLS):
        for season in SEASONS:
            revenue = 1e9 * (index + 1) * (1 if season == 20220930 else 1.5)
            rows.append({
                "symbol": symbol, "season": season, "name": f"测试{index + 1}",
                "total_revenue": revenue, "total_revenue_yoy": 20.0,
                "net_profit": revenue * 0.1, "net_profit_yoy": 25.0,
                "total_assets": revenue * 5, "total_liabilities": revenue * 2,
                "debt_ratio": 40.0, "total_equity": revenue * 3,
                "ann_date_bs": "2023-01-10", "ann_date_is": "2023-01-10", "ann_date_cf": "2023-01-10",
                # TTM 列（正常由 quant rebuild-ttm 回填）
                "revenue_ttm": revenue * 4, "net_profit_ttm": revenue * 0.4,
            })
    return pd.DataFrame(rows)


def _financial_frame() -> pd.DataFrame:
    rows = []
    for index, symbol in enumerate(SYMBOLS):
        for offset, report_date in enumerate(FINANCIAL_DATES):
            eps = 1.0 + index + offset * 0.1
            bvps = 5.0 + index
            rows.append({
                "symbol": symbol,
                "report_date": report_date,
                "idate": int(report_date.replace("-", "")),
                "eps_diluted": eps, "eps_deducted": eps,
                "bvps_before": bvps, "bvps_after": bvps,
                "net_profit_deducted": eps * 1e9,
                "roe": 12.0, "gross_margin": 30.0,
                "eps_ttm": eps, "bvps_ttm": bvps,
            })
    return pd.DataFrame(rows)


def build_sample_db(path: Path) -> Path:
    """在 path 处建一个含少量合成数据的数据库。"""
    store.init_db(path)
    with store.open_db(path) as conn:
        store.write_price(conn, _price_frame())
        store.write_fundamental(conn, _fundamental_frame())
        store.write_financial(conn, _financial_frame())

        growth = _fundamental_frame().loc[:, ["symbol", "season"]].copy()
        growth["pre_year_income"] = 1e8
        growth["season_income"] = growth["season"].map({20220930: 3e8, 20221231: 4e8})
        growth["season_income_growth"] = growth["season"].map({20220930: 30.0, 20221231: 40.0})
        growth["pre_year_profit"] = 1e7
        growth["season_profit"] = growth["season"].map({20220930: 2e7, 20221231: 3e7})
        growth["season_profit_growth"] = growth["season"].map({20220930: 50.0, 20221231: 60.0})
        store.write_growth(conn, growth)

        store.write_stock_list(conn, pd.DataFrame({"symbol": list(SYMBOLS), "name": ["测试1", "测试2", "测试3"]}))

        # 估值分位（正常由 quant rebuild-valuation 生成）
        pct_rows = []
        for index, symbol in enumerate(SYMBOLS):
            for window in (3, 5, 10, 0):
                pct_rows.append({
                    "symbol": symbol, "window_years": window,
                    "as_of": DATES[-1], "current_pe": 10.0 + index,
                    "current_pb": 2.0 + index, "current_ps": 1.0 + index,
                    "pe_pct": 5.0 + index, "pb_pct": 15.0 + index, "ps_pct": 25.0 + index,
                    "sample_days": len(DATES), "window_start": DATES[0],
                    "window_years_actual": float(window or 5), "computed_at": "2023-03-27 00:00:00",
                })
        store.write_valuation_percentile(conn, pd.DataFrame(pct_rows))
        conn.commit()
    return path


@pytest.fixture
def sample_db(temp_dir):
    """返回合成数据库的路径。"""
    return build_sample_db(temp_dir / "sample.db")
