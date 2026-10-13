"""季报日期工具的单测（纯函数，不依赖数据）。"""

from __future__ import annotations

import datetime as dt

import pytest

from quant.foundation.season import (
    get_season_iDATE,
    get_seasondate,
    pre_year_season,
    season_to_date,
)


def test_get_seasondate_full_year():
    seasons = get_seasondate("2022-01-01", beforedays=0, end_date=dt.date(2023, 12, 31))
    assert seasons == [
        "20220331", "20220630", "20220930", "20221231",
        "20230331", "20230630", "20230930", "20231231",
    ]


def test_get_seasondate_excludes_start_date():
    # 严格大于 start_date：起始日当天正好是季报日时应当排除
    seasons = get_seasondate("2022-03-31", beforedays=0, end_date=dt.date(2022, 12, 31))
    assert seasons == ["20220630", "20220930", "20221231"]


def test_get_seasondate_beforedays():
    # end_date - 90 天 = 2023-02-01，最后一个季度应为 20221231
    seasons = get_seasondate("2020-01-01", beforedays=90, end_date=dt.date(2023, 5, 1))
    assert seasons[-1] == "20221231"


def test_get_seasondate_empty_when_start_in_future():
    seasons = get_seasondate("2030-01-01", beforedays=0, end_date=dt.date(2023, 12, 31))
    assert seasons == []


@pytest.mark.parametrize(
    ("season", "expected"),
    [(20120331, 20111231), (20120630, 20120331), (20120930, 20120630), (20121231, 20120930)],
)
def test_pre_year_season(season, expected):
    assert pre_year_season(season) == expected


@pytest.mark.parametrize(
    ("date", "expected"),
    [
        ("2012-12-21", 20120930),
        ("2012-09-30", 20120930),
        ("2012-09-29", 20120630),
        ("2012-06-30", 20120630),
        ("2012-06-29", 20120331),
        ("2012-03-31", 20120331),
        ("2012-03-30", 20111231),
        ("2012-01-04", 20111231),
    ],
)
def test_get_season_idate(date, expected):
    assert get_season_iDATE(date) == expected


def test_season_to_date():
    assert season_to_date(20230331) == dt.date(2023, 3, 31)
