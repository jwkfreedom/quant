"""基本面：季度数据读取、残缺股剔除、单季增长计算。

阶段 2.2 改写要点：
    - 数据源改为 SQLite（`fundamental` 表），不再逐个季度读 CSV
    - `growth_score` 由「逐股票 × 逐季度 `.loc` 全表扫描 + `.item()`」改为**向量化**，
      复杂度从 O(股票数²) 降到 O(行数)，并且缺数据时返回 NaN 而不是抛异常
    - 列名统一英文（见 quant/data/schema.py）
"""

from __future__ import annotations

import logging
import sqlite3

import pandas as pd

from quant.data import schema, store
from quant.foundation.season import get_seasondate, pre_year_season

logger = logging.getLogger(__name__)

#: 计算单季增长所需的输入列
SEASON_FIELD_MAP = schema.GROWTH_FIELD_MAP


# --------------------------------------------------------------------------
# 读取
# --------------------------------------------------------------------------
def load_fundamental(
    season_start: int | None = None,
    season_end: int | None = None,
    symbols=None,
    *,
    conn: sqlite3.Connection | None = None,
    strict: bool = True,
) -> pd.DataFrame:
    """从数据库读取季度基本面。

    参数
    ----
    season_start / season_end : YYYYMMDD 整数边界（含），可选
    symbols                   : 只取指定股票代码，可选
    strict                    : 为 True 时，若一个季度都没有数据则抛 FileNotFoundError
    """
    if conn is not None:
        return store.read_fundamental(conn, season_start, season_end, symbols)

    with store.open_db() as own_conn:
        if not store.table_exists(own_conn, schema.TABLE_FUNDAMENTAL):
            if strict:
                raise FileNotFoundError("数据库尚未初始化，请先运行 quant db-init 与 quant db-migrate")
            return pd.DataFrame()
        return store.read_fundamental(own_conn, season_start, season_end, symbols)


def load_jibenmian(
    season_start: str,
    beforedays: int = 90,
    *,
    conn: sqlite3.Connection | None = None,
) -> pd.DataFrame:
    """按起始日期读取连续季度基本面（保留旧函数名与签名）。

    参数 season_start 格式 '2021-01-01'；beforedays 表示截止到多少天前。
    """
    seasons = [int(s) for s in get_seasondate(season_start, beforedays)]
    if not seasons:
        logger.warning("起始日期 %s 之后没有任何季度", season_start)
        return pd.DataFrame()

    df = load_fundamental(seasons[0], seasons[-1], conn=conn)
    if df.empty:
        raise FileNotFoundError(
            f"数据库中 {seasons[0]} ~ {seasons[-1]} 没有基本面数据；"
            "请先运行 quant update-jibenmian 与 quant db-migrate"
        )

    available = sorted(df["season"].unique())
    missing = sorted(set(seasons) - set(available))
    if missing:
        logger.warning("缺少 %d 个季度的数据: %s ~ %s（可运行 quant update-jibenmian 补齐）",
                       len(missing), missing[0], missing[-1])
    return df


def rm_broken_stocks(df: pd.DataFrame) -> pd.DataFrame:
    """删除数据不全的股票，只保留在所有季度都出现的股票代码。"""
    if df.empty:
        return df
    counts = df.groupby("symbol")["season"].nunique()
    season_count = df["season"].nunique()
    keep = counts[counts == season_count].index
    logger.info("季度数 %d，完整股票 %d / %d", season_count, len(keep), counts.size)
    return df[df["symbol"].isin(keep)].copy()


# --------------------------------------------------------------------------
# 单季增长（向量化）
# --------------------------------------------------------------------------
def _season_growth_for(df: pd.DataFrame, cumulative: str, yoy: str, pre_year: str,
                       season_value: str, season_growth: str) -> pd.DataFrame:
    """计算某一口径（收入/利润）的单季值与同比，返回 symbol/season + 三列。"""
    # 所有行先算出「去年同季值」
    full = df.loc[:, ["symbol", "season", cumulative, yoy]].copy()
    full["pre_value"] = full[cumulative] / (1 + full[yoy] / 100.0)

    base = full.copy()
    base["prev_season"] = base["season"].map(pre_year_season)

    # 上一季的累计值
    prev_cumulative = full.loc[:, ["symbol", "season", cumulative]].rename(
        columns={"season": "prev_season", cumulative: "prev_cumulative"}
    )
    base = base.merge(prev_cumulative, on=["symbol", "prev_season"], how="left")

    # 上一季的「去年同季值」（按 (symbol, prev_season) 查 full 里的 pre_value）
    prev_pre = full.loc[:, ["symbol", "season", "pre_value"]].rename(
        columns={"season": "prev_season", "pre_value": "prev_pre_value"}
    )
    base = base.merge(prev_pre, on=["symbol", "prev_season"], how="left")

    is_q1 = base["season"] % 10000 == 331

    single = (base[cumulative] - base["prev_cumulative"]).where(~is_q1, base[cumulative])
    growth = ((single / (base["pre_value"] - base["prev_pre_value"])) - 1) * 100
    growth = growth.where(~is_q1, base[yoy])

    out = pd.DataFrame({
        "symbol": base["symbol"],
        "season": base["season"],
        pre_year: base["pre_value"],
        season_value: single,
        season_growth: growth,
    })

    incomplete = int((~is_q1 & base["prev_cumulative"].isna()).sum())
    if incomplete > 0:
        logger.warning("%s：有 %d 行缺少上一季度数据", season_value, incomplete)
    return out


def compute_growth(df: pd.DataFrame) -> pd.DataFrame:
    """对季度基本面计算单季收入/利润及其同比，返回带增长列的新 DataFrame。

    前置条件：输入需包含 symbol/season 及 GROWTH_FIELD_MAP 中使用的列；
             首个季度应为 XXXX0331，否则第一季的单季同比无意义。
    """
    if df.empty:
        return df

    seasons = sorted(df["season"].unique())
    if seasons and seasons[0] % 10000 != 331:
        logger.warning("首个季度不是一季报（%s），单季口径可能与预期不符", seasons[0])

    work = df.sort_values(["symbol", "season"]).reset_index(drop=True)
    result = work.copy()
    for _name, (cumulative, yoy, pre_year, season_value, season_growth) in SEASON_FIELD_MAP.items():
        part = _season_growth_for(work, cumulative, yoy, pre_year, season_value, season_growth)
        result = result.merge(part, on=["symbol", "season"], how="left", sort=False)

    return result


def growth_score(df: pd.DataFrame) -> pd.DataFrame | None:
    """兼容旧接口：计算单季增长。

    旧实现要求首季必须是 XXXX0331，否则返回 None；这里保留该行为。
    """
    if df.empty:
        return None
    seasons = sorted(df["season"].unique())
    if seasons[0] % 10000 != 331:
        logger.error("first season should be XXXX0331. Now is %s", seasons[0])
        return None
    return compute_growth(df)


def growth_columns() -> tuple[str, ...]:
    """返回单季增长表的列名。"""
    return schema.GROWTH_VALUE_COLUMNS
