"""增量更新：追加最新数据（季度基本面 / 日线 / ETF），并重建派生表。

设计
----
- `update-jibenmian`：只下载归档区里缺失的季度快照，然后增量摄入 `fundamental` 表
- `update-price`    ：逐只股票从「库中最后一个交易日 + 1 天」接着拉，只写新增区间；
                       `--mode full` 则整段重拉（历史复权因子变化时需要）
- `rebuild-growth` ：从 `fundamental` 重算单季增长写入 `fundamental_growth`
- 所有函数都可重复执行（幂等），支持 `limit` 便于小规模试跑
"""

from __future__ import annotations

import datetime
import logging
import sqlite3
import time

import pandas as pd

from quant.data import download_a, frames, migrate, schema, store
from quant.foundation import growth as growth_module
from quant.foundation.season import get_seasondate

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# 工具
# --------------------------------------------------------------------------
def _next_day(date_str: str) -> str:
    """'2023-06-30' -> '20230701'；非法输入返回空串。"""
    try:
        day = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return ""
    return (day + datetime.timedelta(days=1)).strftime("%Y%m%d")


def _latest_db_season(conn: sqlite3.Connection) -> int | None:
    if not store.table_exists(conn, schema.TABLE_FUNDAMENTAL):
        return None
    row = conn.execute(f"SELECT MAX(season) FROM {schema.TABLE_FUNDAMENTAL}").fetchone()
    return row[0] if row and row[0] else None


def _resolve_symbols(conn: sqlite3.Connection, symbols=None, limit: int | None = None) -> list[str]:
    """确定要更新的股票列表：显式指定 > stock_list 表 > 归档区最新季度文件。"""
    if symbols:
        result = [str(s).zfill(6) for s in symbols]
    else:
        result = []
        if store.table_exists(conn, schema.TABLE_STOCK_LIST):
            result = [row[0] for row in conn.execute(
                f"SELECT symbol FROM {schema.TABLE_STOCK_LIST} ORDER BY symbol")]
        if not result:
            result = download_a.all_a_stocks()
    if limit:
        result = result[:limit]
    return result


# --------------------------------------------------------------------------
# 季度基本面
# --------------------------------------------------------------------------
def update_jibenmian(
    from_year: int | None = None,
    to_year: int | None = None,
    tables: tuple[str, ...] = ("zcfz", "lrb", "xjll"),
    *,
    force: bool = False,
    ingest: bool = True,
    delay: float = 3.0,
    conn: sqlite3.Connection | None = None,
) -> dict:
    """下载缺失季度的基本面快照并摄入数据库。"""
    today = datetime.date.today()
    if to_year is None:
        to_year = today.year
    if from_year is None:
        with store.open_db() as own_conn:
            latest = _latest_db_season(conn or own_conn)
        from_year = latest // 10000 if latest else 2010

    seasons = [s for s in get_seasondate(f"{from_year}-01-01", beforedays=90)
               if int(s[:4]) <= to_year]
    if not seasons:
        logger.info("没有需要更新的季度（%s ~ %s）", from_year, to_year)
        return {"seasons": [], "downloaded": 0, "rows": 0}

    logger.info("目标季度 %s ~ %s，共 %d 个", seasons[0], seasons[-1], len(seasons))

    downloaded = 0
    for table in tables:
        for date in seasons:
            try:
                df = download_a.fetch_jibenmian_season(table, date, force=force)
            except Exception:
                logger.exception("下载失败: %s %s", table, date)
                continue
            if df is None:
                continue
            downloaded += 1
            time.sleep(max(delay, 0))

    result = {"seasons": seasons, "downloaded": downloaded, "rows": 0}
    if ingest:
        own = conn is None
        if own:
            conn = store.connect(create=True)
        try:
            ingested = migrate.migrate_fundamental(conn, download_a.JIBENMIAN_DIR)
            result["rows"] = ingested.get("rows", 0)
            result["ingested_seasons"] = ingested.get("seasons", 0)
        finally:
            if own:
                conn.close()
    return result


