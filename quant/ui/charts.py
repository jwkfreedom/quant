"""matplotlib 绘图函数。

只负责「数据 -> Figure」，不依赖任何 GUI 库，
因此可以直接单测（构造图形不报错）或在 GUI 里嵌入。
"""

from __future__ import annotations

import logging

import matplotlib

matplotlib.use("Agg", force=False)  # GUI 嵌入时会由后端覆盖

import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

logger = logging.getLogger(__name__)

#: 中文字体（找不到就退回默认，图形仍可显示，只是中文变方框）
for _font in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial Unicode MS"):
    if any(_font.lower() in f.name.lower() for f in matplotlib.font_manager.fontManager.ttflist):
        plt.rcParams["font.sans-serif"] = [_font]
        break
plt.rcParams["axes.unicode_minus"] = False


def _empty_figure(message: str = "暂无数据") -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.text(0.5, 0.5, message, ha="center", va="center", fontsize=12, color="#888")
    ax.set_axis_off()
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------
# K 线
# --------------------------------------------------------------------------
def kline_figure(
    df: pd.DataFrame,
    *,
    title: str = "",
    ma_periods=(5, 10, 20, 60),
    volume: bool = True,
    max_bars: int = 500,
) -> plt.Figure:
    """K 线 + 均线 + 成交量。

    参数 df 需包含 date / open / high / low / close / volume（前复权口径）。
    """
    if df is None or df.empty:
        return _empty_figure()

    data = df.tail(max_bars).copy()
    data["date"] = pd.to_datetime(data["date"])
    x = np.arange(len(data))

    if volume:
        fig, (ax, ax_vol) = plt.subplots(
            2, 1, figsize=(12, 6), sharex=True, gridspec_kw={"height_ratios": [3, 1]}
        )
    else:
        fig, ax = plt.subplots(figsize=(12, 5))
        ax_vol = None

    up = data["close"] >= data["open"]
    colors = np.where(up, "#d32f2f", "#388e3c")

    ax.vlines(x, data["low"], data["high"], color=colors, linewidth=0.8)
    ax.bar(x[up], (data["close"] - data["open"])[up], bottom=data["open"][up],
           color="#d32f2f", width=0.6)
    ax.bar(x[~up], (data["open"] - data["close"])[~up], bottom=data["close"][~up],
           color="#388e3c", width=0.6)

    for period in ma_periods or ():
        if len(data) >= period:
            ax.plot(x, data["close"].rolling(period).mean(), linewidth=0.9,
                    label=f"MA{period}")

    ax.set_title(title or "K 线")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.25)

    if ax_vol is not None:
        ax_vol.bar(x, data["volume"], color=colors, width=0.6)
        ax_vol.set_ylabel("成交量")
        ax_vol.grid(alpha=0.25)

    step = max(1, len(data) // 12)
    ticks = x[::step]
    labels = data["date"].dt.strftime("%Y-%m").iloc[::step]
    (ax_vol or ax).set_xticks(ticks)
    (ax_vol or ax).set_xticklabels(labels, rotation=30, ha="right", fontsize=8)

    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------
# 估值带
# --------------------------------------------------------------------------
def valuation_band_figure(
    valuation: pd.DataFrame,
    *,
    title: str = "",
    price_column: str = "close",
    quantiles=(0.1, 0.3, 0.5, 0.7, 0.9),
    max_points: int = 1500,
) -> plt.Figure:
    """价格 + PE 分位通道。

    做法：把窗口内的 PE 分位点换算成对应价格（PE 分位价 = 分位 PE × 当前 EPS），
    这样图上能直接看出「现在贵不贵」。
    """
    if valuation is None or valuation.empty or price_column not in valuation.columns:
        return _empty_figure()

    data = valuation.dropna(subset=[price_column, "pe"]).copy()
    data = data[data["pe"] > 0]
    if data.empty:
        return _empty_figure("缺少有效估值数据")

    if len(data) > max_points:
        data = data.iloc[:: max(1, len(data) // max_points)]

    data["date"] = pd.to_datetime(data["date"])
    fig, ax = plt.subplots(figsize=(12, 5))

    ax.plot(data["date"], data[price_column], color="#1565c0", linewidth=1.2, label="价格")

    eps = data["eps_ttm"].iloc[-1] if "eps_ttm" in data.columns else np.nan
    if pd.notna(eps) and eps and eps > 0:
        for q in quantiles:
            pe_q = float(data["pe"].quantile(q))
            ax.axhline(pe_q * eps, color="#999", linewidth=0.8, linestyle="--", alpha=0.8)
            ax.text(data["date"].iloc[0], pe_q * eps, f" PE {int(q * 100)}%分位",
                    fontsize=7, va="bottom", color="#666")

    ax.set_title(title or "估值带（价格 vs PE 分位通道）")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    fig.autofmt_xdate()
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------
# 财务
# --------------------------------------------------------------------------
def financial_figure(
    fundamental: pd.DataFrame,
    growth: pd.DataFrame = None,
    *,
    title: str = "",
    max_points: int = 40,
) -> plt.Figure:
    """营收 / 净利润（柱）+ 单季同比（线）。"""
    if fundamental is None or fundamental.empty:
        return _empty_figure("暂无基本面数据")

    data = fundamental.sort_values("season").tail(max_points).copy()
    data["label"] = data["season"].astype(str)

    fig, ax = plt.subplots(figsize=(12, 4.5))
    x = np.arange(len(data))
    width = 0.4

    ax.bar(x - width / 2, pd.to_numeric(data["total_revenue"], errors="coerce") / 1e8,
           width, label="营业总收入(亿)", color="#5c6bc0")
    ax.bar(x + width / 2, pd.to_numeric(data["net_profit"], errors="coerce") / 1e8,
           width, label="净利润(亿)", color="#ef6c00")
    ax.set_ylabel("亿元")
    ax.grid(alpha=0.25, axis="y")

    if growth is not None and not growth.empty:
        g = growth.sort_values("season").tail(max_points)
        ax2 = ax.twinx()
        ax2.plot(x[: len(g)], g["season_income_growth"], color="#2e7d32",
                 marker="o", markersize=3, label="单季营收同比(%)")
        ax2.set_ylabel("同比 %")
        ax2.axhline(0, color="#bbb", linewidth=0.8)
        lines, labels = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines + lines2, labels + labels2, loc="upper left", fontsize=8)
    else:
        ax.legend(loc="upper left", fontsize=8)

    step = max(1, len(data) // 12)
    ax.set_xticks(x[::step])
    ax.set_xticklabels(data["label"].iloc[::step], rotation=45, ha="right", fontsize=8)
    ax.set_title(title or "营收与利润")
    fig.tight_layout()
    return fig


def valuation_history_figure(
    valuation: pd.DataFrame,
    *,
    title: str = "",
    max_points: int = 1500,
) -> plt.Figure:
    """PE / PB / PS 历史曲线。"""
    if valuation is None or valuation.empty:
        return _empty_figure()

    data = valuation.copy()
    if len(data) > max_points:
        data = data.iloc[:: max(1, len(data) // max_points)]
    data["date"] = pd.to_datetime(data["date"])

    fig, axes = plt.subplots(3, 1, figsize=(12, 7), sharex=True)
    for ax, (column, label, color) in zip(
        axes,
        (("pe", "PE(TTM)", "#1565c0"), ("pb", "PB(TTM)", "#6a1b9a"), ("ps", "PS(TTM)", "#00897b")),
    ):
        if column in data.columns:
            series = pd.to_numeric(data[column], errors="coerce").where(lambda s: s > 0)
            ax.plot(data["date"], series, color=color, linewidth=1)
            ax.set_ylabel(label)
            ax.grid(alpha=0.25)
    axes[0].set_title(title or "估值历史")
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    fig.autofmt_xdate()
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------
# 净值曲线
# --------------------------------------------------------------------------
def equity_figure(result, *, title: str = "") -> plt.Figure:
    """回测净值曲线 vs 买入持有基准。"""
    curve = getattr(result, "equity_curve", None)
    if curve is None or curve.empty:
        return _empty_figure("没有净值数据")

    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.plot(pd.to_datetime(curve["date"]), curve["value"], label="策略", color="#1565c0")

    benchmark = getattr(result, "benchmark_curve", None)
    if benchmark is not None and not benchmark.empty:
        ax.plot(pd.to_datetime(benchmark["date"]), benchmark["value"],
                label="买入持有", color="#9e9e9e", linestyle="--")

    ax.axhline(result.initial_cash, color="#e0e0e0", linewidth=0.8)
    ax.set_title(title or f"净值曲线 · {result.strategy} @ {result.symbol}")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    return fig


def market_cap_figure(snapshot: pd.DataFrame, *, title: str = "", max_yi: float = 2000) -> plt.Figure:
    """全市场市值分布直方图。"""
    if snapshot is None or snapshot.empty or "market_cap" not in snapshot.columns:
        return _empty_figure()

    cap = (pd.to_numeric(snapshot["market_cap"], errors="coerce") / 1e8).dropna()
    cap = cap[cap <= max_yi]
    if cap.empty:
        return _empty_figure()

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.hist(cap, bins=60, color="#42a5f5")
    ax.set_xlabel("总市值（亿元）")
    ax.set_ylabel("股票数")
    ax.set_title(title or "全市场市值分布")
    ax.grid(alpha=0.25, axis="y")
    fig.tight_layout()
    return fig


def pe_distribution_figure(snapshot: pd.DataFrame, *, title: str = "") -> plt.Figure:
    """PE 分布直方图（只取 0~100 区间）。"""
    if snapshot is None or snapshot.empty or "pe" not in snapshot.columns:
        return _empty_figure()

    pe = pd.to_numeric(snapshot["pe"], errors="coerce").dropna()
    pe = pe[(pe > 0) & (pe <= 100)]
    if pe.empty:
        return _empty_figure()

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.hist(pe, bins=50, color="#ab47bc")
    ax.axvline(pe.median(), color="#d32f2f", linestyle="--",
               label=f"中位数 {pe.median():.1f}")
    ax.set_xlabel("PE(TTM)")
    ax.set_ylabel("股票数")
    ax.set_title(title or "全市场 PE 分布（0~100）")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.25, axis="y")
    fig.tight_layout()
    return fig
