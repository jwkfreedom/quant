"""单季增长计算的单测（构造数据，不依赖磁盘）。"""

from __future__ import annotations

import pandas as pd
import pytest

from quant.foundation.growth import calc_season_growth, growth_score


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "股票代码": [600000, 600000],
            "iDATE": [20220331, 20220630],
            "营业总收入": [100.0, 250.0],
            "营业总收入同比": [0.0, 25.0],
        }
    )


def test_calc_season_growth_income():
    df = _sample_df()
    seasons = [20220331, 20220630]
    result = calc_season_growth(df, 600000, seasons, "营业总收入")

    first = result[result["iDATE"] == 20220331].iloc[0]
    second = result[result["iDATE"] == 20220630].iloc[0]

    # 一季度：单季值即累计值，同比即总同比
    assert first["preYearIncome"] == pytest.approx(100.0)
    assert first["SeasonIncome"] == pytest.approx(100.0)
    assert first["SeasonIncomeGrowth"] == pytest.approx(0.0)

    # 二季度：单季 = 本期累计 - 上期累计 = 250 - 100 = 150
    assert second["preYearIncome"] == pytest.approx(250.0 / 1.25)      # 200
    assert second["SeasonIncome"] == pytest.approx(150.0)
    # 单季同比 = 150 / (200 - 100) - 1 = 50%
    assert second["SeasonIncomeGrowth"] == pytest.approx(50.0)


def test_growth_score_requires_q1_start():
    df = _sample_df().iloc[[1]].copy()  # 只有 20220630
    assert growth_score(df) is None


def test_growth_score_runs_for_both_types():
    df = _sample_df()
    df["净利润"] = [20.0, 60.0]
    df["净利润同比"] = [0.0, 50.0]

    result = growth_score(df)

    assert result is not None
    for column in ("SeasonIncome", "SeasonIncomeGrowth", "SeasonProfit", "SeasonProfitGrowth"):
        assert column in result.columns
    second = result[result["iDATE"] == 20220630].iloc[0]
    assert second["SeasonProfit"] == pytest.approx(40.0)
