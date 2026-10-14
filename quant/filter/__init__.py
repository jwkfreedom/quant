"""可插拔选股过滤器。

快速使用::

    from quant.filter import FilterContext, FilterChain

    with FilterContext(as_of=20231229) as ctx:
        result = FilterChain.from_specs([
            "exclude_st",
            "min_listing:bars=250",
            "market_cap:max=80",
            "growth:field=season_income_growth,min=30",
            "price_change:bars=20,min=10",
        ]).run(ctx)
    print(result.report())
    print(result.frame[["symbol", "name", "market_cap", "season_income_growth"]])

自定义过滤器::

    from quant.filter import register

    @register
    class SmallCap:
        name = "small_cap"
        description = "市值小于 80 亿"
        def __init__(self, max_yi=80):
            self.max_yi = max_yi
        def apply(self, df, ctx):
            return df[df["market_cap"] <= self.max_yi * 1e8]
"""

from __future__ import annotations

from quant.filter.base import (
    Filter,
    FilterContext,
    available_filters,
    clear_registry,
    describe_filters,
    get_filter_class,
    register,
)
from quant.filter.chain import FilterChain, ScreenResult, build_filter, parse_spec

# 导入内置过滤器以触发注册
from quant.filter import builtin  # noqa: E402,F401  (必须在 base 之后)

__all__ = [
    "Filter",
    "FilterContext",
    "FilterChain",
    "ScreenResult",
    "register",
    "available_filters",
    "describe_filters",
    "get_filter_class",
    "clear_registry",
    "build_filter",
    "parse_spec",
]
