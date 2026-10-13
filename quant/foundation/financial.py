"""基本面：TTM 计算、财务指标修补、PE/PB 估值。

阶段 2.2 改写要点（原实现在 stockdata.py 中逐行循环 + `.item()`，遇到重复行/缺行会抛异常）：
    - 全部改为 pandas 向量化，缺数据处返回 NaN 而不是崩溃
    - 列名统一英文
    - PE/PB 计算前强制按日期排序并按季度分组，消除「依赖组内行序」的隐患
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def calc_ttm(df: pd.DataFrame, value_column: str, ttm_column: str, *, idate_column: str = "idate") -> pd.DataFrame:
    """计算 TTM（滚动四季度）值，返回新的 DataFrame。

    公式：TTM(本期) = 去年年报值 - 去年同季值 + 本期累计值

    与旧实现的差异：缺少去年年报或去年同季时结果为 NaN（旧实现写入字符串 '--'）。
    """
    df = df.sort_values(idate_column).copy()
    value = pd.to_numeric(df[value_column], errors="coerce")
    df[value_column] = value

    lookup = pd.Series(value.values, index=df[idate_column].values)
    lookup = lookup[~lookup.index.duplicated(keep="last")]

    prev_same = df[idate_column] - 10000
    prev_year_end = (df[idate_column] // 10000 - 1) * 10000 + 1231

    prev_same_value = prev_same.map(lookup)
    prev_year_end_value = prev_year_end.map(lookup)

    df[ttm_column] = prev_year_end_value.values - prev_same_value.values + value.values
    return df


def fix_bvps(df: pd.DataFrame, *, before: str = "bvps_before", after: str = "bvps_after") -> pd.DataFrame:
    """修补 '每股净资产(调整后)' 缺失值。

    规则：若某期「调整后」缺失，则用「调整前」减去上一期的（调整前 - 调整后）差额。
    与旧实现等价，但改为向量化（旧的逐季循环靠循环变量 diff 传递状态）。
    """
    df = df.sort_values("idate").copy()
    before_values = pd.to_numeric(df[before], errors="coerce")
    after_values = pd.to_numeric(df[after], errors="coerce")

    diff = (before_values - after_values)
    # 上一期已知的差额（向前填充后整体下移一行），首期为 0
    diff_prev = diff.ffill().shift(1).fillna(0.0)
    filled = before_values - diff_prev

    df[before] = before_values
    df[after] = after_values.where(after_values.notna(), filled)
    return df


def compute_pe_pb(df_price: pd.DataFrame, df_financial: pd.DataFrame) -> pd.DataFrame:
    """把 TTM 每股指标并入日线并计算 PE / PB。

    口径（沿用重构前）：
        - 每个季度的**首个交易日**：PE = 不复权收盘价 / 每股收益TTM，PB 同理
        - 该季度其余交易日：按不复权收盘价相对首日的比例线性缩放
        - 每股收益TTM 为 0 或缺该季度财务数据时，整段 PE = 0
    """
    price = df_price.sort_values("date").copy()

    fin = df_financial.loc[:, ["idate", "eps_ttm", "bvps_ttm"]].rename(columns={"idate": "season"})
    fin = fin.drop_duplicates(subset=["season"], keep="last")
    price = price.merge(fin, on="season", how="left")

    price["eps_ttm"] = pd.to_numeric(price["eps_ttm"], errors="coerce")
    price["bvps_ttm"] = pd.to_numeric(price["bvps_ttm"], errors="coerce")

    # 旧实现用副本的 SEASON 顺序取“季度首行”，这里显式按日期取首行
    is_first = ~price.duplicated(subset=["season"], keep="first")
    first = price.loc[is_first].set_index("season")

    first_close = first["close_org"]
    first_eps = first["eps_ttm"].fillna(0.0)
    first_bvps = first["bvps_ttm"].fillna(0.0)

    pe_base = pd.Series(0.0, index=first.index)
    valid = first_eps != 0
    pe_base[valid] = first_close[valid] / first_eps[valid]

    pb_base = pd.Series(0.0, index=first.index)
    valid = first_bvps != 0
    pb_base[valid] = first_close[valid] / first_bvps[valid]

    ratio = price["close_org"] / price["season"].map(first_close)

    pe = price["season"].map(pe_base) * ratio
    pb = price["season"].map(pb_base) * ratio

    # 旧实现：季度首行直接等于基准值（ratio 为 1，结果一致），无财务数据的季度为 0
    price["PE"] = pe.where(price["season"].map(first_eps).ne(0), 0.0).fillna(0.0).round(10)
    price["PB"] = pb.where(price["season"].map(first_bvps).ne(0), 0.0).fillna(0.0).round(10)

    return price


def financial_to_ttm(df_financial: pd.DataFrame) -> pd.DataFrame:
    """对 financial_indicator 表数据做修补 + TTM，返回带 eps_ttm / bvps_ttm 的 DataFrame。"""
    if df_financial.empty:
        return df_financial

    df = df_financial.sort_values("report_date").copy()
    df = fix_bvps(df)
    df = calc_ttm(df, "eps_diluted", "eps_ttm")
    df = calc_ttm(df, "bvps_after", "bvps_ttm")

    df = df[df["eps_ttm"].notna()]
    df = df[df["bvps_ttm"].notna()]
    return df.reset_index(drop=True)