# --------------------------------------------------------------------------
# 日线
# --------------------------------------------------------------------------
def update_price(
    symbols=None,
    *,
    mode: str = "incremental",
    start: str = download_a.DEFAULT_START,
    limit: int | None = None,
    delay: float = download_a.DEFAULT_DELAY,
    conn: sqlite3.Connection | None = None,
) -> dict:
    """增量（或全量）更新日线。

    参数 mode:
        'incremental' 从库中最后一个交易日之后开始拉（推荐，日常用）
        'full'        整段重拉（前复权因子变化后需要）
    """
    own = conn is None
    if own:
        conn = store.connect(create=True)

    try:
        symbol_list = _resolve_symbols(conn, symbols, limit)
        today = download_a.today_compact()
        started = time.time()

        updated: list[str] = []
        skipped = 0
        rows = 0
        failures: list[str] = []

        for index, symbol in enumerate(symbol_list, 1):
            try:
                if mode == "full":
                    start_date = start
                else:
                    last = store.last_price_date(conn, symbol)
                    start_date = _next_day(last) if last else start

                if not start_date or start_date > today:
                    skipped += 1
                    continue

                raw = download_a.fetch_price(symbol, start_date, today)
                frame = frames.prepare_price_frame(raw, symbol)
                if frame.empty:
                    skipped += 1
                    continue

                rows += store.write_price(conn, frame)
                updated.append(symbol)
            except Exception:
                failures.append(symbol)
                logger.exception("更新日线失败: %s", symbol)

            if index % 100 == 0:
                conn.commit()
                logger.info("日线更新进度 %d/%d，新增 %d 行，用时 %.0fs",
                            index, len(symbol_list), rows, time.time() - started)
            download_a.sleep(delay)

        conn.commit()
        return {
            "mode": mode,
            "symbols": len(symbol_list),
            "updated": len(updated),
            "skipped": skipped,
            "rows": rows,
            "failures": failures,
        }
    finally:
        if own:
            conn.close()


# --------------------------------------------------------------------------
# ETF
# --------------------------------------------------------------------------
def update_etf(
    symbols=None,
    *,
    start: str = "20180101",
    end: str | None = None,
    delay: float = download_a.DEFAULT_DELAY,
    conn: sqlite3.Connection | None = None,
) -> dict:
    """增量更新 ETF 日线（默认更新内置 ETF 池）。"""
    own = conn is None
    if own:
        conn = store.connect(create=True)

    try:
        symbol_list = [str(s).zfill(6) for s in (symbols or download_a.default_symbols())]
        end = end or download_a.today_compact()

        rows = 0
        updated: list[str] = []
        failures: list[str] = []

        for symbol in symbol_list:
            try:
                last = None
                if store.table_exists(conn, schema.TABLE_ETF_DAILY):
                    row = conn.execute(
                        f"SELECT MAX(date) FROM {schema.TABLE_ETF_DAILY} WHERE symbol = ?", (symbol,)
                    ).fetchone()
                    last = row[0] if row else None
                start_date = _next_day(last) if last else start
                if start_date > end:
                    continue

                raw = download_a.fetch_etf(symbol, start_date, end)
                frame = frames.prepare_etf_frame(raw, symbol)
                if frame.empty:
                    continue
                rows += store.write_etf_price(conn, frame)
                updated.append(symbol)
            except Exception:
                failures.append(symbol)
                logger.exception("更新 ETF 失败: %s", symbol)
            download_a.sleep(delay)

        conn.commit()
        return {"symbols": len(symbol_list), "updated": len(updated), "rows": rows, "failures": failures}
    finally:
        if own:
            conn.close()


# --------------------------------------------------------------------------
# 派生表
# --------------------------------------------------------------------------
def rebuild_growth(
    *,
    season_start: int | None = None,
    drop_broken: bool = False,
    conn: sqlite3.Connection | None = None,
) -> dict:
    """从 fundamental 重算单季增长并写入 fundamental_growth。

    参数 drop_broken=False（默认）时**不**剔除季度不全的股票——缺失季度留 NaN，
    这样增长表覆盖全市场；需要「所有季度都完整」的股票集合时，
    由调用方（例如 calc-growth 或选股过滤链）按查询区间自行过滤。
    """
    own = conn is None
    if own:
        conn = store.connect(create=True)

    try:
        df = store.read_fundamental(conn, season_start, None)
        if df.empty:
            return {"rows": 0, "message": "fundamental 表为空"}

        if drop_broken:
            df = growth_module.rm_broken_stocks(df)

        result = growth_module.compute_growth(df)
        out = result.loc[:, ["symbol", "season", *schema.GROWTH_VALUE_COLUMNS]].copy()

        if season_start is not None:
            conn.execute(f"DELETE FROM {schema.TABLE_FUNDAMENTAL_GROWTH} WHERE season >= ?", (season_start,))
        else:
            conn.execute(f"DELETE FROM {schema.TABLE_FUNDAMENTAL_GROWTH}")
        written = store.write_growth(conn, out)
        conn.commit()
        return {"rows": written, "symbols": int(out["symbol"].nunique())}
    finally:
        if own:
            conn.close()


def update_all(*, price_limit: int | None = None) -> dict:
    """日常一键更新：季度基本面 -> 增长表 -> 日线 -> ETF。"""
    results = {}
    results["jibenmian"] = update_jibenmian()
    results["growth"] = rebuild_growth()
    results["price"] = update_price(limit=price_limit)
    results["etf"] = update_etf()
    return results
