"""内置选股过滤器。

约定
----
- 每个过滤器的参数都是**显式关键字参数**，便于 CLI 用 `name:k=v,k=v` 描述；
- `min`/`max` 为 None 表示该侧不限制；
- 金额单位统一用「元」，市值类过滤器额外提供 `*_yi`（亿元）参数。
"""

from __future__ import annotations

import pandas as pd

from quant.filter.base import FilterContext, register


def _between(series: pd.Series, minimum, maximum) -> pd.Series:
    """通用的区间判断：NaN 一律剔除。"""
    mask = series.notna()
    if minimum is not None:
        mask &= series >= minimum
    if maximum is not None:
        mask &= series <= maximum
    return mask


class _Base:
    name = ""
    description = ""

    def __repr__(self) -> str:  # pragma: no cover - 便于日志
        params = ", ".join(f"{k}={v!r}" for k, v in vars(self).items())
        return f"{type(self).__name__}({params})"


# --------------------------------------------------------------------------
# 基础面
# --------------------------------------------------------------------------
@register
class ExcludeSt(_Base):
    name = "exclude_st"
    description = "剔除 ST / 退市 / 停牌类名称"

    def __init__(self, keywords: str = "ST,退"):
        self.keywords = keywords

    def apply(self, df: pd.DataFrame, ctx: FilterContext) -> pd.DataFrame:
        words = [w.strip() for w in str(self.keywords).split(",") if w.strip()]
        if not words or "name" not in df.columns:
            return df
        name = df["name"].fillna("").astype(str)
        mask = ~name.str.contains("|".join(words), case=False, regex=True)
        return df[mask]


@register
class MinListing(_Base):
    name = "min_listing"
    description = "上市满 N 根 K 线（剔除次新股）"

    #: 需要 FilterChain 预先并入上市信息
    needs_listing = True

    def __init__(self, bars: int = 250):
        self.bars = int(bars)

    def apply(self, df: pd.DataFrame, ctx: FilterContext) -> pd.DataFrame:
        if "listed_bars" not in df.columns:
            df = df.merge(ctx.listing(), on="symbol", how="left")
        return df[pd.to_numeric(df["listed_bars"], errors="coerce").fillna(0) >= self.bars]


@register
class MarketCap(_Base):
    name = "market_cap"
    description = "总市值区间（参数 min/max 单位：亿元）"

    def __init__(self, min: float | None = None, max: float | None = None):  # noqa: A002
        self.min = min
        self.max = max

    def apply(self, df: pd.DataFrame, ctx: FilterContext) -> pd.DataFrame:
        cap = pd.to_numeric(df.get("market_cap"), errors="coerce")
        low = None if self.min is None else float(self.min) * 1e8
        high = None if self.max is None else float(self.max) * 1e8
        return df[_between(cap, low, high)]


@register
class Pe(_Base):
    name = "pe"
    description = "市盈率(TTM) 区间"

    def __init__(self, min: float | None = None, max: float | None = None):  # noqa: A002
        self.min = min
        self.max = max

    def apply(self, df: pd.DataFrame, ctx: FilterContext) -> pd.DataFrame:
        pe = pd.to_numeric(df.get("pe"), errors="coerce")
        return df[_between(pe, self.min, self.max)]


@register
class Pb(_Base):
    name = "pb"
    description = "市净率(TTM) 区间"

    def __init__(self, min: float | None = None, max: float | None = None):  # noqa: A002
        self.min = min
        self.max = max

    def apply(self, df: pd.DataFrame, ctx: FilterContext) -> pd.DataFrame:
        pb = pd.to_numeric(df.get("pb"), errors="coerce")
        return df[_between(pb, self.min, self.max)]


@register
class Growth(_Base):
    name = "growth"
    description = "单季增长区间，field 取 season_income_growth / season_profit_growth"

    def __init__(self, field: str = "season_income_growth", min: float | None = None,
                 max: float | None = None):  # noqa: A002
        self.field = field
        self.min = min
        self.max = max

    def apply(self, df: pd.DataFrame, ctx: FilterContext) -> pd.DataFrame:
        if self.field not in df.columns:
            raise KeyError(f"快照中没有列 {self.field}，可选: season_income_growth / season_profit_growth")
        values = pd.to_numeric(df[self.field], errors="coerce")
        return df[_between(values, self.min, self.max)]


