"""统一查询 API —— 面向研究 / notebook / 选股过滤器的数据入口。

设计目标
--------
- **一次调用拿到一张可分析的表**：`snapshot()` 返回「一行一只股票」的横截面快照
  （最新行情 + 最近已披露季度基本面 + 最新财务指标 + 派生估值），选股链条直接基于它工作。
- **批量取数走 SQL**，不再逐只股票开连接。
- 所有函数都接受可选的 `conn`；不传时自己开一个短连接。

典型用法::

    from quant.query import snapshot, prices, growth

    df = snapshot()                      # 最新交易日全市场快照
    df = snapshot(as_of=20231229)        # 指定日期（YYYYMMDD）
    df = df[df["market_cap"] < 8e9]

    px = prices(["000001", "600519"], start=20230101)   # 多只股票日线（长表）
    g = growth(seasons=[20231231])                       # 指定季度的单季增长
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterable, Sequence

import pandas as pd

from quant.data import schema, store

logger = logging.getLogger(__name__)

#: IN (...) 子句的分片大小
_CHUNK = 500

#: snapshot 返回列的顺序
SNAPSHOT_COLUMNS: tuple[str, ...] = (
    "symbol", "name",
    "date", "idate", "close", "close_org", "close_qfq", "volume", "turnover",
    "pct_change", "turnover_rate",
    "season", "total_revenue", "total_revenue_yoy", "net_profit", "net_profit_yoy",
    "total_assets", "total_liabilities", "debt_ratio", "total_equity",
    "season_income", "season_income_growth", "season_profit", "season_profit_growth",
    "revenue_ttm", "net_profit_ttm",
    "report_date", "eps_ttm", "bvps_ttm", "roe", "gross_margin", "net_margin",
    "shares", "market_cap", "pe", "pb", "ps",
    "pe_pct_3y", "pe_pct_5y", "pe_pct_10y", "pe_pct_all", "pb_pct_10y", "ps_pct_10y",
)


# --------------------------------------------------------------------------
# 连接辅助
# --------------------------------------------------------------------------
class _Conn:
    """轻量连接包装：外部传入则复用，否则自建并在退出时关闭。"""

    def __init__(self, conn: sqlite3.Connection | None):
        self._external = conn
        self.conn: sqlite3.Connection | None = conn

    def __enter__(self) -> sqlite3.Connection:
        if self.conn is None:
            self.conn = store.connect()
            if not store.table_exists(self.conn, schema.TABLE_DAILY_PRICE):
                raise FileNotFoundError("数据库尚未初始化，请先运行 quant db-init 与 quant db-migrate")
        return self.conn

    def __exit__(self, *exc) -> None:
        if self._external is None and self.conn is not None:
            self.conn.close()


def _chunks(values: Sequence, size: int = _CHUNK):
    for start in range(0, len(values), size):
        yield values[start:start + size]


def _placeholders(values: Sequence) -> str:
    return ", ".join("?" for _ in values)


def _read_sql(conn: sqlite3.Connection, sql: str, params: Sequence | dict = ()) -> pd.DataFrame:
    """执行查询。

    注意：dict 参数（命名占位符）必须原样传给 pandas，
    一旦被 list() 转换就会变成「键的列表」，绑定到 :name 上得到错误结果。
    """
    if isinstance(params, dict):
        return pd.read_sql_query(sql, conn, params=params)
    return pd.read_sql_query(sql, conn, params=list(params))


# --------------------------------------------------------------------------
# 概况
# --------------------------------------------------------------------------
def latest_trading_date(conn: sqlite3.Connection | None = None, as_of: int | None = None) -> str | None:
    """返回不晚于 as_of 的最新交易日（YYYY-MM-DD）。"""
    with _Conn(conn) as active:
        sql = f"SELECT MAX(date) FROM {schema.TABLE_DAILY_PRICE}"
        params: list = []
        if as_of is not None:
            sql += " WHERE idate <= ?"
            params.append(int(as_of))
        row = active.execute(sql, params).fetchone()
        return row[0] if row else None


def latest_season(conn: sqlite3.Connection | None = None, as_of: int | None = None) -> int | None:
    """返回不晚于 as_of 的最新已披露季度（YYYYMMDD 整数）。"""
    with _Conn(conn) as active:
        sql = f"SELECT MAX(season) FROM {schema.TABLE_FUNDAMENTAL}"
        params: list = []
        if as_of is not None:
            sql += " WHERE season <= ?"
            params.append(int(as_of))
        row = active.execute(sql, params).fetchone()
        return row[0] if row else None


def summary(conn: sqlite3.Connection | None = None) -> dict:
    """数据概况：各表行数 + 覆盖区间。"""
    with _Conn(conn) as active:
        result = {"tables": store.stats(active)}
        row = active.execute(
            f"SELECT COUNT(DISTINCT symbol), MIN(date), MAX(date), COUNT(*) FROM {schema.TABLE_DAILY_PRICE}"
        ).fetchone()
        result["price"] = {"symbols": row[0], "start": row[1], "end": row[2], "rows": row[3]}
        row = active.execute(
            f"SELECT COUNT(DISTINCT symbol), COUNT(DISTINCT season), MIN(season), MAX(season) "
            f"FROM {schema.TABLE_FUNDAMENTAL}"
        ).fetchone()
        result["fundamental"] = {"symbols": row[0], "seasons": row[1], "start": row[2], "end": row[3]}
        return result


# --------------------------------------------------------------------------
# 横截面快照
# --------------------------------------------------------------------------
_SNAPSHOT_SQL = f"""
WITH last_price AS (
    -- close/close_qfq 为前复权（技术指标用），close_org 为不复权（市值/估值用）
    SELECT p.symbol, p.date, p.idate, p.close_qfq AS close, p.close AS close_org, p.close_qfq,
           p.volume, p.turnover, p.pct_change, p.turnover_rate
    FROM {schema.TABLE_DAILY_PRICE} p
    JOIN (
        SELECT symbol, MAX(idate) AS idate
        FROM {schema.TABLE_DAILY_PRICE}
        WHERE idate <= :as_of
        GROUP BY symbol
    ) t ON p.symbol = t.symbol AND p.idate = t.idate
),
last_fund AS (
    SELECT f.*
    FROM {schema.TABLE_FUNDAMENTAL} f
    JOIN (
        SELECT symbol, MAX(season) AS season
        FROM {schema.TABLE_FUNDAMENTAL}
        WHERE season <= :season_max
        GROUP BY symbol
    ) t ON f.symbol = t.symbol AND f.season = t.season
),
last_growth AS (
    SELECT g.symbol, g.season AS growth_season, g.season_income, g.season_income_growth,
           g.season_profit, g.season_profit_growth
    FROM {schema.TABLE_FUNDAMENTAL_GROWTH} g
    JOIN (
        SELECT symbol, MAX(season) AS season
        FROM {schema.TABLE_FUNDAMENTAL_GROWTH}
        WHERE season <= :season_max
        GROUP BY symbol
    ) t ON g.symbol = t.symbol AND g.season = t.season
),
last_fin AS (
    SELECT i.symbol, i.report_date, i.eps_ttm, i.bvps_ttm, i.roe, i.gross_margin,
           i.net_margin, i.eps_deducted, i.net_profit_deducted
    FROM {schema.TABLE_FINANCIAL} i
    JOIN (
        SELECT symbol, MAX(idate) AS idate
        FROM {schema.TABLE_FINANCIAL}
        WHERE idate <= :as_of
        GROUP BY symbol
    ) t ON i.symbol = t.symbol AND i.idate = t.idate
),
valuation AS (
    -- 把四个窗口的估值分位透视成一行一只股票
    SELECT symbol,
           MAX(CASE WHEN window_years = 3  THEN pe_pct END) AS pe_pct_3y,
           MAX(CASE WHEN window_years = 5  THEN pe_pct END) AS pe_pct_5y,
           MAX(CASE WHEN window_years = 10 THEN pe_pct END) AS pe_pct_10y,
           MAX(CASE WHEN window_years = 0  THEN pe_pct END) AS pe_pct_all,
           MAX(CASE WHEN window_years = 10 THEN pb_pct END) AS pb_pct_10y,
           MAX(CASE WHEN window_years = 10 THEN ps_pct END) AS ps_pct_10y,
           MAX(as_of) AS valuation_as_of
    FROM {schema.TABLE_VALUATION_PERCENTILE}
    GROUP BY symbol
)
SELECT
    p.symbol,
    f.name,
    p.date, p.idate, p.close, p.close_org, p.close_qfq, p.volume, p.turnover,
    p.pct_change, p.turnover_rate,
    f.season, f.total_revenue, f.total_revenue_yoy, f.net_profit, f.net_profit_yoy,
    f.total_assets, f.total_liabilities, f.debt_ratio, f.total_equity,
    f.revenue_ttm, f.net_profit_ttm,
    g.season_income, g.season_income_growth, g.season_profit, g.season_profit_growth,
    i.report_date, i.eps_ttm, i.bvps_ttm, i.roe, i.gross_margin, i.net_margin,
    v.pe_pct_3y, v.pe_pct_5y, v.pe_pct_10y, v.pe_pct_all,
    v.pb_pct_10y, v.ps_pct_10y, v.valuation_as_of,
    CASE
        WHEN i.eps_ttm IS NOT NULL AND i.eps_ttm <> 0 AND f.net_profit_ttm IS NOT NULL
            THEN f.net_profit_ttm / i.eps_ttm
        WHEN i.eps_deducted IS NOT NULL AND i.eps_deducted <> 0
            THEN i.net_profit_deducted / i.eps_deducted
    END AS shares
