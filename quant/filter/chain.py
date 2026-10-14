"""过滤链与选股结果。

```python
from quant.filter import FilterChain, FilterContext
from quant.filter.builtin import ExcludeSt, MarketCap, Growth   # noqa: F401

ctx = FilterContext(as_of=20231229)
with ctx:
    chain = FilterChain.from_specs(["exclude_st", "market_cap:max=80", "growth:min=30"])
    result = chain.run(ctx)
print(result.steps)     # 每一步剩余多少只
print(result.frame.head())
```
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from quant.filter import base

logger = logging.getLogger(__name__)


def parse_spec(spec: str) -> tuple[str, dict[str, Any]]:
    """把 `name:k=v,k=v` 解析成 (name, kwargs)。

    >>> parse_spec("market_cap:max=80")
    ('market_cap', {'max': 80})
    >>> parse_spec("exclude_st")
    ('exclude_st', {})
    """
    if not spec or not spec.strip():
        raise ValueError("过滤器描述不能为空")
    name, _, raw_params = spec.partition(":")
    name = name.strip()
    kwargs: dict[str, Any] = {}
    if raw_params.strip():
        for item in raw_params.split(","):
            item = item.strip()
            if not item:
                continue
            if "=" not in item:
                raise ValueError(f"参数必须是 key=value 形式: {item!r}（来自 {spec!r}）")
            key, _, value = item.partition("=")
            kwargs[key.strip()] = _cast(value.strip())
    return name, kwargs


def _cast(value: str) -> Any:
    """把字符串参数转成 int / float / bool / str。"""
    lowered = value.lower()
    if lowered in ("true", "yes"):
        return True
    if lowered in ("false", "no"):
        return False
    if lowered in ("none", "null", ""):
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def build_filter(spec: str) -> base.Filter:
    """按描述创建过滤器实例。"""
    name, kwargs = parse_spec(spec)
    cls = base.get_filter_class(name)
    try:
        return cls(**kwargs)
    except TypeError as exc:
        raise TypeError(f"过滤器 {name} 参数不匹配: {exc}") from exc


@dataclass
class ScreenResult:
    """选股结果。"""

    frame: pd.DataFrame
    steps: list[tuple[str, int, int]] = field(default_factory=list)
    as_of: int | None = None

    def __len__(self) -> int:
        return len(self.frame)

    def report(self) -> str:
        """生成可打印的过滤过程说明。"""
        lines = [f"选股日期: {self.as_of}", "-" * 52]
        total = self.steps[0][1] if self.steps else len(self.frame)
        lines.append(f"{'初始股票池':<28}{total:>8} 只")
        for name, before, after in self.steps:
            lines.append(f"  - {name:<26}{after:>8} 只  (剔除 {before - after})")
        lines.append("-" * 52)
        lines.append(f"{'最终结果':<28}{len(self.frame):>8} 只")
        return "\n".join(lines)


class FilterChain:
    """按顺序执行一组过滤器，并记录每一步的剩余数量。"""

    def __init__(self, filters: list[base.Filter] | None = None):
        self.filters: list[base.Filter] = list(filters or [])

    @classmethod
    def from_specs(cls, specs: list[str]) -> "FilterChain":
        """由 `name:k=v` 描述列表构造。"""
        return cls([build_filter(spec) for spec in specs])

    def add(self, filter_: base.Filter) -> "FilterChain":
        self.filters.append(filter_)
        return self

    def run(self, ctx: base.FilterContext | None = None, *, with_listing: bool = False) -> ScreenResult:
        """执行过滤链。传入 ctx 时复用其连接与缓存。"""
        own = ctx is None
        if own:
            ctx = base.FilterContext()

        with ctx:
            df = ctx.snapshot()
            needs_listing = with_listing or any(getattr(f, "needs_listing", False) for f in self.filters)
            if needs_listing and "listed_bars" not in df.columns:
                df = df.merge(ctx.listing(), on="symbol", how="left")

            steps: list[tuple[str, int, int]] = []
            for filter_ in self.filters:
                before = len(df)
                df = filter_.apply(df, ctx)
                after = len(df)
                steps.append((getattr(filter_, "name", type(filter_).__name__), before, after))
                logger.info("%s: %d -> %d", steps[-1][0], before, after)
                if after == 0:
                    break

            return ScreenResult(frame=df.reset_index(drop=True), steps=steps, as_of=ctx.as_of)
