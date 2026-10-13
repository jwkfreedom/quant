"""季报日期工具。

季报标识（iDATE）统一使用 8 位整数，例如 20230331::

    0331 -> 一季报   0630 -> 半年报   0930 -> 三季报   1231 -> 年报

本模块由原 stockdata.py 等价迁移，不含行为变更。
"""

from __future__ import annotations

import datetime as dt

#: 四个季报月份日
SEASON_SUFFIXES: tuple[str, ...] = ("0331", "0630", "0930", "1231")

#: 上一季报的月份日映射
_PRE_SEASON_MAP: dict[int, int] = {331: 1231, 630: 331, 930: 630, 1231: 930}


def get_seasondate(
    start_date: str,
    beforedays: int = 90,
    end_date: dt.date | None = None,
) -> list[str]:
    """获得季报日期列表。

    参数
    ----
    start_date : 起始日期，格式 '2010-01-04'
    beforedays : 截止日期为多少天前（默认 90，即取到上一个已披露季度）
    end_date   : 截止基准日，默认今天。显式传入可让调用可复现（测试用）

    返回
    ----
    ['20100331', '20100630', ...]，
    仅包含严格晚于 start_date 且不晚于截止日的季报。
    """
    start_parts = start_date.split("-")
    start_year = int(start_parts[0])
    start_compact = int(start_parts[0] + start_parts[1] + start_parts[2])

    base = end_date if end_date is not None else dt.date.today()
    end_limit = base - dt.timedelta(beforedays)
    end_year = int(end_limit.strftime("%Y"))
    end_compact = int(end_limit.strftime("%Y%m%d"))

    seasons: list[str] = []
    for year in range(start_year, end_year + 1):
        for suffix in SEASON_SUFFIXES:
            value = int(str(year) + suffix)
            if start_compact < value <= end_compact:
                seasons.append(str(value))
    return seasons


def pre_year_season(year_season: int) -> int:
    """获得上一财季的季报 id（跨年时年份减 1）。

    >>> pre_year_season(20120331)
    20111231
    >>> pre_year_season(20120630)
    20120331
    """
    year = int(year_season / 10000)
    season = year_season % 10000
    pre_season = _PRE_SEASON_MAP[season]
    if pre_season > season:
        return (year - 1) * 10000 + pre_season
    return year * 10000 + pre_season


def get_season_iDATE(date: str) -> int:
    """由交易日得到所属季报 id。

    参数 date 格式 '2012-12-21'，返回 20120930（该日所属、且已披露的季报）。
    """
    idate = int(date.replace("-", ""))
    year = int(idate / 10000)
    monthday = idate % 10000
    if monthday < 331:
        return (year - 1) * 10000 + 1231
    if monthday < 630:
        return year * 10000 + 331
    if monthday < 930:
        return year * 10000 + 630
    return year * 10000 + 930


def season_to_date(season: int) -> dt.date:
    """季报 id 转日期：20230331 -> date(2023, 3, 31)。"""
    text = str(season)
    return dt.date(int(text[:4]), int(text[4:6]), int(text[6:8]))
