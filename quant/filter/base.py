"""过滤器基础设施：Filter 协议、FilterContext、注册表。

设计
----
- **Filter**：把「一行一只股票」的快照表变窄。可以只依赖快照列（横截面），
  也可以通过 `ctx.history(bars)` 拿最近 N 根 K 线做时序判断。
- **FilterContext**：统一提供数据与缓存，过滤器不直接碰数据库。
  在同一次选股中，快照与历史只查一次，多个过滤器复用。
- **注册表**：名字 -> 过滤器类，供 CLI 用字符串描述过滤器。

写一个新过滤器::

    from quant.filter import Filter, register

    class SmallCap:
        name = "small_cap"
        description = "市值上限"
        def __init__(self, max_yi=80):
            self.max_yi = max_yi
        def apply(self, df, ctx):
            return df[df["market_cap"] <= self.max_yi * 1e8]

    register(SmallCap)
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import pandas as pd

from quant import query
from quant.data import store

logger = logging.getLogger(__name__)


@runtime_checkable
class Filter(Protocol):
    """选股过滤器协议。"""

    #: 唯一标识（CLI 里用这个名字）
    name: str
    #: 一行说明，`quant screen --list` 会打印
    description: str

    def apply(self, df: pd.DataFrame, ctx: "FilterContext") -> pd.DataFrame:  # pragma: no cover
        ...


@dataclass
class FilterContext:
    """一次选股过程中的数据上下文（含缓存）。"""

    conn: sqlite3.Connection | None = None
    as_of: int | None = None
    _snapshot: pd.DataFrame | None = field(default=None, repr=False)
    _history_cache: tuple[int, pd.DataFrame] | None = field(default=None, repr=False)
    _history_slices: dict[int, pd.DataFrame] = field(default_factory=dict, repr=False)
    _trading_days: list[str] | None = field(default=None, repr=False)
    _last_dates_cache: pd.DataFrame | None = field(default=None, repr=False)
    _listing: pd.DataFrame | None = field(default=None, repr=False)
    _owns_conn: bool = False

    def __enter__(self) -> "FilterContext":
        if self.conn is None:
            self.conn = store.connect()
            self._owns_conn = True
        return self

    def __exit__(self, *exc) -> None:
        if self._owns_conn and self.conn is not None:
            self.conn.close()
            self.conn = None

    # ---------------------------------------------------------------- 数据
    def snapshot(self) -> pd.DataFrame:
        """当前交易日全市场快照（含市值/PE/PB），带缓存。"""
        if self._snapshot is None:
            self._snapshot = query.snapshot(as_of=self.as_of, conn=self.conn)
        return self._snapshot

    def listing(self) -> pd.DataFrame:
        """每只股票的首个交易日与 K 线根数。"""
        if self._listing is None:
            with query._Conn(self.conn) as active:
                self._listing = query._read_sql(
                    active,
                    "SELECT symbol, MIN(date) AS first_date, COUNT(*) AS listed_bars "
                    "FROM daily_price WHERE idate <= ? GROUP BY symbol",
                    [self.as_of if self.as_of else 99999999],
                )
        return self._listing

    def history(self, bars: int) -> pd.DataFrame:
        """每只股票最近 bars 根 K 线（长表，按 symbol/date 升序），按 bars 缓存。

        返回列与 `get_stock_price()` 口径一致：
            `close/open/high/low` 为**前复权**，`close_org` 为**不复权**，
            另有 `volume / turnover / turnover_rate / pct_change / idate`。
        """
        bars = int(bars)
        if bars <= 0:
            raise ValueError("bars 必须为正整数")

        if bars in self._history_slices:
            return self._history_slices[bars]

        if self._history_cache is not None and self._history_cache[0] >= bars:
            df = self._slice_per_symbol(self._history_cache[1], bars)
        else:
            df = self._fetch_history(bars)
            self._history_cache = (bars, df)

        self._history_slices[bars] = df
        return df

    @staticmethod
    def _slice_per_symbol(df: pd.DataFrame, bars: int) -> pd.DataFrame:
        """从更大的缓存里裁出每只股票最近 bars 根。"""
        return (
            df.sort_values(["symbol", "date"])
            .groupby("symbol", group_keys=False)
            .tail(bars)
            .reset_index(drop=True)
        )

    _HISTORY_COLUMNS = (
        "symbol, date, idate, close, close_qfq, open_qfq, high_qfq, low_qfq, "
        "volume, turnover, turnover_rate, pct_change"
    )

    def _calendar(self, conn: sqlite3.Connection) -> list[str]:
        """as_of 之前的全部交易日（升序），用于按交易日个数回推区间。"""
        if self._trading_days is None:
            as_of = self.as_of if self.as_of else 99999999
            rows = conn.execute(
                "SELECT DISTINCT date FROM daily_price WHERE idate <= ? ORDER BY date", [as_of]
            ).fetchall()
            self._trading_days = [row[0] for row in rows]
        return self._trading_days

    def _last_dates(self, conn: sqlite3.Connection) -> pd.DataFrame:
        """每只股票在 as_of 之前的最后交易日（走主键索引，较快）。"""
        if self._last_dates_cache is None:
            as_of = self.as_of if self.as_of else 99999999
            self._last_dates_cache = query._read_sql(
                conn,
                "SELECT symbol, MAX(date) AS last_date FROM daily_price WHERE idate <= ? GROUP BY symbol",
                [as_of],
            )
        return self._last_dates_cache

    def _fetch_history(self, bars: int) -> pd.DataFrame:
        """查询每只股票最近 bars 根 K 线。

        实现要点（关系到性能）：
            1. 取 as_of 之前的交易日日历与每只股票的**最后交易日**；
            2. 对每只股票按**自己的最后交易日**回推 bars*2+20 个交易日，得到各自的下界；
            3. 用临时表 + 主键 (symbol, date) 做区间扫描，只读需要的行；
            4. 最后按 symbol 裁到最近 bars 根。
        这样既避免了 1000 万行的全表窗口排序，又不会漏掉长期停牌/退市的股票
        （它们的最后交易日可能远早于市场的最后交易日）。
        """
        as_of = self.as_of if self.as_of else 99999999
        margin = bars * 2 + 20

        with query._Conn(self.conn) as active:
            calendar = self._calendar(active)
            if not calendar:
                return pd.DataFrame()
            index_of = {date: i for i, date in enumerate(calendar)}

            last_dates = self._last_dates(active)
            bounds = []
            for symbol, last_date in zip(last_dates["symbol"], last_dates["last_date"]):
                position = index_of.get(last_date)
                if position is None:
                    continue
                bounds.append((symbol, calendar[max(0, position - margin)]))

            if not bounds:
                return pd.DataFrame()

            active.execute("CREATE TEMP TABLE IF NOT EXISTS _hist_bounds (symbol TEXT PRIMARY KEY, cutoff TEXT)")
            active.execute("DELETE FROM _hist_bounds")
            active.executemany("INSERT INTO _hist_bounds VALUES (?, ?)", bounds)

            selected = ", ".join(f"p.{c.strip()}" for c in self._HISTORY_COLUMNS.split(","))
            # 上下界都用 date 字符串，让主键索引 (symbol, date) 走紧凑的范围扫描
            sql = (
                f"SELECT {selected} FROM daily_price p "
                "JOIN _hist_bounds b ON b.symbol = p.symbol "
                "WHERE p.date >= b.cutoff AND p.date <= ? ORDER BY p.symbol, p.date"
            )
            df = query._read_sql(active, sql, [calendar[-1]])
            active.execute("DROP TABLE IF EXISTS _hist_bounds")

        if df.empty:
            return df

        df = self._slice_per_symbol(df, bars)
        # daily_price 里 close 是不复权、close_qfq 是前复权；对外统一成 loader 的口径
        df["close_org"] = df["close"]
        df["open"] = df["open_qfq"]
        df["high"] = df["high_qfq"]
        df["low"] = df["low_qfq"]
        df["close"] = df["close_qfq"]
        return df.reset_index(drop=True)


# --------------------------------------------------------------------------
# 注册表
# --------------------------------------------------------------------------
_REGISTRY: dict[str, type] = {}


def register(cls: type) -> type:
    """注册过滤器类（按 `cls.name`）。"""
    name = getattr(cls, "name", None)
    if not name:
        raise ValueError(f"{cls!r} 缺少 name 属性")
    _REGISTRY[name] = cls
    return cls


def available_filters() -> list[str]:
    """已注册的过滤器名字（排序）。"""
    return sorted(_REGISTRY)


def get_filter_class(name: str) -> type:
    """按名字取过滤器类，未注册时抛 KeyError。"""
    if name not in _REGISTRY:
        raise KeyError(f"未注册的过滤器: {name}；可用: {available_filters()}")
    return _REGISTRY[name]


def describe_filters() -> list[tuple[str, str]]:
    """返回 (名字, 说明) 列表，供 `quant screen --list` 使用。"""
    return [(name, getattr(_REGISTRY[name], "description", "")) for name in available_filters()]


def clear_registry() -> None:
    """清空注册表（测试用）。"""
    _REGISTRY.clear()
