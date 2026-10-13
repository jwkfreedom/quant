"""基本面：季度三表合并、残缺股剔除、单季增长计算。

由原 stockdata.py 等价迁移，算法未改动。
"""

from __future__ import annotations

import logging

import pandas as pd

from quant.config import DATA_DIR
from quant.foundation.season import get_seasondate, pre_year_season

logger = logging.getLogger(__name__)

#: 单季字段命名：type -> (去年同季值, 单季值, 单季同比)
SEASON_FIELD_MAP: dict[str, list[str]] = {
    "营业总收入": ["preYearIncome", "SeasonIncome", "SeasonIncomeGrowth"],
    "净利润": ["preYearProfit", "SeasonProfit", "SeasonProfitGrowth"],
}


def load_jibenmian(season_start: str, beforedays: int = 90) -> pd.DataFrame:
    """读取并合并 data/a/jibenmian 目录下多个季度的三表数据。

    参数
    ----
    season_start : 起始季度，格式 '2010-03-01'
    beforedays   : 截至到多少天前，缺省 90 天（即上季度）

    返回
    ----
    纵向拼接后的 DataFrame，附加 DATE（字符串）与 iDATE（整数）两列。
    """
    seasons = get_seasondate(season_start, beforedays)
    src_dir = DATA_DIR / "a" / "jibenmian"

    # 只保留三表文件都齐全的季度；缺失的季度跳过并告警（数据尚未下载到该季度）
    available: list[str] = []
    missing: list[str] = []
    for season in seasons:
        if all((src_dir / f"{table}_{season}.csv").is_file() for table in ("zcfz", "lrb", "xjll")):
            available.append(season)
        else:
            missing.append(season)

    if missing:
        logger.warning(
            "跳过 %d 个缺少数据文件的季度: %s ~ %s（可运行 quant download-jibenmian 补齐）",
            len(missing), missing[0], missing[-1],
        )
    if not available:
        raise FileNotFoundError(
            f"{src_dir} 下没有任何完整的季度数据（需要 {seasons[:1]} 等季度的 zcfz/lrb/xjll 文件）；"
            "请先运行 quant download-jibenmian"
        )

    frames: list[pd.DataFrame] = []
    for season in available:
        logger.info("season=%s", season)
        df_zcfz = pd.read_csv(src_dir / f"zcfz_{season}.csv")
        df_lrb = pd.read_csv(src_dir / f"lrb_{season}.csv")
        df_xjll = pd.read_csv(src_dir / f"xjll_{season}.csv")

        df = pd.merge(df_zcfz, df_lrb, on="股票代码")
        df = pd.merge(df_xjll, df, on="股票代码")
        df["DATE"] = season
        df["iDATE"] = int(season)
        frames.append(df)

    return pd.concat(frames, ignore_index=False)


def rm_broken_stocks(df: pd.DataFrame) -> pd.DataFrame:
    """删除数据不全的股票，只保留在所有季度都出现的股票代码。"""
    season_set = set(df["iDATE"].unique())

    stock_sets: list[set] = []
    for season in season_set:
        df_season = df.loc[df["iDATE"] == season]
        stock_sets.append(set(df_season["股票代码"].unique()))

    common_elements = set.intersection(*stock_sets)
    return df[df["股票代码"].isin(common_elements)]


def growth_score(df: pd.DataFrame, max_season: int | None = None) -> pd.DataFrame | None:
    """计算每只股票每个季度的单季收入/利润及其同比。

    .. warning::
       要求首个季度必须是 XXXX0331，否则返回 None（保持原行为）。

    TODO(2.2): 改为返回结果并抛出明确异常，而不是静默返回 None；
               TODO(2.2): 用 groupby+shift 向量化，替换当前的逐股票循环。
    """
    stock_id_set = set(df["股票代码"].unique())
    logger.info("共有 %d 个股票数据", len(stock_id_set))

    seasons = sorted(set(df["iDATE"].unique()))
    if max_season is not None:
        seasons = [s for s in seasons if s <= max_season]

    if not seasons or seasons[0] % 10000 != 331:
        logger.error("first season should be XXXX0331. Now is %s", seasons[0] if seasons else None)
        return None

    for stock_id in stock_id_set:
        calc_season_growth(df, stock_id, seasons, "营业总收入")

    for stock_id in stock_id_set:
        calc_season_growth(df, stock_id, seasons, "净利润")

    return df


def calc_season_growth(df: pd.DataFrame, stock_id, seasons: list[int], type: str) -> pd.DataFrame:
    """计算单只股票所有季度的单季数据（原地修改 df 并返回）。

    参数 type 取值 '营业总收入' 或 '净利润'。
    """
    type_tongbi = type + "同比"
    pre_year_name, season_name, season_growth_name = SEASON_FIELD_MAP[type]

    for season in seasons:
        mask = (df["股票代码"] == stock_id) & (df["iDATE"] == season)

        total_growth = df.loc[mask, type_tongbi]
        pre_year_value = df.loc[mask, type] / (1 + total_growth / 100.0)
        income = df.loc[mask, type]
        df.loc[mask, pre_year_name] = pre_year_value

        if season % 10000 == 331:
            # 每年第一季度，单季增长不必特殊计算
            df.loc[mask, season_growth_name] = total_growth
            df.loc[mask, season_name] = income
        else:
            income_value = df.loc[mask, type].item()
            pre_total_income = df.loc[df["股票代码"].eq(stock_id) & df["iDATE"].eq(pre_year_season(season)), type].item()
            season_income = income_value - pre_total_income
            df.loc[mask, season_name] = season_income

            pre_year_season_income = pre_year_value - df.loc[
                df["股票代码"].eq(stock_id) & df["iDATE"].eq(pre_year_season(season)), pre_year_name
            ].item()
            growth = (season_income / pre_year_season_income - 1) * 100
            df.loc[mask, season_growth_name] = growth

    return df
