"""估值历史分位：PE / PB / PS 的逐日序列与分位计算。

口径（与 UI 设计稿一致）
------------------------
对股票 s、交易日 t：

    PE_t = 不复权收盘价_t / eps_ttm(t)
    PB_t = 不复权收盘价_t / bvps_ttm(t)
    PS_t = 总市值_t / revenue_ttm(t)

其中 `eps_ttm(t)` 等取 **t 时点已披露的最近报告期** 的值（`报告期 <= t`）。

**分位** = 窗口内 `估值 < 当前估值` 的交易日数 ÷ 窗口内有效交易日数 × 100。
「PE 处于 10% 低位」即分位 ≤ 10 —— 窗口内至少 90% 的交易日比现在贵。

有效交易日：剔除估值 `<= 0`（亏损期）与关键指标缺失的交易日。

已知简化：用「报告期」而不是「实际披露日」判断可得性（与项目既有口径
`get_season_iDATE` 一致），因此年初可能提前用到尚未公告的年报。
"""

from __future__ import annotations

import datetime
import logging
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd

from quant.data import schema, store
from quant.foundation.financial import calc_ttm

logger = logging.getLogger(__name__)

#: 参与分位计算的指标
VALUATION_METRICS: tuple[str, ...] = ("pe", "pb", "ps")


# --------------------------------------------------------------------------
# 单只股票的逐日估值序列
# --------------------------------------------------------------------------
def _latest_per_symbol(df: pd.DataFrame, on: str, columns: list[str]) -> pd.DataFrame:
    """按 on 列排序去重（同一报告期只保留一条）。"""
    if df.empty:
        return df
    df = df.sort_values(on)
    df = df.drop_duplicates(subset=[on], keep="last")
    return df.loc[:, [on, *columns]]


def compute_symbol_valuation(symbol: str, conn: sqlite3.Connection) -> pd.DataFrame:
    """返回单只股票的逐日估值序列。

    列：date / idate / close / shares / eps_ttm / bvps_ttm / revenue_ttm / pe / pb / ps
    """
    price = store.read_price(conn, symbol)
    if price.empty:
        return pd.DataFrame()

    price = price.loc[:, ["date", "idate", "close"]].copy()
    price["idate"] = price["idate"].astype("int64")

    financial = store.read_financial(conn, symbol)
    if financial.empty:
        return pd.DataFrame()

    financial = financial.loc[:, ["idate", "eps_ttm", "bvps_ttm", "eps_deducted", "net_profit_deducted"]].copy()
    financial["idate"] = financial["idate"].astype("int64")
    financial = _latest_per_symbol(
        financial, "idate", ["eps_ttm", "bvps_ttm", "eps_deducted", "net_profit_deducted"]
    )

    merged = pd.merge_asof(price, financial, on="idate", direction="backward")

    fundamental = store.read_fundamental(conn, symbols=[symbol])
    if not fundamental.empty:
        fundamental = fundamental.loc[:, ["season", "revenue_ttm", "net_profit_ttm"]].copy()
        fundamental["season"] = fundamental["season"].astype("int64")
        fundamental = _latest_per_symbol(fundamental, "season", ["revenue_ttm", "net_profit_ttm"])
        merged = pd.merge_asof(merged, fundamental, left_on="idate", right_on="season", direction="backward")

    close = pd.to_numeric(merged["close"], errors="coerce")
    eps = pd.to_numeric(merged["eps_ttm"], errors="coerce")
    bvps = pd.to_numeric(merged["bvps_ttm"], errors="coerce")
    revenue = pd.to_numeric(merged["revenue_ttm"], errors="coerce")

    with np.errstate(divide="ignore", invalid="ignore"):
        # 股本 = 净利润(TTM) / 每股收益(TTM)；两者同口径，缺失时回退到扣非口径
        shares_ttm = merged["net_profit_ttm"] / eps.where(eps != 0)
        shares_deducted = merged["net_profit_deducted"] / merged["eps_deducted"].where(
            merged["eps_deducted"] != 0
        )
        merged["shares"] = shares_ttm.fillna(shares_deducted)

        merged["pe"] = close / eps.where(eps != 0)
        merged["pb"] = close / bvps.where(bvps != 0)
        merged["ps"] = (close * merged["shares"]) / revenue.where(revenue > 0)

    merged["symbol"] = symbol
    return merged.replace([np.inf, -np.inf], np.nan)


# --------------------------------------------------------------------------
# 分位
# --------------------------------------------------------------------------
def percentile_rank(values: pd.Series, current: float) -> float:
    """当前值在窗口内的分位（0~100）。"""
    valid = pd.to_numeric(values, errors="coerce")
    valid = valid[(valid > 0) & np.isfinite(valid)]
    if len(valid) == 0 or not np.isfinite(current) or current <= 0:
        return float("nan")
    return float((valid < current).sum()) / float(len(valid)) * 100.0