@register
class DebtRatio(_Base):
    name = "debt_ratio"
    description = "资产负债率(%) 上限"

    def __init__(self, max: float | None = None):  # noqa: A002
        self.max = max

    def apply(self, df: pd.DataFrame, ctx: FilterContext) -> pd.DataFrame:
        values = pd.to_numeric(df.get("debt_ratio"), errors="coerce")
        return df[_between(values, None, self.max)]


@register
class Roe(_Base):
    name = "roe"
    description = "净资产收益率(%) 下限"

    def __init__(self, min: float | None = None):  # noqa: A002
        self.min = min

    def apply(self, df: pd.DataFrame, ctx: FilterContext) -> pd.DataFrame:
        values = pd.to_numeric(df.get("roe"), errors="coerce")
        return df[_between(values, self.min, None)]


# --------------------------------------------------------------------------
# 行情 / 时序
# --------------------------------------------------------------------------
def _history_wide(ctx: FilterContext, bars: int, field: str) -> pd.DataFrame:
    """把最近 bars 根 K 线透视成「symbol × 时间」宽表（时间由远到近）。"""
    hist = ctx.history(bars)
    hist = hist.sort_values(["symbol", "date"])
    wide = hist.pivot_table(index="symbol", columns="date", values=field, aggfunc="last")
    return wide


@register
class PriceChange(_Base):
    name = "price_change"
    description = "最近 N 个交易日涨跌幅区间（%），基于前复权收盘价"

    def __init__(self, bars: int = 20, min: float | None = None, max: float | None = None):  # noqa: A002
        self.bars = int(bars)
        self.min = min
        self.max = max

    def apply(self, df: pd.DataFrame, ctx: FilterContext) -> pd.DataFrame:
        wide = _history_wide(ctx, self.bars + 1, "close")
        if wide.shape[1] < 2:
            return df.iloc[0:0]
        change = (wide.iloc[:, -1] / wide.iloc[:, 0] - 1) * 100
        change = change.reindex(df["symbol"])
        return df[_between(change.reset_index(drop=True), self.min, self.max).to_numpy()]


@register
class PriceRange(_Base):
    name = "price_range"
    description = "最近 N 个交易日 (最高-最低)/最低 的振幅上限（%）"

    def __init__(self, bars: int = 5, max: float | None = None):  # noqa: A002
        self.bars = int(bars)
        self.max = max

    def apply(self, df: pd.DataFrame, ctx: FilterContext) -> pd.DataFrame:
        hist = ctx.history(self.bars)
        grouped = hist.groupby("symbol").agg(high=("high", "max"), low=("low", "min"))
        amplitude = (grouped["high"] - grouped["low"]) / grouped["low"] * 100
        amplitude = amplitude.reindex(df["symbol"]).reset_index(drop=True)
        return df[_between(amplitude, None, self.max).to_numpy()]


@register
class MaTrend(_Base):
    name = "ma_trend"
    description = "均线多头：short 日均线在 long 日均线之上"

    def __init__(self, short: int = 5, long: int = 20):  # noqa: A002
        self.short = int(short)
        self.long = int(long)

    def apply(self, df: pd.DataFrame, ctx: FilterContext) -> pd.DataFrame:
        if self.short >= self.long:
            raise ValueError("short 必须小于 long")
        hist = ctx.history(self.long).sort_values(["symbol", "date"])
        grouped = hist.groupby("symbol")["close"]
        short_ma = grouped.apply(lambda s: s.tail(self.short).mean())
        long_ma = grouped.mean()
        mask = (short_ma > long_ma).reindex(df["symbol"]).fillna(False).reset_index(drop=True)
        return df[mask.to_numpy()]