FROM last_price p
LEFT JOIN last_fund f ON f.symbol = p.symbol
LEFT JOIN last_growth g ON g.symbol = p.symbol
LEFT JOIN last_fin i ON i.symbol = p.symbol
LEFT JOIN valuation v ON v.symbol = p.symbol
"""


def snapshot(
    as_of: int | None = None,
    *,
    season_max: int | None = None,
    conn: sqlite3.Connection | None = None,
    with_listing: bool = False,
) -> pd.DataFrame:
    """横截面快照：一行一只股票。

    参数
    ----
    as_of        : 快照日期（YYYYMMDD 整数），缺省用库中最新交易日
    season_max   : 使用的季度上限，缺省与 as_of 相同（只用已披露的季度）
    with_listing : 是否附带 first_date / listed_bars（需要额外聚合，稍慢）

    返回列见 `SNAPSHOT_COLUMNS`，并额外派生 `market_cap` / `pe` / `pb`。
    """
    with _Conn(conn) as active:
        if as_of is None:
            latest = latest_trading_date(active)
            if latest is None:
                raise FileNotFoundError("daily_price 为空，请先运行 quant db-migrate 或 quant update-price")
            as_of = int(latest.replace("-", ""))
        as_of = int(as_of)
        season_max = int(season_max) if season_max is not None else as_of

        # 老库可能还没有估值分位表
        if not store.table_exists(active, schema.TABLE_VALUATION_PERCENTILE):
            store.ensure_schema(active)

        df = _read_sql(
            active,
            _SNAPSHOT_SQL,
            {"as_of": as_of, "season_max": season_max},
        )

        if with_listing:
            listing = _read_sql(
                active,
                f"SELECT symbol, MIN(date) AS first_date, COUNT(*) AS listed_bars "
                f"FROM {schema.TABLE_DAILY_PRICE} WHERE idate <= ? GROUP BY symbol",
                [as_of],
            )
            df = df.merge(listing, on="symbol", how="left")

    df = _add_valuation(df)
    ordered = [c for c in SNAPSHOT_COLUMNS if c in df.columns]
    extra = [c for c in df.columns if c not in ordered]
    return df.loc[:, ordered + extra].reset_index(drop=True)


def _add_valuation(df: pd.DataFrame) -> pd.DataFrame:
    """派生市值 / PE / PB。

    口径：
        shares     = 扣非净利润 / 扣非每股收益（同一报告期，来自 financial_indicator）
        market_cap = 不复权收盘价 × shares
        pe         = 不复权收盘价 / eps_ttm
        pb         = 不复权收盘价 / bvps_ttm
    """
    if df.empty:
        return df

    close = pd.to_numeric(df["close_org"], errors="coerce")
    shares = pd.to_numeric(df.get("shares"), errors="coerce")
    df["market_cap"] = close * shares

    eps = pd.to_numeric(df.get("eps_ttm"), errors="coerce")
    bvps = pd.to_numeric(df.get("bvps_ttm"), errors="coerce")
    revenue = pd.to_numeric(df.get("revenue_ttm"), errors="coerce")

    # 沿用各报告期的市场规模口径：PE/PB 用不复权价 ÷ 每股指标，PS 用市值 ÷ 营业总收入(TTM)
    df["pe"] = (close / eps.where(eps != 0)).replace([float("inf"), float("-inf")], pd.NA)
    df["pb"] = (close / bvps.where(bvps != 0)).replace([float("inf"), float("-inf")], pd.NA)
    df["ps"] = (df["market_cap"] / revenue.where(revenue > 0)).replace(
        [float("inf"), float("-inf")], pd.NA
    )
    return df


# --------------------------------------------------------------------------
# 时序数据
# --------------------------------------------------------------------------
def prices(
    symbols: str | Iterable[str] | None = None,
    start: int | None = None,
    end: int | None = None,
    *,
    columns: Sequence[str] | None = None,
    conn: sqlite3.Connection | None = None,
    limit_per_symbol: int | None = None,
) -> pd.DataFrame:
    """批量读取日线，返回**长表**（symbol/date/... 各一行）。

    参数 limit_per_symbol 表示每只股票只取最近 N 根（需要 start/end 之外的额外排序，稍慢）。
    """
    selected = ", ".join(columns) if columns else "*"
    with _Conn(conn) as active:
        if symbols is None:
            sql = f"SELECT {selected} FROM {schema.TABLE_DAILY_PRICE} WHERE 1=1"
            params: list = []
            if start is not None:
                sql += " AND idate >= ?"
                params.append(int(start))
            if end is not None:
                sql += " AND idate <= ?"
                params.append(int(end))
            sql += " ORDER BY symbol, date"
            return _read_sql(active, sql, params)

        if isinstance(symbols, str):
            symbols = [symbols]
        symbols = [str(s).zfill(6) for s in symbols]

        frames = []
        for chunk in _chunks(list(symbols)):
            sql = (
                f"SELECT {selected} FROM {schema.TABLE_DAILY_PRICE} "
                f"WHERE symbol IN ({_placeholders(chunk)})"
            )
            params = list(chunk)
            if start is not None:
                sql += " AND idate >= ?"
                params.append(int(start))
            if end is not None:
                sql += " AND idate <= ?"
                params.append(int(end))
            sql += " ORDER BY symbol, date"
            frames.append(_read_sql(active, sql, params))

    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)

    if limit_per_symbol:
        df = df.groupby("symbol", group_keys=False).tail(limit_per_symbol).reset_index(drop=True)
    return df


def price_wide(
    symbols: Iterable[str],
    start: int | None = None,
    end: int | None = None,
    field: str = "close_qfq",
    *,
    conn: sqlite3.Connection | None = None,
) -> pd.DataFrame:
    """把某一只字段透视成「日期 × 股票」的宽表（便于算相关性/组合）。"""
    df = prices(symbols, start, end, columns=["symbol", "date", field], conn=conn)
    if df.empty:
        return df
    return df.pivot(index="date", columns="symbol", values=field)


def price_history(
    symbols: Iterable[str],
    bars: int,
    *,
    as_of: int | None = None,
    fields: Sequence[str] = ("symbol", "date", "close_qfq", "volume"),
    conn: sqlite3.Connection | None = None,
) -> pd.DataFrame:
    """取每只股票最近 bars 根 K 线（不含 as_of 之后的日期）。"""
    columns = [c for c in set(fields) | {"symbol", "date", "idate"}]
    df = prices(symbols, end=as_of, columns=columns, conn=conn)
    if df.empty:
        return df
    df = df.sort_values(["symbol", "date"])
    df = df.groupby("symbol", group_keys=False).tail(bars).reset_index(drop=True)
    return df.loc[:, [c for c in fields if c in df.columns] + [c for c in df.columns if c not in fields]]


def fundamentals(
    seasons: int | Iterable[int] | None = None,
    symbols: Iterable[str] | None = None,
    *,
    conn: sqlite3.Connection | None = None,
) -> pd.DataFrame:
    """读取季度基本面（长表）。"""
    with _Conn(conn) as active:
        return _read_by_filters(active, schema.TABLE_FUNDAMENTAL, "season", seasons, symbols)


def growth(
    seasons: int | Iterable[int] | None = None,
    symbols: Iterable[str] | None = None,
    *,
    conn: sqlite3.Connection | None = None,
) -> pd.DataFrame:
    """读取单季增长（长表）。"""
    with _Conn(conn) as active:
        return _read_by_filters(active, schema.TABLE_FUNDAMENTAL_GROWTH, "season", seasons, symbols)


def financial(
    symbols: Iterable[str] | None = None,
    *,
    conn: sqlite3.Connection | None = None,
) -> pd.DataFrame:
    """读取财务指标（长表）。"""
    with _Conn(conn) as active:
        return _read_by_filters(active, schema.TABLE_FINANCIAL, None, None, symbols)


def _read_by_filters(
    conn: sqlite3.Connection,
    table: str,
    season_column: str | None,
    seasons,
    symbols,
) -> pd.DataFrame:
    sql = f"SELECT * FROM {table} WHERE 1=1"
    params: list = []

    if seasons is not None:
        if isinstance(seasons, (int, str)):
            seasons = [seasons]
        seasons = [int(s) for s in seasons]
        sql += f" AND {season_column} IN ({_placeholders(seasons)})"
        params.extend(seasons)

    if symbols is not None:
        if isinstance(symbols, str):
            symbols = [symbols]
        symbols = [str(s).zfill(6) for s in symbols]
        sql += f" AND symbol IN ({_placeholders(symbols)})"
        params.extend(symbols)

    order = f" ORDER BY symbol, {season_column}" if season_column else " ORDER BY symbol"
    return _read_sql(conn, sql + order, params)


def stock_names(symbols: Iterable[str] | None = None, *, conn: sqlite3.Connection | None = None) -> pd.DataFrame:
    """读取股票代码与简称。"""
    with _Conn(conn) as active:
        if symbols is None:
            return _read_sql(active, f"SELECT * FROM {schema.TABLE_STOCK_LIST} ORDER BY symbol")
        symbols = [str(s).zfill(6) for s in symbols]
        return _read_sql(
            active,
            f"SELECT * FROM {schema.TABLE_STOCK_LIST} WHERE symbol IN ({_placeholders(symbols)})",
            symbols,
        )


def universe(
    *,
    as_of: int | None = None,
    min_bars: int = 250,
    conn: sqlite3.Connection | None = None,
) -> list[str]:
    """返回基础股票池：在 as_of 之前至少有 min_bars 根 K 线的股票。"""
    with _Conn(conn) as active:
        sql = (
            f"SELECT symbol, COUNT(*) AS n FROM {schema.TABLE_DAILY_PRICE} "
            f"WHERE idate <= ? GROUP BY symbol HAVING n >= ?"
        )
        rows = active.execute(sql, [int(as_of) if as_of else 99999999, int(min_bars)]).fetchall()
    return [row[0] for row in rows]


def to_display(df: pd.DataFrame) -> pd.DataFrame:
    """把列名转成中文展示名（UI / 报表用）。"""
    return schema.rename_for_display(df)