def compute_percentiles(
    series: pd.DataFrame,
    windows=(3, 5, 10, 0),
    as_of: str | None = None,
) -> list[dict]:
    """对一只股票的逐日估值序列计算各窗口分位。"""
    if series is None or series.empty:
        return []

    df = series.sort_values("date").copy()
    df["_ts"] = pd.to_datetime(df["date"])
    last = df.iloc[-1]
    as_of = as_of or str(last["date"])
    as_of_ts = pd.Timestamp(as_of)

    results: list[dict] = []
    for window in windows:
        if window:
            start_ts = as_of_ts - pd.DateOffset(years=window)
        else:
            start_ts = df["_ts"].min()

        window_df = df[df["_ts"] >= start_ts]
        if window_df.empty:
            continue

        row: dict = {
            "symbol": str(last["symbol"]),
            "window_years": int(window),
            "as_of": as_of,
            "sample_days": int(len(window_df)),
            "window_start": str(window_df.iloc[0]["date"]),
            "window_years_actual": round(
                (as_of_ts - pd.Timestamp(window_df.iloc[0]["_ts"])).days / 365.25, 2
            ),
            "computed_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        for metric in VALUATION_METRICS:
            current = float(last[metric]) if pd.notna(last.get(metric)) else float("nan")
            row[f"current_{metric}"] = current
            row[f"{metric}_pct"] = percentile_rank(window_df[metric], current)
        results.append(row)

    return results


# --------------------------------------------------------------------------
# 批量重建
# --------------------------------------------------------------------------
def rebuild_valuation(
    symbols=None,
    *,
    windows=(3, 5, 10, 0),
    limit: int | None = None,
    workers: int = 4,
    conn: sqlite3.Connection | None = None,
) -> dict:
    """批量计算估值分位并写入 `valuation_percentile` 表。

    - 幂等：按 (symbol, window_years) 覆盖写入
    - 可中断续跑：`symbols` 只传还没算过的股票即可
    """
    own = conn is None
    if own:
        conn = store.connect(create=True)

    started = datetime.datetime.now()
    try:
        if symbols is None:
            symbols = [row[0] for row in conn.execute(
                "SELECT DISTINCT symbol FROM daily_price ORDER BY symbol")]
        else:
            symbols = [str(s).zfill(6) for s in symbols]
        if limit:
            symbols = symbols[:limit]

        logger.info("计算估值分位: %d 只股票, 窗口 %s", len(symbols), list(windows))

        # SQLite 连接不能跨线程共用：并发时每个线程持有自己的连接
        local = threading.local()
        worker_connections: list[sqlite3.Connection] = []
        conn_lock = threading.Lock()

        def thread_conn() -> sqlite3.Connection:
            if not hasattr(local, "conn"):
                local.conn = store.connect()
                with conn_lock:
                    worker_connections.append(local.conn)
            return local.conn

        def work(code: str):
            series = compute_symbol_valuation(code, thread_conn() if workers > 1 else conn)
            return compute_percentiles(series, windows)

        done = 0
        written = 0
        failures: list[str] = []
        rows: list[dict] = []

        if workers and workers > 1:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(work, code): code for code in symbols}
                for future in as_completed(futures):
                    code = futures[future]
                    done += 1
                    try:
                        rows.extend(future.result())
                    except Exception:
                        failures.append(code)
                        logger.exception("计算估值分位失败: %s", code)
                    if done % 200 == 0:
                        written += store.write_valuation_percentile(conn, pd.DataFrame(rows))
                        rows = []
                        conn.commit()
                        elapsed = (datetime.datetime.now() - started).total_seconds()
                        logger.info("估值分位进度 %d/%d，累计 %d 行，用时 %.0fs",
                                    done, len(symbols), written, elapsed)
        else:
            for code in symbols:
                done += 1
                try:
                    rows.extend(work(code))
                except Exception:
                    failures.append(code)
                    logger.exception("计算估值分位失败: %s", code)
                if done % 200 == 0:
                    written += store.write_valuation_percentile(conn, pd.DataFrame(rows))
                    rows = []
                    conn.commit()
                    logger.info("估值分位进度 %d/%d，累计 %d 行", done, len(symbols), written)

        if rows:
            written += store.write_valuation_percentile(conn, pd.DataFrame(rows))
        conn.commit()

        elapsed = (datetime.datetime.now() - started).total_seconds()
        return {
            "symbols": len(symbols),
            "rows": written,
            "failures": failures,
            "elapsed_seconds": round(elapsed, 1),
        }
    finally:
        for worker_conn in locals().get("worker_connections", []):
            try:
                worker_conn.close()
            except Exception:  # pragma: no cover
                pass
        if own:
            conn.close()


def rebuild_fundamental_ttm(conn: sqlite3.Connection | None = None) -> dict:
    """回填 `fundamental` 的 revenue_ttm / net_profit_ttm（滚动四季度）。

    PS 需要「营业总收入(TTM)」，而 fundamental 存的是累计值，这里统一算好落库。
    """
    own = conn is None
    if own:
        conn = store.connect(create=True)
    try:
        df = store.read_fundamental(conn)
        if df.empty:
            return {"rows": 0}

        frames = []
        for column, ttm in (("total_revenue", "revenue_ttm"), ("net_profit", "net_profit_ttm")):
            part = df.loc[:, ["symbol", "season", column]].copy()
            part[column] = pd.to_numeric(part[column], errors="coerce")
            computed = (
                part.groupby("symbol", group_keys=False)
                .apply(lambda g: calc_ttm(g, column, ttm, idate_column="season"))
            )
            computed = computed.dropna(subset=[column])
            frames.append(computed.loc[:, ["symbol", "season", ttm]])

        merged = frames[0].merge(frames[1], on=["symbol", "season"], how="outer")
        rows = store.update_columns(
            conn, schema.TABLE_FUNDAMENTAL, ("symbol", "season"),
            merged, ("revenue_ttm", "net_profit_ttm"),
        )
        conn.commit()
        return {"rows": rows, "symbols": int(merged["symbol"].nunique())}
    finally:
        if own:
            conn.close()
