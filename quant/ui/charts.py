"""matplotlib 绘图函数。

只负责「数据 -> Figure」，不依赖任何 GUI 库，
因此可以直接单测（构造图形不报错）或在 GUI 里嵌入。
"""

from __future__ import annotations

import logging
import warnings

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
# --------------------------------------------------------------------------
# 指标计算（纯 pandas，不依赖 talib）
# --------------------------------------------------------------------------
def macd_series(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """返回 (DIF, DEA, MACD 柱)。"""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    return dif, dea, (dif - dea) * 2


def rsi_series(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder RSI。

    边界：只涨不跌时为 100，完全无波动时为 50（否则会出现全 NaN）。
    """
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()

    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    rsi = rsi.where(loss > 0, 100.0)
    rsi = rsi.where(~((gain <= 0) & (loss <= 0)), 50.0)
    return rsi


def price_columns(df: pd.DataFrame, adjust: str = "qfq") -> dict[str, str]:
    """返回 OHLC 四列的实际列名。

    数据库/查询层的约定是：`open/high/low/close` 为**不复权**，
    `*_qfq` 为**前复权**；而 loader 返回的 DataFrame 里另有 `*_org` 表示不复权。
    这里统一处理两套命名。
    """
    if adjust == "qfq":
        if "close_qfq" in df.columns:
            return {"open": "open_qfq", "high": "high_qfq", "low": "low_qfq", "close": "close_qfq"}
        if "close_org" in df.columns:      # loader 口径：close 本身就是前复权
            return {"open": "open", "high": "high", "low": "low", "close": "close"}
    else:
        if "close_org" in df.columns:
            return {"open": "open_org", "high": "high_org", "low": "low_org", "close": "close_org"}
        return {"open": "open", "high": "high", "low": "low", "close": "close"}

    return {"open": "open", "high": "high", "low": "low", "close": "close"}


def kline_figure(
    df: pd.DataFrame,
    *,
    title: str = "",
    adjust: str = "qfq",
    ma_periods=(5, 10, 20, 60),
    volume: bool = True,
    macd: bool = False,
    rsi: bool = False,
    max_bars: int = 500,
) -> plt.Figure:
    """K 线 + 均线 (+ 成交量 / MACD / RSI)。

    参数
    ----
    df     : 需包含 date 与 OHLC；同时支持两套列名（见 `price_columns`）
    adjust : 'qfq' 用前复权、'raw' 用不复权，蜡烛与均线保持同一口径
    macd / rsi : 是否叠加对应指标子图
    """
    if df is None or df.empty:
        return _empty_figure()

    mapping = price_columns(df, adjust)
    missing = [c for c in mapping.values() if c not in df.columns]
    if missing:
        return _empty_figure(f"缺少价格列: {missing}")

    # 只取需要的列再改名，否则会与原列（例如不复权的 close）重名
    keep = ["date"] + [mapping[k] for k in ("open", "high", "low", "close")]
    if "volume" in df.columns:
        keep.append("volume")
    data = df.loc[:, [c for c in keep if c in df.columns]].copy()
    data = data.rename(columns={mapping[k]: k for k in ("open", "high", "low", "close")})
    data = data.tail(max_bars).copy()
    data["date"] = pd.to_datetime(data["date"])
    x = np.arange(len(data))

    panels: list[tuple[str, float]] = [("price", 3.0)]
    if volume and "volume" in data.columns:
        panels.append(("volume", 1.0))
    if macd:
        panels.append(("macd", 1.0))
    if rsi:
        panels.append(("rsi", 1.0))

    # 多子图 + sharex 用 constrained_layout，比 tight_layout 更稳（后者会告警）
    fig = plt.figure(figsize=(12, 2.2 + 1.4 * len(panels)), constrained_layout=True)
    grid = fig.add_gridspec(len(panels), 1, height_ratios=[p[1] for p in panels])

    axes: dict[str, plt.Axes] = {}
    for index, (name, _ratio) in enumerate(panels):
        axes[name] = fig.add_subplot(grid[index, 0], sharex=axes["price"] if index else None)

    ax = axes["price"]
    up = data["close"] >= data["open"]
    colors = np.where(up, "#d32f2f", "#388e3c")

    ax.vlines(x, data["low"], data["high"], color=colors, linewidth=0.8)
    ax.bar(x[up], (data["close"] - data["open"])[up], bottom=data["open"][up],
           color="#d32f2f", width=0.6)
    ax.bar(x[~up], (data["open"] - data["close"])[~up], bottom=data["close"][~up],
           color="#388e3c", width=0.6)

    for period in ma_periods or ():
        if len(data) >= period:
            ax.plot(x, data["close"].rolling(period).mean(), linewidth=0.9, label=f"MA{period}")

    ax.set_title(title or "K 线")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.25)

    ax_vol = axes.get("volume")
    if ax_vol is not None:
        ax_vol.bar(x, data["volume"], color=colors, width=0.6)
        ax_vol.set_ylabel("成交量", fontsize=8)
        ax_vol.grid(alpha=0.25)

    ax_macd = axes.get("macd")
    if ax_macd is not None:
        dif, dea, hist = macd_series(data["close"])
        ax_macd.bar(x, hist, color=np.where(hist >= 0, "#d32f2f", "#388e3c"), width=0.6)
        ax_macd.plot(x, dif, color="#1565c0", linewidth=0.9, label="DIF")
        ax_macd.plot(x, dea, color="#ef6c00", linewidth=0.9, label="DEA")
        ax_macd.axhline(0, color="#bbb", linewidth=0.7)
        ax_macd.set_ylabel("MACD", fontsize=8)
        ax_macd.legend(loc="upper left", fontsize=7)
        ax_macd.grid(alpha=0.25)

    ax_rsi = axes.get("rsi")
    if ax_rsi is not None:
        values = rsi_series(data["close"])
        ax_rsi.plot(x, values, color="#6a1b9a", linewidth=0.9)
        ax_rsi.axhline(70, color="#bbb", linewidth=0.7, linestyle="--")
        ax_rsi.axhline(30, color="#bbb", linewidth=0.7, linestyle="--")
        ax_rsi.set_ylim(0, 100)
        ax_rsi.set_ylabel("RSI", fontsize=8)
        ax_rsi.grid(alpha=0.25)

    if ax_vol is not None:
        ax_vol.bar(x, data["volume"], color=colors, width=0.6)
        ax_vol.set_ylabel("成交量")
        ax_vol.grid(alpha=0.25)

    step = max(1, len(data) // 12)
    ticks = x[::step]
    labels = data["date"].dt.strftime("%Y-%m").iloc[::step]
    bottom_ax = list(axes.values())[-1]
    bottom_ax.set_xticks(ticks)
    bottom_ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)

    return fig


# --------------------------------------------------------------------------
# 周期重采样
# --------------------------------------------------------------------------
def resample_ohlc(df: pd.DataFrame, freq: str = "D") -> pd.DataFrame:
    """把日线重采样成周线 / 月线。

    参数 freq 取 'D' / 'W'（周五收盘）/ 'M'。
    """
    if df is None or df.empty or freq == "D":
        return df

    data = df.copy()
    data["date"] = pd.to_datetime(data["date"])
    data = data.sort_values("date").set_index("date")

    rule = {"W": "W-FRI", "M": "M"}.get(freq)
    if rule is None:
        return df

    columns = {
        "open": "first", "high": "max", "low": "min", "close": "last",
        "open_qfq": "first", "high_qfq": "max", "low_qfq": "min", "close_qfq": "last",
        "open_org": "first", "high_org": "max", "low_org": "min", "close_org": "last",
        "volume": "sum", "turnover": "sum",
    }
    aggregation = {k: v for k, v in columns.items() if k in data.columns}

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")   # pandas 对 'M' 的弃用提示
        out = data.resample(rule).agg(aggregation).dropna(subset=["close"])

    return out.reset_index()


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


def sweep_figure(
    table: pd.DataFrame,
    *,
    x_column: str,
    title: str = "",
    metrics=("return_pct", "max_drawdown_pct", "sharpe"),
) -> plt.Figure:
    """参数扫描结果：x 轴为参数值，纵轴为各项指标。"""
    if table is None or table.empty or x_column not in table.columns:
        return _empty_figure("没有扫描结果")

    available = [m for m in metrics if m in table.columns]
    if not available:
        return _empty_figure("没有可比指标")

    labels = {"return_pct": "总收益率%", "max_drawdown_pct": "最大回撤%",
              "sharpe": "夏普", "trades": "交易次数", "annual_return": "年化%"}
    colors = {"return_pct": "#1565c0", "max_drawdown_pct": "#c62828",
              "sharpe": "#2e7d32", "trades": "#6a1b9a", "annual_return": "#ef6c00"}

    fig, axes = plt.subplots(len(available), 1, figsize=(11, 2.2 * len(available)),
                             sharex=True, squeeze=False)
    for ax, metric in zip(axes[:, 0], available):
        ax.plot(table[x_column], table[metric], marker="o", markersize=4,
                color=colors.get(metric, "#555"), label=labels.get(metric, metric))
        best_index = table[metric].idxmax() if metric != "max_drawdown_pct" else table[metric].idxmin()
        if pd.notna(best_index):
            best_x = table.loc[best_index, x_column]
            best_y = table.loc[best_index, metric]
            ax.axvline(best_x, color="#bbb", linestyle="--", linewidth=0.8)
            ax.annotate(f"最优 {best_x:g}", (best_x, best_y), fontsize=8,
                        textcoords="offset points", xytext=(4, 6))
        ax.set_ylabel(labels.get(metric, metric), fontsize=8)
        ax.grid(alpha=0.25)

    axes[-1, 0].set_xlabel(x_column)
    fig.suptitle(title or f"参数扫描：{x_column}", fontsize=11)
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
