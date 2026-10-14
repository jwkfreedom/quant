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
import socket
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

            # PS 分位依赖 fundamental 的 TTM 列，摄入后顺手回填
            from quant.foundation.valuation import rebuild_fundamental_ttm

            result["ttm_rows"] = rebuild_fundamental_ttm(conn).get("rows", 0)
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
    workers: int = 4,
    timeout: float = 40.0,
    source: str = "auto",
    conn: sqlite3.Connection | None = None,
) -> dict:
    """增量（或全量）更新日线。

    参数 mode:
        'incremental' 从库中最后一个交易日之后开始拉（推荐，日常用）
        'full'        整段重拉（前复权因子变化后需要）

    抓取用线程池并发（默认 4），写库仍是单线程，避免 SQLite 并发写冲突。
    """
    own = conn is None
    if own:
        conn = store.connect(create=True)

    original_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)

    try:
        symbol_list = _resolve_symbols(conn, symbols, limit)
        today = download_a.today_compact()
        started = time.time()

        # 先算好每只股票的起始日期（要读库，放在主线程）
        plan: list[tuple[str, str]] = []
        skipped = 0
        for symbol in symbol_list:
            if mode == "full":
                start_date = start
            else:
                last = store.last_price_date(conn, symbol)
                start_date = _next_day(last) if last else start
            if not start_date or start_date > today:
                skipped += 1
                continue
            plan.append((symbol, start_date))

        updated: list[str] = []
        rows = 0
        failures: list[str] = []

        def load_one(item: tuple[str, str]) -> tuple[str, pd.DataFrame]:
            code, start_date = item
            download_a.sleep(delay)
            raw = download_a.fetch_price(code, start_date, today, source=source)
            return code, frames.prepare_price_frame(raw, code)

        def consume(code: str, frame: pd.DataFrame) -> None:
            nonlocal rows
            if frame is None or frame.empty:
                return
            rows += store.write_price(conn, frame)
            updated.append(code)

        if workers and workers > 1:
            from concurrent.futures import ThreadPoolExecutor, as_completed

            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(load_one, item): item[0] for item in plan}
                for index, future in enumerate(as_completed(futures), 1):
                    code = futures[future]
                    try:
                        symbol_code, frame = future.result()
                        consume(symbol_code, frame)
                    except Exception:
                        failures.append(code)
                        logger.exception("更新日线失败: %s", code)
                    if index % 100 == 0:
                        conn.commit()
                        logger.info("日线更新进度 %d/%d，更新 %d 只，新增 %d 行，用时 %.0fs",
                                    index, len(plan), len(updated), rows, time.time() - started)
        else:
            for index, item in enumerate(plan, 1):
                try:
                    code, frame = load_one(item)
                    consume(code, frame)
                except Exception:
                    failures.append(item[0])
                    logger.exception("更新日线失败: %s", item[0])
                if index % 100 == 0:
                    conn.commit()
                    logger.info("日线更新进度 %d/%d，更新 %d 只，新增 %d 行，用时 %.0fs",
                                index, len(plan), len(updated), rows, time.time() - started)

        conn.commit()
        return {
            "mode": mode,
            "symbols": len(symbol_list),
            "planned": len(plan),
            "updated": len(updated),
            "skipped": skipped,
            "rows": rows,
            "failures": failures,
        }
    finally:
        socket.setdefaulttimeout(original_timeout)
        if own:
            conn.close()


# --------------------------------------------------------------------------
# 财务指标
# --------------------------------------------------------------------------
#: fetch_financial 的起始年份回退阶梯
_FINANCIAL_START_YEARS: tuple[str, ...] = ("2010", "2015", "2020")


def fetch_financial(symbol: str, start_year: str = "2010") -> pd.DataFrame:
    """拉取单只股票的财务指标（新浪「主要财务指标」）。

    akshare 的实现会按年份逐年请求，起始年份太早时（例如 2000）对部分股票会
    直接返回空表。因此这里做**起始年份回退**：2010 -> 2015 -> 2020，
    取第一个非空结果。
    """
    import akshare as ak

    ladder = [start_year] + [year for year in _FINANCIAL_START_YEARS if year != start_year]
    for year in ladder:
        try:
            df = ak.stock_financial_analysis_indicator(symbol=symbol, start_year=year)
        except TypeError:
            # 老版本 akshare 没有 start_year 参数
            try:
                return ak.stock_financial_analysis_indicator(symbol=symbol)
            except Exception:
                return pd.DataFrame()
        except Exception:
            logger.debug("fetch_financial(%s, %s) 失败，尝试下一个起始年份", symbol, year, exc_info=True)
            continue
        if df is not None and not df.empty:
            return df

    logger.warning("%s 的财务指标接口返回空数据", symbol)
    return pd.DataFrame()


