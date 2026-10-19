"""说明书与代码一致性的测试。

这一层专门防止「文档写了、代码改了」的脱节：
    - 每个已注册的过滤器都必须有说明；
    - 说明里覆盖的参数必须与 __init__ 的真实参数完全一致；
    - 说明书里必须包含快照日期与过滤链机制的说明。
"""

from __future__ import annotations

import inspect

import pytest

from quant.filter import available_filters, get_filter_class
from quant.filter.guide import (
    FILTER_GUIDE,
    MECHANICS_DOC,
    SNAPSHOT_DOC,
    build_guide,
    describe_filter,
)

#: 界面上的分组（与 screener.py 的 GROUPS 保持一致，这里复制一份做交叉检查）
GROUPS = [
    ("基础", ["exclude_st", "min_listing"]),
    ("估值", ["market_cap", "pe", "pb", "ps",
              "pe_percentile", "pb_percentile", "ps_percentile"]),
    ("财务", ["roe", "debt_ratio", "gross_margin", "growth"]),
    ("行情技术", ["break_ma", "ma_align", "ma_trend", "ma_cross",
                  "price_change", "price_range", "volume_ratio", "turnover_rate"]),
]


def _init_params(name: str) -> list[str]:
    signature = inspect.signature(get_filter_class(name).__init__)
    return [p for p in signature.parameters if p != "self"]


def test_every_filter_is_documented():
    missing = [name for name in available_filters() if name not in FILTER_GUIDE]
    assert not missing, f"以下过滤器缺少说明: {missing}"


def test_no_doc_for_unknown_filter():
    extra = [name for name in FILTER_GUIDE if name not in available_filters()]
    assert not extra, f"说明里出现了未注册的过滤器: {extra}"


@pytest.mark.parametrize("name", sorted(FILTER_GUIDE))
def test_documented_params_match_signature(name: str):
    """说明里写的参数必须与 __init__ 的真实参数一一对应。"""
    documented = set(FILTER_GUIDE[name].get("params", {}))
    actual = set(_init_params(name))
    assert documented == actual, (
        f"{name} 的参数不一致：文档={sorted(documented)} 实际={sorted(actual)}"
    )


@pytest.mark.parametrize("name", sorted(FILTER_GUIDE))
def test_describe_filter_contains_params_and_examples(name: str):
    text = describe_filter(name)
    assert name in text
    for param in _init_params(name):
        assert param in text, f"{name}.{param} 没有出现在说明里"
    assert "例子" in text or name in ("pb_percentile", "ps_percentile")


def test_groups_cover_all_filters():
    grouped = {name for _group, names in GROUPS for name in names}
    assert grouped == set(available_filters()), (
        f"分组未覆盖: {set(available_filters()) - grouped}；"
        f"多余: {grouped - set(available_filters())}"
    )


def test_snapshot_doc_explains_as_of():
    assert "快照日期" in SNAPSHOT_DOC
    for keyword in ("YYYYMMDD", "20231229", "留空", "退市"):
        assert keyword in SNAPSHOT_DOC, f"快照说明缺少 {keyword}"


def test_mechanics_doc_explains_chain_and_nan():
    assert "过滤链" in MECHANICS_DOC
    for keyword in ("缺失", "「与」", "quant screen"):
        assert keyword in MECHANICS_DOC, f"机制说明缺少 {keyword}"


def test_build_guide_full_and_grouped():
    full = build_guide()
    assert SNAPSHOT_DOC in full
    assert MECHANICS_DOC in full
    for name in available_filters():
        assert f"● {name}" in full

    grouped = build_guide(GROUPS)
    assert "[估值]" in grouped
    assert "pe_percentile" in grouped


def test_guide_mentions_every_parameter():
    text = build_guide()
    for name in available_filters():
        for param in _init_params(name):
            assert param in text
