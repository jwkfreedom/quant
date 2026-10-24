"""资产库的 SQLite 存取层。

只做「建表 + 增删改查」，业务规则（买卖、成本、风险统计）在 quant.portfolio.service。
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from quant.config import PORTFOLIO_DB_PATH
from quant.portfolio import schema

logger = logging.getLogger(__name__)


def today() -> str:
    """今天的 ISO 日期字符串。"""
    return date.today().isoformat()


# --------------------------------------------------------------------------
# 连接与建表
# --------------------------------------------------------------------------
def connect(path: Path | str | None = None, *, create: bool = True) -> sqlite3.Connection:
    """打开资产库连接（不会自动建表）。"""
    db_path = Path(path) if path is not None else PORTFOLIO_DB_PATH
    if create:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


@contextmanager
def open_db(path: Path | str | None = None, *, create: bool = True):
    """上下文管理器形式的连接。"""
    conn = connect(path, create=create)
    try:
        yield conn
    finally:
        conn.close()


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """给旧库补新列（CREATE TABLE IF NOT EXISTS 不会改已存在的表）。"""
    columns = _table_columns(conn, schema.TABLE_DIVIDEND)
    if "report_period" not in columns:
        conn.execute(
            f"ALTER TABLE {schema.TABLE_DIVIDEND} ADD COLUMN report_period TEXT"
        )
        logger.info("资产库迁移：%s 新增 report_period 列", schema.TABLE_DIVIDEND)


def ensure_schema(conn: sqlite3.Connection) -> None:
    """建表 + 索引 + 旧库迁移（幂等）。"""
    conn.executescript(schema.DDL)
    conn.executescript(schema.INDEXES)
    _migrate_schema(conn)
    conn.execute(
        f"INSERT INTO {schema.TABLE_META} (key, value) VALUES (?, ?) "
        f"ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        ("schema_version", str(schema.SCHEMA_VERSION)),
    )
    conn.commit()


def init_db(path: Path | str | None = None) -> Path:
    """建库/建表（幂等），返回数据库路径。"""
    db_path = Path(path) if path is not None else PORTFOLIO_DB_PATH
    with open_db(db_path, create=True) as conn:
        ensure_schema(conn)
    logger.info("资产库就绪: %s", db_path)
    return db_path


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _to_dicts(rows) -> list[dict]:
    return [dict(row) for row in rows]


def _safe_number(value, default: float = 0.0) -> float:
    """NaN/None/非法值一律转成 default（NaN 写进 SQLite 会变成 NULL）。"""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if result != result:
        return default
    return result


# --------------------------------------------------------------------------
# 资产账户（人）
# --------------------------------------------------------------------------
def create_owner(conn: sqlite3.Connection, name: str, note: str = "") -> int:
    cursor = conn.execute(
        f"INSERT INTO {schema.TABLE_OWNER} (name, note, created_at) VALUES (?, ?, ?)",
        (name.strip(), note, today()),
    )
    conn.commit()
    return int(cursor.lastrowid)


def list_owners(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(f"SELECT * FROM {schema.TABLE_OWNER} ORDER BY id").fetchall()
    return _to_dicts(rows)


def get_owner(conn: sqlite3.Connection, owner_id: int) -> dict | None:
    row = conn.execute(f"SELECT * FROM {schema.TABLE_OWNER} WHERE id = ?", (owner_id,)).fetchone()
    return dict(row) if row else None


def find_owner(conn: sqlite3.Connection, name: str) -> dict | None:
    row = conn.execute(f"SELECT * FROM {schema.TABLE_OWNER} WHERE name = ?", (name,)).fetchone()
    return dict(row) if row else None


def update_owner(conn: sqlite3.Connection, owner_id: int, *, name: str | None = None,
                 note: str | None = None) -> None:
    sets, params = [], []
    if name is not None:
        sets.append("name = ?")
        params.append(name.strip())
    if note is not None:
        sets.append("note = ?")
        params.append(note)
    if not sets:
        return
    params.append(owner_id)
    conn.execute(f"UPDATE {schema.TABLE_OWNER} SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()


def delete_owner(conn: sqlite3.Connection, owner_id: int) -> None:
    """删除资产账户（级联删除其下资金账户、持仓、流水）。"""
    conn.execute(f"DELETE FROM {schema.TABLE_OWNER} WHERE id = ?", (owner_id,))
    conn.commit()


# --------------------------------------------------------------------------
# 资金账户
# --------------------------------------------------------------------------
def create_account(conn: sqlite3.Connection, owner_id: int, name: str, *,
                   account_type: str = "securities", currency: str = "CNY",
                   note: str = "") -> int:
    cursor = conn.execute(
        f"INSERT INTO {schema.TABLE_ACCOUNT} "
        f"(owner_id, name, account_type, currency, note, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (owner_id, name.strip(), account_type, currency, note, today()),
    )
    conn.commit()
    return int(cursor.lastrowid)


def list_accounts(conn: sqlite3.Connection, owner_id: int | None = None) -> list[dict]:
    if owner_id is None:
        rows = conn.execute(f"SELECT * FROM {schema.TABLE_ACCOUNT} ORDER BY owner_id, id").fetchall()
    else:
        rows = conn.execute(
            f"SELECT * FROM {schema.TABLE_ACCOUNT} WHERE owner_id = ? ORDER BY id", (owner_id,)
        ).fetchall()
    return _to_dicts(rows)


def get_account(conn: sqlite3.Connection, account_id: int) -> dict | None:
    row = conn.execute(f"SELECT * FROM {schema.TABLE_ACCOUNT} WHERE id = ?", (account_id,)).fetchone()
    return dict(row) if row else None


def find_account(conn: sqlite3.Connection, name: str, owner_id: int | None = None) -> dict | None:
    if owner_id is None:
        row = conn.execute(f"SELECT * FROM {schema.TABLE_ACCOUNT} WHERE name = ?", (name,)).fetchone()
    else:
        row = conn.execute(
            f"SELECT * FROM {schema.TABLE_ACCOUNT} WHERE name = ? AND owner_id = ?",
            (name, owner_id),
        ).fetchone()
    return dict(row) if row else None


def update_account(conn: sqlite3.Connection, account_id: int, **fields) -> None:
    allowed = {"name", "account_type", "currency", "note"}
    sets, params = [], []
    for key, value in fields.items():
        if key in allowed and value is not None:
            sets.append(f"{key} = ?")
            params.append(value)
    if not sets:
        return
    params.append(account_id)
    conn.execute(f"UPDATE {schema.TABLE_ACCOUNT} SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()


def delete_account(conn: sqlite3.Connection, account_id: int) -> None:
    """删除资金账户（级联删除其持仓与流水）。"""
    conn.execute(f"DELETE FROM {schema.TABLE_ACCOUNT} WHERE id = ?", (account_id,))
    conn.commit()


# --------------------------------------------------------------------------
# 产品
# --------------------------------------------------------------------------
def find_instrument(conn: sqlite3.Connection, kind: str, market: str,
                    symbol: str) -> dict | None:
    row = conn.execute(
        f"SELECT * FROM {schema.TABLE_INSTRUMENT} WHERE kind = ? AND market = ? AND symbol = ?",
        (kind, market, symbol),
    ).fetchone()
    return dict(row) if row else None


def get_instrument(conn: sqlite3.Connection, instrument_id: int) -> dict | None:
    row = conn.execute(
        f"SELECT * FROM {schema.TABLE_INSTRUMENT} WHERE id = ?", (instrument_id,)
    ).fetchone()
    return dict(row) if row else None


def get_or_create_instrument(conn: sqlite3.Connection, kind: str, market: str, symbol: str, *,
                             name: str = "", currency: str | None = None,
                             risk: str | None = None, price_source: str = schema.PRICE_SOURCE_AUTO,
                             note: str = "") -> int:
    """按 (类型, 市场, 代码) 取或建产品；已存在时不覆盖其风险等级等设置。"""
    existing = find_instrument(conn, kind, market, symbol)
    if existing:
        return int(existing["id"])

    if kind not in schema.KINDS:
        raise ValueError(f"未知产品类型: {kind}")
    if market not in schema.MARKETS:
        raise ValueError(f"未知市场: {market}")

    currency = currency or schema.MARKET_CURRENCY.get(market, "CNY")
    risk = risk or schema.DEFAULT_RISK.get(kind, schema.RISK_MID)
    if risk not in schema.RISKS:
        raise ValueError(f"未知风险等级: {risk}")

    cursor = conn.execute(
        f"INSERT INTO {schema.TABLE_INSTRUMENT} "
        f"(kind, market, symbol, name, currency, risk, price_source, note, created_at) "
        f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (kind, market, symbol, name, currency, risk, price_source, note, today()),
    )
    conn.commit()
    return int(cursor.lastrowid)


def cash_instrument(conn: sqlite3.Connection, currency: str = "CNY") -> int:
    """取或建该币种的现金产品。"""
    market = schema.CURRENCY_MARKET.get(currency, schema.MARKET_CN)
    instrument_id = get_or_create_instrument(
        conn, schema.KIND_CASH, market, schema.CASH_SYMBOL,
        name=f"{schema.CURRENCY_NAMES.get(currency, currency)}现金",
        currency=currency, risk=schema.RISK_LOW,
    )
    # 现金的价格恒为 1
    conn.execute(
        f"UPDATE {schema.TABLE_INSTRUMENT} SET price_source = ?, manual_price = 1.0 WHERE id = ?",
        (schema.PRICE_SOURCE_MANUAL, instrument_id),
    )
    conn.commit()
    return instrument_id


def list_instruments(conn: sqlite3.Connection, kind: str | None = None) -> list[dict]:
    if kind is None:
        rows = conn.execute(f"SELECT * FROM {schema.TABLE_INSTRUMENT} ORDER BY id").fetchall()
    else:
        rows = conn.execute(
            f"SELECT * FROM {schema.TABLE_INSTRUMENT} WHERE kind = ? ORDER BY id", (kind,)
        ).fetchall()
    return _to_dicts(rows)


def update_instrument(conn: sqlite3.Connection, instrument_id: int, **fields) -> None:
    allowed = {"name", "risk", "currency", "price_source", "manual_price", "price_date", "note"}
    sets, params = [], []
    for key, value in fields.items():
        if key in allowed:
            sets.append(f"{key} = ?")
            params.append(value)
    if not sets:
        return
    params.append(instrument_id)
    conn.execute(f"UPDATE {schema.TABLE_INSTRUMENT} SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()


def set_manual_price(conn: sqlite3.Connection, instrument_id: int, price: float,
                     price_date: str | None = None) -> None:
    update_instrument(conn, instrument_id, price_source=schema.PRICE_SOURCE_MANUAL,
                      manual_price=float(price), price_date=price_date or today())


# --------------------------------------------------------------------------
# 持仓
# --------------------------------------------------------------------------
def get_holding(conn: sqlite3.Connection, account_id: int,
                instrument_id: int) -> dict | None:
    row = conn.execute(
        f"SELECT * FROM {schema.TABLE_HOLDING} WHERE account_id = ? AND instrument_id = ?",
        (account_id, instrument_id),
    ).fetchone()
    return dict(row) if row else None


def upsert_holding(conn: sqlite3.Connection, account_id: int, instrument_id: int, *,
                   quantity: float, cost_price: float, opened_at: str | None = None) -> None:
    existing = get_holding(conn, account_id, instrument_id)
    if existing is None:
        conn.execute(
            f"INSERT INTO {schema.TABLE_HOLDING} "
            f"(account_id, instrument_id, quantity, cost_price, opened_at, updated_at) "
            f"VALUES (?, ?, ?, ?, ?, ?)",
            (account_id, instrument_id, float(quantity), float(cost_price),
             opened_at or today(), today()),
        )
    else:
        conn.execute(
            f"UPDATE {schema.TABLE_HOLDING} SET quantity = ?, cost_price = ?, updated_at = ?, "
            f"opened_at = COALESCE(opened_at, ?) WHERE account_id = ? AND instrument_id = ?",
            (float(quantity), float(cost_price), today(), opened_at or today(),
             account_id, instrument_id),
        )
    conn.commit()


def delete_holding(conn: sqlite3.Connection, account_id: int, instrument_id: int) -> None:
    conn.execute(
        f"DELETE FROM {schema.TABLE_HOLDING} WHERE account_id = ? AND instrument_id = ?",
        (account_id, instrument_id),
    )
    conn.commit()


def list_holdings(conn: sqlite3.Connection, account_id: int | None = None) -> list[dict]:
    """持仓（带产品信息）。数量为 0 的持仓不返回，负数量（如现金透支）保留。"""
    sql = (
        f"SELECT h.account_id, h.instrument_id, h.quantity, h.cost_price, h.opened_at, "
        f"       i.kind, i.market, i.symbol, i.name, i.currency, i.risk, "
        f"       i.price_source, i.manual_price, i.price_date "
        f"FROM {schema.TABLE_HOLDING} h "
        f"JOIN {schema.TABLE_INSTRUMENT} i ON i.id = h.instrument_id "
        f"WHERE ABS(h.quantity) > 1e-9"
    )
    params: list = []
    if account_id is not None:
        sql += " AND h.account_id = ?"
        params.append(account_id)
    sql += " ORDER BY h.account_id, i.kind, i.symbol"
    return _to_dicts(conn.execute(sql, params).fetchall())


# --------------------------------------------------------------------------
# 交易流水
# --------------------------------------------------------------------------
def add_txn(conn: sqlite3.Connection, account_id: int, instrument_id: int, *,
            trade_date: str, action: str, quantity: float, price: float = 0.0,
            fee: float = 0.0, realized_pnl: float | None = None, note: str = "") -> int:
    if action not in schema.ACTIONS:
        raise ValueError(f"未知操作: {action}")
    cursor = conn.execute(
        f"INSERT INTO {schema.TABLE_TXN} "
        f"(account_id, instrument_id, trade_date, action, quantity, price, fee, "
        f" realized_pnl, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (account_id, instrument_id, trade_date, action, float(quantity), float(price),
         float(fee), realized_pnl, note, today()),
    )
    conn.commit()
    return int(cursor.lastrowid)


def get_txn(conn: sqlite3.Connection, txn_id: int) -> dict | None:
    """按 id 取一条流水（带产品与账户信息）。"""
    row = conn.execute(
        f"SELECT t.*, i.kind, i.market, i.symbol, i.name, i.currency, "
        f"       a.name AS account_name "
        f"FROM {schema.TABLE_TXN} t "
        f"JOIN {schema.TABLE_INSTRUMENT} i ON i.id = t.instrument_id "
        f"JOIN {schema.TABLE_ACCOUNT} a ON a.id = t.account_id "
        f"WHERE t.id = ?",
        (txn_id,),
    ).fetchone()
    return dict(row) if row else None


def list_txns(conn: sqlite3.Connection, *, account_id: int | None = None,
              instrument_id: int | None = None, start: str | None = None,
              end: str | None = None, limit: int | None = None) -> list[dict]:
    sql = (
        f"SELECT t.*, i.kind, i.market, i.symbol, i.name, i.currency, a.name AS account_name "
        f"FROM {schema.TABLE_TXN} t "
        f"JOIN {schema.TABLE_INSTRUMENT} i ON i.id = t.instrument_id "
        f"JOIN {schema.TABLE_ACCOUNT} a ON a.id = t.account_id WHERE 1=1"
    )
    params: list = []
    if account_id is not None:
        sql += " AND t.account_id = ?"
        params.append(account_id)
    if instrument_id is not None:
        sql += " AND t.instrument_id = ?"
        params.append(instrument_id)
    if start is not None:
        sql += " AND t.trade_date >= ?"
        params.append(start)
    if end is not None:
        sql += " AND t.trade_date <= ?"
        params.append(end)
    sql += " ORDER BY t.trade_date DESC, t.id DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return _to_dicts(conn.execute(sql, params).fetchall())


def delete_txn(conn: sqlite3.Connection, txn_id: int) -> None:
    conn.execute(f"DELETE FROM {schema.TABLE_TXN} WHERE id = ?", (txn_id,))
    conn.commit()


# --------------------------------------------------------------------------
# 汇率
# --------------------------------------------------------------------------
def upsert_fx(conn: sqlite3.Connection, rate_date: str, currency: str, rate: float,
              source: str = "") -> None:
    conn.execute(
        f"INSERT INTO {schema.TABLE_FX} (date, currency, rate, source) VALUES (?, ?, ?, ?) "
        f"ON CONFLICT(date, currency) DO UPDATE SET rate = excluded.rate, source = excluded.source",
        (rate_date, currency, float(rate), source),
    )
    conn.commit()


def get_fx(conn: sqlite3.Connection, currency: str, rate_date: str | None = None) -> float:
    """取 <= rate_date 的最近一条汇率；CNY 恒为 1；查不到抛 KeyError。"""
    if currency == schema.BASE_CURRENCY:
        return 1.0
    if rate_date is None:
        row = conn.execute(
            f"SELECT rate FROM {schema.TABLE_FX} WHERE currency = ? ORDER BY date DESC LIMIT 1",
            (currency,),
        ).fetchone()
    else:
        row = conn.execute(
            f"SELECT rate FROM {schema.TABLE_FX} WHERE currency = ? AND date <= ? "
            f"ORDER BY date DESC LIMIT 1",
            (currency, rate_date),
        ).fetchone()
    if row is None:
        raise KeyError(f"缺少汇率: {currency} @ {rate_date or '最新'}")
    return float(row["rate"])


def list_fx(conn: sqlite3.Connection, currency: str | None = None,
            start: str | None = None, end: str | None = None) -> list[dict]:
    sql = f"SELECT * FROM {schema.TABLE_FX} WHERE 1=1"
    params: list = []
    if currency:
        sql += " AND currency = ?"
        params.append(currency)
    if start:
        sql += " AND date >= ?"
        params.append(start)
    if end:
        sql += " AND date <= ?"
        params.append(end)
    sql += " ORDER BY date DESC, currency"
    return _to_dicts(conn.execute(sql, params).fetchall())


# --------------------------------------------------------------------------
# 分红
# --------------------------------------------------------------------------
def upsert_dividend(conn: sqlite3.Connection, instrument_id: int, *, ex_date: str,
                    pay_date: str | None = None, report_period: str | None = None,
                    cash_per_share: float = 0.0,
                    stock_per_share: float = 0.0, currency: str = "CNY",
                    source: str = schema.DIVIDEND_SOURCE_AUTO, note: str = "") -> int:
    cursor = conn.execute(
        f"INSERT INTO {schema.TABLE_DIVIDEND} "
        f"(instrument_id, ex_date, pay_date, report_period, cash_per_share, "
        f" stock_per_share, currency, source, recorded, note, fetched_at) "
        f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?) "
        f"ON CONFLICT(instrument_id, ex_date) DO UPDATE SET "
        f"pay_date = excluded.pay_date, "
        f"report_period = COALESCE(excluded.report_period, report_period), "
        f"cash_per_share = excluded.cash_per_share, "
        f"stock_per_share = excluded.stock_per_share, currency = excluded.currency, "
        f"note = excluded.note, fetched_at = excluded.fetched_at",
        (instrument_id, ex_date, pay_date, report_period,
         _safe_number(cash_per_share), _safe_number(stock_per_share),
         currency, source, note, today()),
    )
    conn.commit()
    row = conn.execute(
        f"SELECT id FROM {schema.TABLE_DIVIDEND} WHERE instrument_id = ? AND ex_date = ?",
        (instrument_id, ex_date),
    ).fetchone()
    return int(row["id"])


def list_dividends(conn: sqlite3.Connection, *, instrument_id: int | None = None,
                   start: str | None = None, end: str | None = None) -> list[dict]:
    sql = (
        f"SELECT d.*, i.kind, i.market, i.symbol, i.name, "
        f"       i.currency AS instrument_currency "
        f"FROM {schema.TABLE_DIVIDEND} d "
        f"JOIN {schema.TABLE_INSTRUMENT} i ON i.id = d.instrument_id WHERE 1=1"
    )
    params: list = []
    if instrument_id is not None:
        sql += " AND d.instrument_id = ?"
        params.append(instrument_id)
    if start:
        sql += " AND d.ex_date >= ?"
        params.append(start)
    if end:
        sql += " AND d.ex_date <= ?"
        params.append(end)
    sql += " ORDER BY d.ex_date DESC, d.id DESC"
    return _to_dicts(conn.execute(sql, params).fetchall())


def mark_dividend_recorded(conn: sqlite3.Connection, dividend_id: int,
                           recorded: bool = True) -> None:
    conn.execute(
        f"UPDATE {schema.TABLE_DIVIDEND} SET recorded = ? WHERE id = ?",
        (1 if recorded else 0, dividend_id),
    )
    conn.commit()


def delete_dividend(conn: sqlite3.Connection, dividend_id: int) -> None:
    conn.execute(f"DELETE FROM {schema.TABLE_DIVIDEND} WHERE id = ?", (dividend_id,))
    conn.commit()