@register
class MaCross(_Base):
    name = "ma_cross"
    description = "均线金叉：short 日均线在最近 window 日内上穿 long 日均线"

    def __init__(self, short: int = 5, long: int = 20, window: int = 3):  # noqa: A002
        self.short = int(short)
        self.long = int(long)
        self.window = int(window)

    def apply(self, df: pd.DataFrame, ctx: FilterContext) -> pd.DataFrame:
        bars = self.long + self.window
        wide = _history_wide(ctx, bars, "close")
        if wide.shape[1] < self.long + 1:
            return df.iloc[0:0]
        # 用转置后的 rolling，避免 pandas 对 rolling(axis=1) 的弃用告警
        short_ma = wide.T.rolling(self.short).mean().T
        long_ma = wide.T.rolling(self.long).mean().T
        above = short_ma > long_ma
        crossed = above.iloc[:, -self.window:].any(axis=1) & (~above.iloc[:, -self.window - 1])
        crossed = crossed.reindex(df["symbol"]).fillna(False)
        return df[crossed.to_numpy()]


@register
class VolumeRatio(_Base):
    name = "volume_ratio"
    description = "当日成交量 / 最近 N 日均量 的区间"

    def __init__(self, bars: int = 20, min: float | None = None, max: float | None = None):  # noqa: A002
        self.bars = int(bars)
        self.min = min
        self.max = max

    def apply(self, df: pd.DataFrame, ctx: FilterContext) -> pd.DataFrame:
        hist = ctx.history(self.bars).sort_values(["symbol", "date"])
        grouped = hist.groupby("symbol")["volume"]
        mean_volume = grouped.apply(lambda s: s.iloc[:-1].tail(self.bars - 1).mean())
        last_volume = grouped.last()
        ratio = last_volume / mean_volume
        ratio = ratio.reindex(df["symbol"]).reset_index(drop=True)
        return df[_between(ratio, self.min, self.max).to_numpy()]


@register
class Ps(_Base):
    name = "ps"
    description = "市销率(总市值 / 营业总收入TTM) 区间"

    def __init__(self, min: float | None = None, max: float | None = None):  # noqa: A002
        self.min = min
        self.max = max

    def apply(self, df: pd.DataFrame, ctx: FilterContext) -> pd.DataFrame:
        values = pd.to_numeric(df.get("ps"), errors="coerce")
        return df[_between(values, self.min, self.max)]


@register
class GrossMargin(_Base):
    name = "gross_margin"
    description = "销售毛利率(%) 区间"

    def __init__(self, min: float | None = None, max: float | None = None):  # noqa: A002
        self.min = min
        self.max = max

    def apply(self, df: pd.DataFrame, ctx: FilterContext) -> pd.DataFrame:
        values = pd.to_numeric(df.get("gross_margin"), errors="coerce")
        return df[_between(values, self.min, self.max)]


# --------------------------------------------------------------------------
# 估值历史分位
# --------------------------------------------------------------------------
#: 窗口年数 -> 快照里的分位列
_PERCENTILE_FIELDS: dict[int, str] = {
    3: "pe_pct_3y",
    5: "pe_pct_5y",
    10: "pe_pct_10y",
    0: "pe_pct_all",
}


class _PercentileBase(_Base):
    """分位过滤器基类。

    分位含义：窗口内「估值低于当前」的交易日占比（%）。
    分位 ≤ 10 表示当前估值处于窗口内最低的 10% —— 窗口内至少 90% 的交易日更贵。
    数据来自 `valuation_percentile` 表（`quant rebuild-valuation` 生成）。
    """

    metric = "pe"

    def __init__(self, window_years: int = 10, min: float | None = None,  # noqa: A002
                 max: float | None = None):  # noqa: A002
        self.window_years = int(window_years)
        self.min = min
        self.max = max

    @property
    def column(self) -> str:
        if self.window_years not in _PERCENTILE_FIELDS:
            raise ValueError(
                f"window_years 只支持 {sorted(_PERCENTILE_FIELDS)}，收到 {self.window_years}"
            )
        if self.metric == "pe":
            return _PERCENTILE_FIELDS[self.window_years]
        if self.window_years == 10:
            return f"{self.metric}_pct_10y"
        raise ValueError(f"{self.metric} 分位目前只提供 10 年窗口")

    def apply(self, df: pd.DataFrame, ctx: FilterContext) -> pd.DataFrame:
        column = self.column
        if column not in df.columns:
            raise KeyError(
                f"快照里没有 {column}，请先运行 quant rebuild-valuation"
            )
        values = pd.to_numeric(df[column], errors="coerce")
        return df[_between(values, self.min, self.max)]


