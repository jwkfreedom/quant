"""可插拔选股过滤器（阶段 2.3 实装）。

设计目标：从全市场股票中按可组合的条件筛选，新增条件只需实现 Filter 协议并注册。

    from quant.filter import Filter, register, get_filters

    class SmallCap(Filter):
        name = "small_cap"

        def apply(self, df):
            return df[df["market_cap"] < 8e9]

    register(SmallCap())

当前仅提供协议与注册表，尚未内置任何过滤器。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd

__all__ = ["Filter", "register", "get_filters", "available_filters", "clear_registry"]


@runtime_checkable
class Filter(Protocol):
    """选股过滤器协议。

    实现者需提供 name（唯一标识）与 apply（返回过滤后的 DataFrame）。
    """

    name: str
    description: str

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:  # pragma: no cover - 协议定义
        ...


_REGISTRY: dict[str, Filter] = {}


def register(filter_: Filter) -> Filter:
    """注册一个过滤器，同名会覆盖。"""
    _REGISTRY[filter_.name] = filter_
    return filter_


def get_filters(names: list[str] | None = None) -> list[Filter]:
    """按名称取出过滤器；names 为 None 时返回全部。"""
    if names is None:
        return list(_REGISTRY.values())
    missing = [n for n in names if n not in _REGISTRY]
    if missing:
        raise KeyError(f"未注册的过滤器: {missing}；可用: {sorted(_REGISTRY)}")
    return [_REGISTRY[n] for n in names]


def available_filters() -> list[str]:
    """返回已注册过滤器名称。"""
    return sorted(_REGISTRY)


def clear_registry() -> None:
    """清空注册表（测试用）。"""
    _REGISTRY.clear()
