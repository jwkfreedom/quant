"""SQLite 存储层：建表、写入、查询。

数据库文件：`quant.config.DB_PATH`（默认 `data/quant.db`）。
所有表使用 WITHOUT ROWID + (主键) 形式，避免额外的 rowid 与索引开销。

TODO(2.3): 增加按日期区间/多股票的批量查询封装，供选股过滤链使用。
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterable, Sequence
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

from quant.config import DB_PATH
from quant.data import schema

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# 建表语句
# --------------------------------------------------------------------------
_DDL = f"""
CREATE TABLE IF NOT EXISTS {schema.TABLE_META} (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS {schema.TABLE_STOCK_LIST} (
    symbol     TEXT PRIMARY KEY,
    name       TEXT,
    source     TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS {schema.TABLE_DAILY_PRICE} (
    symbol        TEXT    NOT NULL,
    date          TEXT    NOT NULL,
    idate         INTEGER NOT NULL,
    open          REAL, high REAL, low REAL, close REAL,
    open_qfq      REAL, high_qfq REAL, low_qfq REAL, close_qfq REAL,
    volume        REAL, turnover REAL, amplitude REAL,
    pct_change    REAL, price_change REAL, turnover_rate REAL,
    PRIMARY KEY (symbol, date)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS {schema.TABLE_ETF_DAILY} (
    symbol        TEXT    NOT NULL,
    date          TEXT    NOT NULL,
    idate         INTEGER NOT NULL,
    open_qfq      REAL, high_qfq REAL, low_qfq REAL, close_qfq REAL,
    volume        REAL, turnover REAL, amplitude REAL,
    pct_change    REAL, price_change REAL, turnover_rate REAL,
    PRIMARY KEY (symbol, date)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS {schema.TABLE_FUNDAMENTAL} (
    symbol TEXT NOT NULL,
    season INTEGER NOT NULL,
    {", ".join(f"{c} TEXT" for c in schema.FUNDAMENTAL_TEXT_COLUMNS)},
    {", ".join(f"{c} REAL" for c in schema.FUNDAMENTAL_NUMERIC_COLUMNS)},
    PRIMARY KEY (symbol, season)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS {schema.TABLE_FUNDAMENTAL_GROWTH} (
    symbol TEXT NOT NULL,
    season INTEGER NOT NULL,
    pre_year_income REAL, season_income REAL, season_income_growth REAL,
    pre_year_profit REAL, season_profit REAL, season_profit_growth REAL,
    PRIMARY KEY (symbol, season)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS {schema.TABLE_FINANCIAL} (
    symbol TEXT NOT NULL,
    report_date TEXT NOT NULL,
    idate INTEGER NOT NULL,
    {", ".join(f"{c} REAL" for c in schema.FINANCIAL_VALUE_COLUMNS)},
    PRIMARY KEY (symbol, report_date)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS {schema.TABLE_TRADE_RECORD} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT,
    date TEXT,
    filter_type INTEGER,
    note TEXT
);
"""

_INDEXES = f"""
CREATE INDEX IF NOT EXISTS idx_daily_price_idate ON {schema.TABLE_DAILY_PRICE} (idate);
CREATE INDEX IF NOT EXISTS idx_fundamental_season ON {schema.TABLE_FUNDAMENTAL} (season);
CREATE INDEX IF NOT EXISTS idx_growth_season ON {schema.TABLE_FUNDAMENTAL_GROWTH} (season);
CREATE INDEX IF NOT EXISTS idx_financial_idate ON {schema.TABLE_FINANCIAL} (idate);
"""


# --------------------------------------------------------------------------
# 连接
# --------------------------------------------------------------------------
def connect(db_path: Path | None = None, *, create: bool = False) -> sqlite3.Connection:
    """打开数据库连接（默认 `DB_PATH`）。

    参数 create=True 时会自动创建父目录与数据库文件。
    """
    path = Path(db_path) if db_path is not None else DB_PATH
    if create:
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


@contextmanager
def open_db(db_path: Path | None = None, *, create: bool = False):
    """上下文管理器形式的连接。"""
    conn = connect(db_path, create=create)
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: Path | None = None, *, with_indexes: bool = True) -> Path:
    """建表（幂等），返回数据库路径。"""
    path = Path(db_path) if db_path is not None else DB_PATH
    with open_db(path, create=True) as conn:
        conn.executescript(_DDL)
        if with_indexes:
            conn.executescript(_INDEXES)
        conn.execute(
            f"INSERT INTO {schema.TABLE_META} (key, value) VALUES (?, ?) "
            f"ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            ("schema_version", str(schema.SCHEMA_VERSION)),
        )
        conn.commit()
    logger.info("数据库就绪: %s", path)
    return path


def drop_indexes(conn: sqlite3.Connection) -> None:
    """批量导入前删除索引（导入完成后重建）。"""
    for name in ("idx_daily_price_idate", "idx_fundamental_season", "idx_growth_season", "idx_financial_idate"):
        conn.execute(f"DROP INDEX IF EXISTS {name}")
    conn.commit()


def create_indexes(conn: sqlite3.Connection) -> None:
    """重建索引。"""
    conn.executescript(_INDEXES)
    conn.commit()


# --------------------------------------------------------------------------
# meta
# --------------------------------------------------------------------------
def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        f"INSERT INTO {schema.TABLE_META} (key, value) VALUES (?, ?) "
        f"ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()


def get_meta(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = conn.execute(f"SELECT value FROM {schema.TABLE_META} WHERE key = ?", (key,)).fetchone()
    return row[0] if row else default


# --------------------------------------------------------------------------
# 写入
# --------------------------------------------------------------------------
def _insert_frame(conn: sqlite3.Connection, table: str, df: pd.DataFrame, columns: Sequence[str]) -> int:
    """把 DataFrame 的指定列批量写入表（INSERT OR REPLACE）。"""
    if df.empty:
        return 0
    placeholders = ", ".join("?" for _ in columns)
    sql = f"INSERT OR REPLACE INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"

    # 缺失的列补 None（例如可选的计算列），保证 SQL 列数一致
    frame = df.loc[:, [c for c in columns if c in df.columns]].copy()
    for column in columns:
        if column not in frame.columns:
            frame[column] = None
    frame = frame.loc[:, list(columns)]

    # sqlite3 不能绑定 numpy 标量（int64/float64），转成 Python 原生类型后再写入
    frame = frame.astype(object).where(pd.notnull(frame), None)
    rows = list(frame.itertuples(index=False, name=None))

    conn.executemany(sql, rows)
    return len(frame)


def write_price(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """写入日线。df 需含 symbol/date 及 PRICE_VALUE_COLUMNS。"""
    return _insert_frame(conn, schema.TABLE_DAILY_PRICE, df, ("symbol", "date", "idate", *schema.PRICE_VALUE_COLUMNS))


def write_etf_price(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """写入 ETF 日线。"""
    columns = ("symbol", "date", "idate", "open_qfq", "high_qfq", "low_qfq", "close_qfq",
               "volume", "turnover", "amplitude", "pct_change", "price_change", "turnover_rate")
    return _insert_frame(conn, schema.TABLE_ETF_DAILY, df, columns)


def write_fundamental(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """写入季度基本面。"""
    return _insert_frame(conn, schema.TABLE_FUNDAMENTAL, df, ("symbol", "season", *schema.FUNDAMENTAL_VALUE_COLUMNS))


def write_growth(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """写入单季增长。"""
    return _insert_frame(conn, schema.TABLE_FUNDAMENTAL_GROWTH, df, ("symbol", "season", *schema.GROWTH_VALUE_COLUMNS))


def write_financial(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """写入财务指标。"""
    return _insert_frame(conn, schema.TABLE_FINANCIAL, df, ("symbol", "report_date", "idate", *schema.FINANCIAL_VALUE_COLUMNS))


def write_stock_list(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """写入股票列表。df 需含 symbol，可选 name/source/updated_at。"""
    df = df.copy()
    if "name" not in df:
        df["name"] = None
    if "source" not in df:
        df["source"] = None
    if "updated_at" not in df:
        df["updated_at"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    return _insert_frame(conn, schema.TABLE_STOCK_LIST, df, ("symbol", "name", "source", "updated_at"))


# --------------------------------------------------------------------------
# 查询
# --------------------------------------------------------------------------
def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


def table_count(conn: sqlite3.Connection, table: str) -> int:
    if not table_exists(conn, table):
        return 0
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def stats(conn: sqlite3.Connection) -> dict[str, int]:
    """返回各表行数。"""
    return {table: table_count(conn, table) for table in schema.ALL_TABLES if table != schema.TABLE_META}


def existing_symbols(conn: sqlite3.Connection, table: str) -> set[str]:
    """返回表中已有的 symbol 集合（用于增量迁移/更新）。"""
    if not table_exists(conn, table):
        return set()
    return {row[0] for row in conn.execute(f"SELECT DISTINCT symbol FROM {table}")}


def read_price(conn: sqlite3.Connection, symbol: str, start: int | None = None, end: int | None = None) -> pd.DataFrame:
    """读取单只股票日线（按日期升序）。start/end 为 YYYYMMDD 整数。"""
    sql = f"SELECT * FROM {schema.TABLE_DAILY_PRICE} WHERE symbol = ?"
    params: list = [symbol]
    if start is not None:
        sql += " AND idate >= ?"
        params.append(int(start))
    if end is not None:
        sql += " AND idate <= ?"
        params.append(int(end))
    sql += " ORDER BY date"
    return pd.read_sql_query(sql, conn, params=params)


def last_price_date(conn: sqlite3.Connection, symbol: str) -> str | None:
    """返回某只股票在库中的最后交易日（YYYY-MM-DD）。"""
    row = conn.execute(
        f"SELECT MAX(date) FROM {schema.TABLE_DAILY_PRICE} WHERE symbol = ?", (symbol,)
    ).fetchone()
    return row[0] if row and row[0] else None


def read_fundamental(
    conn: sqlite3.Connection,
    start_season: int | None = None,
    end_season: int | None = None,
    symbols: Iterable[str] | None = None,
) -> pd.DataFrame:
    """读取季度基本面。"""
    sql = f"SELECT * FROM {schema.TABLE_FUNDAMENTAL} WHERE 1=1"
    params: list = []
    if start_season is not None:
        sql += " AND season >= ?"
        params.append(int(start_season))
    if end_season is not None:
        sql += " AND season <= ?"
        params.append(int(end_season))
    if symbols is not None:
        symbols = list(symbols)
        if not symbols:
            return pd.DataFrame()
        sql += f" AND symbol IN ({', '.join('?' for _ in symbols)})"
        params.extend(symbols)
    sql += " ORDER BY symbol, season"
    return pd.read_sql_query(sql, conn, params=params)


def read_growth(conn: sqlite3.Connection, start_season: int | None = None) -> pd.DataFrame:
    """读取单季增长表。"""
    sql = f"SELECT * FROM {schema.TABLE_FUNDAMENTAL_GROWTH}"
    params: list = []
    if start_season is not None:
        sql += " WHERE season >= ?"
        params.append(int(start_season))
    sql += " ORDER BY symbol, season"
    return pd.read_sql_query(sql, conn, params=params)


def read_financial(conn: sqlite3.Connection, symbol: str) -> pd.DataFrame:
    """读取单只股票的财务指标（按报告期升序）。"""
    sql = f"SELECT * FROM {schema.TABLE_FINANCIAL} WHERE symbol = ? ORDER BY report_date"
    return pd.read_sql_query(sql, conn, params=[symbol])


def read_etf_price(conn: sqlite3.Connection, symbol: str) -> pd.DataFrame:
    """读取单只 ETF 的日线。"""
    sql = f"SELECT * FROM {schema.TABLE_ETF_DAILY} WHERE symbol = ? ORDER BY date"
    return pd.read_sql_query(sql, conn, params=[symbol])
