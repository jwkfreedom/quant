"""基本面：TTM 计算、财务指标修补、PE/PB 估值。

由原 stockdata.py 等价迁移，算法未改动。
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

#: financial_report_XXXXXX.csv 中需要修补的字段
NAME_PREFIX = "每股净资产_调整前(元)"
NAME_POSTFIX = "每股净资产_调整后(元)"


def calc_ttm(df: pd.DataFrame, name_profit: str, ttm_name: str) -> pd.DataFrame:
    """计算财务数据中的 TTM 值。

    TTM = 去年年报值 - 去年同季值 + 本季值。
    若缺少去年同期或去年年报，则该季填 '--'。
    """
    df[name_profit] = pd.to_numeric(df[name_profit], errors="coerce")
    df.dropna(subset=[name_profit], inplace=True)

    if "iDATE" not in df.columns:
        df["DATE"] = df["日期"].str.replace("-", "")
        df["iDATE"] = pd.to_numeric(df["DATE"], errors="coerce")
        df.drop(df[df["iDATE"] < 20110101].index, inplace=True)

    seasons = sorted(set(df["iDATE"].unique()))

    for season in seasons:
        preyear_season = df.loc[df["iDATE"] == season, "iDATE"].item() - 10000
        preyear = int(preyear_season / 10000)
        preyear_end = preyear * 10000 + 1231

        season_profit = df.loc[df["iDATE"] == season, name_profit].item()
        if (not df.loc[df["iDATE"] == preyear_season].empty) and (not df.loc[df["iDATE"] == preyear_end].empty):
            preyear_season_profit = df.loc[df["iDATE"] == preyear_season, name_profit].item()
            preyear_end_profit = df.loc[df["iDATE"] == preyear_end, name_profit].item()
            df.loc[df["iDATE"] == season, ttm_name] = preyear_end_profit - preyear_season_profit + season_profit
        else:
            df.loc[df["iDATE"] == season, ttm_name] = "--"

    return df


def fix_financial_data(df: pd.DataFrame) -> None:
    """修补 financial_report 数据。

    '每股净资产_调整后(元)' 偶有缺失，用 '调整前' 减去上一期的差额推算。
    原地修改 df，无返回值（保持原行为）。

    TODO(2.2): 改为返回 DataFrame，并处理 item() 的多行/缺行异常。
    """
    df["DATE"] = df["日期"].str.replace("-", "")
    df["iDATE"] = pd.to_numeric(df["DATE"], errors="coerce")

    seasons = sorted(set(df["iDATE"].unique()))
    diff = 0

    df[NAME_PREFIX] = pd.to_numeric(df[NAME_PREFIX], errors="coerce")
    df[NAME_POSTFIX] = pd.to_numeric(df[NAME_POSTFIX], errors="coerce")

    for season in seasons:
        season_prefix = df.loc[df["iDATE"] == season, NAME_PREFIX]
        season_postfix = df.loc[df["iDATE"] == season, NAME_POSTFIX]
        if pd.isna(season_postfix.item()):
            value = season_prefix.item() - diff
            df.loc[df["iDATE"] == season, NAME_POSTFIX] = value
            logger.info("fix season=%s, value=%s", season, value)
        else:
            diff = season_prefix.item() - season_postfix.item()


def calc_pepb_by_season(group: pd.DataFrame) -> pd.DataFrame:
    """按季度分组，用季度首个交易日的 close_org 与 TTM 计算 PE/PB，其余交易日按价格比例推算。

    TODO(2.2): 当前依赖组内行序与索引语义，调用前必须保证数据按日期排序且索引已 reset。
    """
    first = group.index[0]

    if group.loc[first, "profitTTM"].item() != 0:
        group.loc[first, "PE"] = group.loc[first, "close_org"] / group.loc[first, "profitTTM"]
        group.loc[group.index[1:], "PE"] = (
            group.loc[group.index[1:], "close_org"] / group.loc[first, "close_org"]
        ) * group.loc[first, "PE"]
    else:
        group.loc[:, "PE"] = 0.0

    if group.loc[first, "netassetTTM"] != 0 or group.loc[first, "netassetTTM"].item() != 0:
        group.loc[first, "PB"] = group.loc[first, "close_org"] / group.loc[first, "netassetTTM"]
        group.loc[group.index[1:], "PB"] = (
            group.loc[group.index[1:], "close_org"] / group.loc[first, "close_org"]
        ) * group.loc[first, "PB"]
    else:
        group.loc[:, "PB"] = 0.0

    return group


def update_price_pe(df_price: pd.DataFrame, df_financial: pd.DataFrame) -> pd.DataFrame:
    """把 TTM 利润/净资产并进日线，再按季度计算 PE/PB。"""
    merged_df = pd.merge(df_price, df_financial, left_on="season", right_on="iDATE", how="left")
    merged_df.fillna({"profitTTM": 0}, inplace=True)
    merged_df.fillna({"netassetTTM": 0}, inplace=True)

    df_price["profitTTM"] = merged_df["profitTTM"]
    df_price["PE"] = 0.0

    df_price["netassetTTM"] = merged_df["netassetTTM"]
    df_price["PB"] = 0.0

    df_price = df_price[pd.to_numeric(df_price["netassetTTM"], errors="coerce").notnull()]
    logger.debug("merged price rows: %d", len(df_price))
    df_price = df_price.groupby("season", group_keys=False).apply(calc_pepb_by_season)

    return df_price