@register
class PePercentile(_PercentileBase):
    name = "pe_percentile"
    description = "PE 历史分位区间（window_years 取 3/5/10/0，0=全历史）"
    metric = "pe"


@register
class PbPercentile(_PercentileBase):
    name = "pb_percentile"
    description = "PB 历史分位(10年) 区间"
    metric = "pb"


@register
class PsPercentile(_PercentileBase):
    name = "ps_percentile"
    description = "PS 历史分位(10年) 区间"
    metric = "ps"


# --------------------------------------------------------------------------
# 均线形态
# --------------------------------------------------------------------------
def _parse_periods(value, default=(5, 10, 20)) -> list[int]:
    """把 '5-10-20' / '5,10,20' / [5,10,20] 解析成正整数列表。"""
    if value is None:
        return list(default)
    if isinstance(value, (list, tuple)):
        return [int(v) for v in value]
    text = str(value).replace(",", "-").replace(" ", "")
    periods = [int(part) for part in text.split("-") if part]
    if not periods:
        raise ValueError(f"无法解析均线周期: {value!r}")
    return periods


@register
class BreakMa(_Base):
    name = "break_ma"
    description = "突破 N 日均线（mode=cross 前一日在下当日在上；mode=above 站上均线）"

    def __init__(self, period: int = 5, mode: str = "cross"):
        self.period = int(period)
        self.mode = mode

    def apply(self, df: pd.DataFrame, ctx: FilterContext) -> pd.DataFrame:
        if self.period < 1:
            raise ValueError("period 必须 >= 1")
        if self.mode not in ("cross", "above"):
            raise ValueError("mode 只能是 'cross' 或 'above'")

        bars = self.period if self.mode == "above" else self.period + 1
        wide = _history_wide(ctx, bars, "close")
        if wide.shape[1] < bars:
            return df.iloc[0:0]

        ma = wide.T.rolling(self.period).mean().T
        last_close, last_ma = wide.iloc[:, -1], ma.iloc[:, -1]

        if self.mode == "above":
            mask = last_close > last_ma
        else:
            prev_close, prev_ma = wide.iloc[:, -2], ma.iloc[:, -2]
            mask = (prev_close <= prev_ma) & (last_close > last_ma)

        mask = mask.reindex(df["symbol"]).fillna(False).reset_index(drop=True)
        return df[mask.to_numpy()]


@register
class MaAlign(_Base):
    name = "ma_align"
    description = "均线多头排列，periods 形如 5-10-20（要求 MA5 > MA10 > MA20）"

    def __init__(self, periods="5-10-20"):
        self.periods = _parse_periods(periods)

    def apply(self, df: pd.DataFrame, ctx: FilterContext) -> pd.DataFrame:
        # 按传入顺序判断：5-10-20 表示 MA5 > MA10 > MA20（多头排列）
        periods = list(self.periods)
        if len(periods) < 2 or min(periods) < 1:
            raise ValueError("periods 至少要有两个正整数周期")

        wide = _history_wide(ctx, max(periods), "close")
        if wide.shape[1] < max(periods):
            return df.iloc[0:0]

        mas = {p: wide.T.rolling(p).mean().T.iloc[:, -1] for p in periods}
        mask = pd.Series(True, index=wide.index)
        for shorter, longer in zip(periods, periods[1:]):
            mask &= mas[shorter] > mas[longer]

        mask = mask.reindex(df["symbol"]).fillna(False).reset_index(drop=True)
        return df[mask.to_numpy()]


@register
class TurnoverRate(_Base):
    name = "turnover_rate"
    description = "换手率(%) 区间"

    def __init__(self, min: float | None = None, max: float | None = None):  # noqa: A002
        self.min = min
        self.max = max

    def apply(self, df: pd.DataFrame, ctx: FilterContext) -> pd.DataFrame:
        values = pd.to_numeric(df.get("turnover_rate"), errors="coerce")
        return df[_between(values, self.min, self.max)]
