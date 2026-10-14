"""一次性迁移：原始 CSV -> SQLite，并把原始件归档到 data/original/。

用法（通过 CLI）::

    quant db-init                     # 建库建表
    quant db-migrate                  # CSV -> SQLite（可重复执行，自动跳过已迁移的标的）
    quant db-migrate --archive        # 迁移完成后把原始 CSV 归档到 data/original/
    quant db-migrate --cleanup        # 归档后删除已入库的行情 CSV（释放空间，不可逆）
    quant db-stats                    # 查看各表行数

迁移完成后：
    data/original/jibenmian/         季度三表原始 CSV
    data/original/financial/         单股财务指标原始 CSV
    data/original/stock_statements/  单股三表明细原始 CSV
    data/original/etf/               ETF 清单等
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
import time
from pathlib import Path

import pandas as pd

from quant.config import DATA_DIR, ORIGINAL_DIR
from quant.data import frames, schema, store

logger = logging.getLogger(__name__)

#: 迁移前的数据布局
LEGACY_JIBENMIAN_DIR = DATA_DIR / "a" / "jibenmian"
LEGACY_FINANCIAL_DIR = DATA_DIR / "a" / "stock" / "financial"
LEGACY_STATEMENT_DIRS = ("lrb", "xjll", "zcfz")
LEGACY_PRICE_DIR = DATA_DIR / "a" / "stock" / "price"
LEGACY_TEMP_DIR = DATA_DIR / "a" / "stock" / "temp"
LEGACY_PRICE_ZIP = DATA_DIR / "a" / "stock" / "price.zip"
LEGACY_ETF_DIR = DATA_DIR / "a" / "etf"
LEGACY_ETF_PRICE_DIR = LEGACY_ETF_DIR / "price"

#: 迁移后的归档位置
ORIGINAL_JIBENMIAN_DIR = ORIGINAL_DIR / "jibenmian"
ORIGINAL_FINANCIAL_DIR = ORIGINAL_DIR / "financial"
ORIGINAL_STATEMENT_DIR = ORIGINAL_DIR / "stock_statements"
ORIGINAL_ETF_DIR = ORIGINAL_DIR / "etf"

#: 交易记录（随包分发）
TRADE_RECORD_CSV = Path(__file__).resolve().parent.parent / "trade" / "records.csv"


# --------------------------------------------------------------------------
# 工具
# --------------------------------------------------------------------------
def _to_numeric(df: pd.DataFrame, columns) -> pd.DataFrame:
    """把指定列转成数值（非数值 -> NaN）。"""
    for column in columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def _normalize_symbol(series: pd.Series) -> pd.Series:
    """股票代码统一为 6 位字符串。"""
    return series.map(lambda v: str(v).strip().split(".")[0].zfill(6))


def _read_price_files(symbol: str) -> pd.DataFrame | None:
    """读取某只股票的 pre/cur 两个 CSV 并合并（不排序，调用方处理）。"""
    parts = []
    for suffix in ("pre", "cur"):
        path = LEGACY_PRICE_DIR / f"price_{symbol}_{suffix}.csv"
        if path.is_file():
            parts.append(pd.read_csv(path))
    if not parts:
        return None
    return pd.concat(parts, ignore_index=True)


# --------------------------------------------------------------------------
# 行情
# --------------------------------------------------------------------------
def migrate_prices(conn: sqlite3.Connection, *, limit: int | None = None, resume: bool = True) -> dict:
    """把 data/a/stock/price/*.csv 迁移进 daily_price 表。"""
    symbols = sorted(
        {p.name[len("price_"):-len("_pre.csv")] for p in LEGACY_PRICE_DIR.glob("price_*_pre.csv")}
        | {p.name[len("price_"):-len("_cur.csv")] for p in LEGACY_PRICE_DIR.glob("price_*_cur.csv")}
    )
    if resume:
        done = store.existing_symbols(conn, schema.TABLE_DAILY_PRICE)
        symbols = [s for s in symbols if s not in done]
    if limit:
        symbols = symbols[:limit]

    total_rows = 0
    failures: list[str] = []
    started = time.time()

    for index, symbol in enumerate(symbols, 1):
        try:
            df = _read_price_files(symbol)
            if df is None or df.empty:
                continue

            frame = frames.prepare_price_frame(df, symbol)
            if frame.empty:
                continue

            total_rows += store.write_price(conn, frame)
        except Exception:
            failures.append(symbol)
            logger.exception("迁移日线失败: %s", symbol)

        if index % 200 == 0:
            conn.commit()
            logger.info("日线进度 %d/%d，累计 %d 行，用时 %.0fs",
                        index, len(symbols), total_rows, time.time() - started)

    conn.commit()
    return {"symbols": len(symbols), "rows": total_rows, "failures": failures}


def migrate_etf(conn: sqlite3.Connection) -> dict:
    """把 data/a/etf/price/*.csv 迁移进 etf_daily 表。"""
    files = sorted(LEGACY_ETF_PRICE_DIR.glob("etf_*.csv")) if LEGACY_ETF_PRICE_DIR.is_dir() else []
    total_rows = 0
    symbols = []
    for path in files:
        symbol = path.stem[len("etf_"):]
        try:
            frame = frames.prepare_etf_frame(pd.read_csv(path), symbol)
            if frame.empty:
                continue
            total_rows += store.write_etf_price(conn, frame)
            symbols.append(symbol)
        except Exception:
            logger.exception("迁移 ETF 失败: %s", path.name)
    conn.commit()
    return {"symbols": len(symbols), "rows": total_rows}


# --------------------------------------------------------------------------
# 基本面
# --------------------------------------------------------------------------
def migrate_fundamental(conn: sqlite3.Connection, src_dir: Path | None = None) -> dict:
    """把季度三表合并后写入 fundamental 表。"""
    src = Path(src_dir) if src_dir else LEGACY_JIBENMIAN_DIR
    if not src.is_dir():
        return {"seasons": 0, "rows": 0, "message": f"目录不存在: {src}"}

    seasons = sorted({p.stem.split("_")[1] for p in src.glob("zcfz_*.csv")})
    done = set()
    if store.table_exists(conn, schema.TABLE_FUNDAMENTAL):
        done = {row[0] for row in conn.execute(f"SELECT DISTINCT season FROM {schema.TABLE_FUNDAMENTAL}")}

    total_rows = 0
    processed = []
    for season in seasons:
        if int(season) in done:
            continue

        frames = {}
        complete = True
        for table in ("zcfz", "lrb", "xjll"):
            path = src / f"{table}_{season}.csv"
            if not path.is_file():
                complete = False
                break
            df = pd.read_csv(path).rename(columns=schema.FUNDAMENTAL_COLUMN_MAP[table])
            keep = [c for c in schema.FUNDAMENTAL_COLUMN_MAP[table].values() if c in df.columns]
            frames[table] = df.loc[:, keep]

        if not complete:
            logger.warning("季度 %s 三表不全，跳过", season)
            continue

        # 与重构前的 pd.merge(on='股票代码') 默认内连接保持一致：
        # 只有三张表都出现的股票才进入基本面表
        merged = frames["zcfz"]
        merged = merged.merge(frames["lrb"], on="symbol", how="inner")
        merged = merged.merge(frames["xjll"], on="symbol", how="inner")

        merged["symbol"] = _normalize_symbol(merged["symbol"])
        merged["season"] = int(season)
        merged = _to_numeric(merged, schema.FUNDAMENTAL_NUMERIC_COLUMNS)
        for column in schema.FUNDAMENTAL_TEXT_COLUMNS:
            if column not in merged.columns:
                merged[column] = None
            merged[column] = merged[column].astype(object).where(pd.notnull(merged[column]), None)

        total_rows += store.write_fundamental(conn, merged)
        processed.append(season)
        conn.commit()

    return {"seasons": len(processed), "rows": total_rows}


# --------------------------------------------------------------------------
# 财务指标
# --------------------------------------------------------------------------
def migrate_financial(conn: sqlite3.Connection, src_dir: Path | None = None, *, limit: int | None = None) -> dict:
    """把单股财务指标 CSV 迁移进 financial_indicator 表（只保留精选列）。"""
    src = Path(src_dir) if src_dir else LEGACY_FINANCIAL_DIR
    if not src.is_dir():
        return {"symbols": 0, "rows": 0, "message": f"目录不存在: {src}"}

    files = sorted(src.glob("financial_report_*.csv"))
    done = store.existing_symbols(conn, schema.TABLE_FINANCIAL)
    files = [p for p in files if p.stem.replace("financial_report_", "") not in done]
    if limit:
        files = files[:limit]

    total_rows = 0
    failures: list[str] = []
    for index, path in enumerate(files, 1):
        symbol = path.stem.replace("financial_report_", "")
        try:
            frame = frames.prepare_financial_frame(pd.read_csv(path), symbol)
            if frame.empty:
                continue
            total_rows += store.write_financial(conn, frame)
        except Exception:
            failures.append(symbol)
            logger.exception("迁移财务指标失败: %s", symbol)

        if index % 300 == 0:
            conn.commit()
            logger.info("财务指标进度 %d/%d，累计 %d 行", index, len(files), total_rows)

    conn.commit()
    return {"symbols": len(files), "rows": total_rows, "failures": failures}


# --------------------------------------------------------------------------
# 交易记录
# --------------------------------------------------------------------------
def migrate_trade_records(conn: sqlite3.Connection, csv_path: Path | None = None) -> dict:
    """把 trade/records.csv 迁移进 trade_record 表。"""
    path = Path(csv_path) if csv_path else TRADE_RECORD_CSV
    if not path.is_file():
        return {"rows": 0, "message": f"文件不存在: {path}"}
    if store.table_count(conn, schema.TABLE_TRADE_RECORD) > 0:
        return {"rows": 0, "message": "trade_record 已有数据，跳过"}

    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(columns={"stockId": "symbol", "fitler": "filter_type"})
    if "note" not in df.columns:
        df["note"] = None
    df["symbol"] = _normalize_symbol(df["symbol"])
    df["date"] = df["date"].astype(str)

    rows = [(r.symbol, r.date, getattr(r, "filter_type", None), getattr(r, "note", None))
            for r in df.itertuples(index=False) if r.symbol and r.symbol != "000nan"]
    conn.executemany(
        f"INSERT INTO {schema.TABLE_TRADE_RECORD} (symbol, date, filter_type, note) VALUES (?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    return {"rows": len(rows)}


# --------------------------------------------------------------------------
# 归档与清理
# --------------------------------------------------------------------------
def _move_tree(src: Path, dst: Path) -> None:
    """把 src 整体移动到 dst。

    优先用 Path.rename（同盘符下是原地改名，不产生复制），
    失败再退回 shutil.move。受限环境下 shutil.move 的「复制后删除」可能因
    删除被拒而中途失败，rename 可以避开这一点。
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        src.rename(dst)
        return
    except OSError as exc:
        logger.debug("rename 失败（%s），退回 shutil.move", exc)
    shutil.move(str(src), str(dst))


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def archive_originals(*, dry_run: bool = False) -> dict:
    """把原始 CSV 移动到 data/original/（保留一份，不复制）。"""
    plan = [
        (LEGACY_JIBENMIAN_DIR, ORIGINAL_JIBENMIAN_DIR),
        (LEGACY_FINANCIAL_DIR, ORIGINAL_FINANCIAL_DIR),
        (LEGACY_ETF_DIR, ORIGINAL_ETF_DIR),
    ]
    for name in LEGACY_STATEMENT_DIRS:
        plan.append((DATA_DIR / "a" / "stock" / name, ORIGINAL_STATEMENT_DIR / name))

    moved = {}
    for src, dst in plan:
        if not src.exists():
            continue
        size = _dir_size(src)
        moved[str(src.relative_to(DATA_DIR))] = size
        if dry_run:
            continue
        try:
            if dst.exists():
                # 目标已存在：逐个文件合并，避免整体覆盖
                for item in src.iterdir():
                    target = dst / item.name
                    if target.exists():
                        logger.warning("目标已存在，跳过: %s", target)
                        continue
                    _move_tree(item, target)
                try:
                    src.rmdir()
                except OSError:
                    logger.warning("目录非空，保留: %s", src)
            else:
                _move_tree(src, dst)
            logger.info("归档 %s -> %s (%.1f MB)", src, dst, size / 1048576)
        except Exception:
            logger.exception("归档失败（保留原目录）: %s", src)

    return moved


# --------------------------------------------------------------------------
# 股票列表
# --------------------------------------------------------------------------
def migrate_stock_list(conn: sqlite3.Connection) -> dict:
    """从 fundamental 表提取股票代码与简称，写入 stock_list。"""
    if not store.table_exists(conn, schema.TABLE_FUNDAMENTAL):
        return {"rows": 0}
    df = pd.read_sql_query(
        f"SELECT symbol, MAX(name) AS name FROM {schema.TABLE_FUNDAMENTAL} GROUP BY symbol", conn
    )
    if df.empty:
        return {"rows": 0}
    df["source"] = "jibenmian"
    rows = store.write_stock_list(conn, df)
    conn.commit()  # 必须显式提交：连接关闭时未提交的事务会回滚
    return {"rows": rows}


# --------------------------------------------------------------------------
# 总入口
# --------------------------------------------------------------------------
def run_all(
    conn: sqlite3.Connection,
    *,
    price_limit: int | None = None,
    financial_limit: int | None = None,
    manage_indexes: bool = True,
) -> dict:
    """按顺序执行全部迁移。可重复调用（自动跳过已迁移部分）。"""
    if manage_indexes:
        store.drop_indexes(conn)
        logger.info("已暂时删除二级索引以加速导入")

    results = {
        "prices": migrate_prices(conn, limit=price_limit),
        "etf": migrate_etf(conn),
        "fundamental": migrate_fundamental(conn),
    }

    if manage_indexes:
        store.create_indexes(conn)

    results["financial"] = migrate_financial(conn, limit=financial_limit)
    results["records"] = migrate_trade_records(conn)
    results["stock_list"] = migrate_stock_list(conn)
    results["stats"] = store.stats(conn)
    return results

def cleanup_sources(*, dry_run: bool = True) -> dict:
    """删除已入库的行情 CSV 与重复副本（不可逆）。

    删除对象：
        data/a/stock/price/   已进 daily_price
        data/a/stock/temp/    价格文件的重复副本
        data/a/stock/price.zip 第三方打包副本
        data/a/etf/price/     已进 etf_daily
    """
    targets = [LEGACY_PRICE_DIR, LEGACY_TEMP_DIR, LEGACY_ETF_PRICE_DIR, LEGACY_PRICE_ZIP]
    freed = {}
    for target in targets:
        if not target.exists():
            continue
        size = _dir_size(target)
        freed[str(target.relative_to(DATA_DIR))] = size
        if dry_run:
            logger.info("[dry-run] 将删除 %s (%.1f MB)", target, size / 1048576)
            continue
        try:
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            logger.info("已删除 %s (%.1f MB)", target, size / 1048576)
        except Exception:
            logger.exception("删除失败: %s", target)
            freed.pop(str(target.relative_to(DATA_DIR)), None)

    # 清理空的 data/a 目录树
    if not dry_run:
        for candidate in (DATA_DIR / "a" / "stock", DATA_DIR / "a" / "etf", DATA_DIR / "a"):
            try:
                if candidate.is_dir() and not any(candidate.iterdir()):
                    candidate.rmdir()
            except OSError:
                pass
    return freed