def stale_financial_symbols(conn: sqlite3.Connection, days: int = 180) -> list[str]:
    """返回财务指标「过期」的股票：没有数据，或最新报告期早于 days 天前。"""
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    sql = f"""
        SELECT s.symbol
        FROM {schema.TABLE_STOCK_LIST} s
        LEFT JOIN (
            SELECT symbol, MAX(report_date) AS last_date
            FROM {schema.TABLE_FINANCIAL} GROUP BY symbol
        ) f ON f.symbol = s.symbol
        WHERE f.last_date IS NULL OR f.last_date < ?
        ORDER BY s.symbol
    """
    return [row[0] for row in conn.execute(sql, [cutoff])]


def update_financial(
    symbols=None,
    *,
    limit: int | None = None,
    delay: float = 0.2,
    skip_unchanged: bool = True,
    workers: int = 3,
    timeout: float = 40.0,
    stale_days: int | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict:
    """逐股更新财务指标（financial_indicator 表）。

    - 接口一次返回该股票的全部历史报告期，直接整体 upsert（幂等）
    - `skip_unchanged=True` 时，若库中最新报告期已与接口返回的最新报告期相同则跳过写入
    - 单只请求约 1~2 秒且是网络等待，因此默认用 `workers=6` 并发抓取
      （写库仍在单线程里做，避免 SQLite 并发写冲突）
    - 全市场约 5000 只，建议后台跑：`quant update-financial`
    """
    from quant.data.frames import prepare_financial_frame

    own = conn is None
    if own:
        conn = store.connect(create=True)

    # akshare 的请求没有超时设置，个别标的可能把线程永久挂住；
    # 这里给整个进程设一个默认 socket 超时，让卡住的请求快速失败并被记入 failures。
    original_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)

    try:
        if stale_days is not None:
            symbol_list = stale_financial_symbols(conn, stale_days)
            if limit:
                symbol_list = symbol_list[:limit]
            logger.info("财务指标过期（%d 天）的股票: %d 只", stale_days, len(symbol_list))
        else:
            symbol_list = _resolve_symbols(conn, symbols, limit)
        started = time.time()
        updated: list[str] = []
        skipped = 0
        rows = 0
        failures: list[str] = []

        def load_one(code: str) -> pd.DataFrame:
            """抓取 + 规范化（在工作线程里跑，纯网络与 CPU，不碰数据库）。"""
            download_a.sleep(delay)
            return prepare_financial_frame(fetch_financial(code), code)

        def consume(frame: pd.DataFrame, symbol: str) -> None:
            """写库（只在主线程调用）。"""
            nonlocal rows, skipped
            if frame is None or frame.empty:
                skipped += 1
                return
            if skip_unchanged and store.table_exists(conn, schema.TABLE_FINANCIAL):
                latest = conn.execute(
                    f"SELECT MAX(report_date) FROM {schema.TABLE_FINANCIAL} WHERE symbol = ?", (symbol,)
                ).fetchone()
                if latest and latest[0] and latest[0] >= frame["report_date"].max():
                    skipped += 1
                    return
            rows += store.write_financial(conn, frame)
            updated.append(symbol)

        if workers and workers > 1:
            from concurrent.futures import ThreadPoolExecutor, as_completed

            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(load_one, symbol): symbol for symbol in symbol_list}
                for index, future in enumerate(as_completed(futures), 1):
                    symbol = futures[future]
                    try:
                        consume(future.result(), symbol)
                    except Exception:
                        failures.append(symbol)
                        logger.exception("更新财务指标失败: %s", symbol)
                    if index % 100 == 0:
                        conn.commit()
                        logger.info("财务指标进度 %d/%d，更新 %d 只，累计 %d 行，用时 %.0fs",
                                    index, len(symbol_list), len(updated), rows, time.time() - started)
        else:
            for index, symbol in enumerate(symbol_list, 1):
                try:
                    consume(load_one(symbol), symbol)
                except Exception:
                    failures.append(symbol)
                    logger.exception("更新财务指标失败: %s", symbol)
                if index % 100 == 0:
                    conn.commit()
                    logger.info("财务指标进度 %d/%d，更新 %d 只，累计 %d 行，用时 %.0fs",
                                index, len(symbol_list), len(updated), rows, time.time() - started)

        conn.commit()
        return {
            "symbols": len(symbol_list),
            "updated": len(updated),
            "skipped": skipped,
            "rows": rows,
            "failures": failures,
        }
    finally:
        socket.setdefaulttimeout(original_timeout)
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


def update_all(*, price_limit: int | None = None, with_financial: bool = False) -> dict:
    """日常一键更新：季度基本面 -> 增长表 -> 日线 -> ETF（可选财务指标）。

    财务指标逐股请求、耗时较长，默认不包含；需要时用 `quant update-financial` 单独跑。
    """
    results = {}
    results["jibenmian"] = update_jibenmian()
    results["growth"] = rebuild_growth()
    results["price"] = update_price(limit=price_limit)
    results["etf"] = update_etf()
    if with_financial:
        results["financial"] = update_financial()
    return results
