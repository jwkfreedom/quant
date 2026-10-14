"""过滤器与过滤链单测（使用合成数据库）。"""

from __future__ import annotations

import pandas as pd
import pytest

from quant.data import store
from quant.filter import (
    FilterChain,
    FilterContext,
    available_filters,
    build_filter,
    parse_spec,
)
from quant.filter.builtin import ExcludeSt, Growth, MarketCap, MinListing, Pe

from conftest import DATES, SYMBOLS


@pytest.fixture
def ctx(sample_db):
    with store.open_db(sample_db) as conn:
        with FilterContext(conn=conn, as_of=int(DATES[-1].replace("-", ""))) as context:
            yield context


# --------------------------------------------------------------------------
# 解析
# --------------------------------------------------------------------------
def test_parse_spec_without_params():
    assert parse_spec("exclude_st") == ("exclude_st", {})


def test_parse_spec_with_params():
    name, params = parse_spec("market_cap:max=80,min=10")
    assert name == "market_cap"
    assert params == {"max": 80, "min": 10}


def test_parse_spec_type_casting():
    _name, params = parse_spec("x:a=1.5,b=true,c=hello,d=none")
    assert params == {"a": 1.5, "b": True, "c": "hello", "d": None}


def test_parse_spec_errors():
    with pytest.raises(ValueError):
        parse_spec("")
    with pytest.raises(ValueError):
        parse_spec("market_cap:max")


def test_build_filter_unknown_name():
    with pytest.raises(KeyError):
        build_filter("no_such_filter")


def test_build_filter_bad_params():
    with pytest.raises(TypeError):
        build_filter("market_cap:wrong=1")


def test_registry_contains_builtins():
    names = available_filters()
    for expected in ("exclude_st", "market_cap", "growth", "pe", "pb", "ma_trend", "volume_ratio"):
        assert expected in names


# --------------------------------------------------------------------------
# 单个过滤器
# --------------------------------------------------------------------------
def test_market_cap_filter(ctx):
    df = ctx.snapshot()
    # 合成数据里 000001 收盘价 ~16 元、股本 1e9 -> 市值 ~160 亿
    filtered = MarketCap(max=200).apply(df, ctx)
    assert len(filtered) >= 1
    assert (filtered["market_cap"] <= 200e8).all()

    assert MarketCap(max=0.0001).apply(df, ctx).empty


def test_growth_filter(ctx):
    df = ctx.snapshot()
    filtered = Growth(field="season_income_growth", min=35).apply(df, ctx)
    assert len(filtered) == len(SYMBOLS)  # 最新季度都是 40%

    assert Growth(field="season_income_growth", min=100).apply(df, ctx).empty


def test_growth_filter_bad_field(ctx):
    with pytest.raises(KeyError):
        Growth(field="not_a_column").apply(ctx.snapshot(), ctx)


def test_pe_filter(ctx):
    df = ctx.snapshot()
    filtered = Pe(max=5).apply(df, ctx)
    assert (filtered["pe"] <= 5).all()


def test_min_listing_filter(ctx):
    df = ctx.snapshot()
    assert len(MinListing(bars=10).apply(df, ctx)) == len(SYMBOLS)
    assert MinListing(bars=1000).apply(df, ctx).empty


def test_exclude_st_removes_matching_names(ctx):
    df = ctx.snapshot().copy()
    df.loc[0, "name"] = "ST测试"
    kept = ExcludeSt().apply(df, ctx)
    assert len(kept) == len(df) - 1


# --------------------------------------------------------------------------
# 过滤链
# --------------------------------------------------------------------------
def test_chain_records_steps(ctx):
    chain = FilterChain.from_specs(["exclude_st", "market_cap:max=1000"])
    result = chain.run(ctx)
    assert [step[0] for step in result.steps] == ["exclude_st", "market_cap"]
    assert result.steps[0][1] == len(SYMBOLS)
    assert len(result.frame) == result.steps[-1][2]


def test_chain_report_contains_names(ctx):
    result = FilterChain.from_specs(["exclude_st"]).run(ctx)
    report = result.report()
    assert "exclude_st" in report
    assert "最终结果" in report


def test_chain_stops_when_empty(ctx):
    result = FilterChain.from_specs(["market_cap:max=0.00001", "growth:min=0"]).run(ctx)
    assert result.frame.empty
    assert len(result.steps) == 1  # 空了就短路


def test_chain_add(ctx):
    chain = FilterChain().add(ExcludeSt())
    assert len(chain.filters) == 1


# --------------------------------------------------------------------------
# 估值分位与形态类过滤器
# --------------------------------------------------------------------------
def test_percentile_filters(ctx):
    from quant.filter.builtin import PePercentile, PbPercentile, PsPercentile

    df = ctx.snapshot()
    # conftest 里三只股票的 pe_pct 分别是 5 / 6 / 7
    assert len(PePercentile(window_years=10, max=6).apply(df, ctx)) == 2
    assert len(PePercentile(window_years=3, max=100).apply(df, ctx)) == 3
    assert len(PbPercentile(max=16).apply(df, ctx)) == 2
    assert len(PsPercentile(max=26).apply(df, ctx)) == 2


def test_percentile_bad_window(ctx):
    from quant.filter.builtin import PePercentile

    with pytest.raises(ValueError):
        PePercentile(window_years=7).apply(ctx.snapshot(), ctx)


def test_ps_and_margin_filters(ctx):
    from quant.filter.builtin import GrossMargin, Ps

    df = ctx.snapshot()
    assert len(Ps(min=0).apply(df, ctx)) == len(SYMBOLS)
    assert Ps(max=1e-9).apply(df, ctx).empty
    # 合成数据里 gross_margin 固定为 30
    assert len(GrossMargin(min=20).apply(df, ctx)) == len(SYMBOLS)
    assert GrossMargin(min=50).apply(df, ctx).empty


def test_break_ma_filter(ctx):
    from quant.filter.builtin import BreakMa

    df = ctx.snapshot()
    # 合成数据收盘价单调上涨 -> 一直站在 5 日线上方，但不会发生"上穿"
    assert len(BreakMa(period=5, mode="above").apply(df, ctx)) == len(SYMBOLS)
    assert BreakMa(period=5, mode="cross").apply(df, ctx).empty


def test_break_ma_validation(ctx):
    from quant.filter.builtin import BreakMa

    with pytest.raises(ValueError):
        BreakMa(period=5, mode="wrong").apply(ctx.snapshot(), ctx)


def test_ma_align_filter(ctx):
    from quant.filter.builtin import MaAlign

    df = ctx.snapshot()
    # 单调上涨 -> MA5 > MA10 > MA20
    assert len(MaAlign("5-10-20").apply(df, ctx)) == len(SYMBOLS)
    assert MaAlign("20-10-5").apply(df, ctx).empty


def test_parse_periods():
    from quant.filter.builtin import _parse_periods

    assert _parse_periods("5-10-20") == [5, 10, 20]
    assert _parse_periods("5,10,20") == [5, 10, 20]
    assert _parse_periods([5, 20]) == [5, 20]
    assert _parse_periods(None) == [5, 10, 20]
