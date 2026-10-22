"""UI 视觉规范：配色、字体、间距、matplotlib 主题。

这个模块不导入 wx，因此绘图代码（quant.ui.charts）也能安全地引用配色。
wx 相关的辅助（字体对象、画笔/画刷、文字度量）在 quant.ui.components 里。

规范说明见 docs/ui_theme.md，效果稿见 docs/ui_mockup.html。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class C:
    """配色板。改这里就能整体换肤。"""

    # 底色与容器
    bg = "#F5F6F8"              # 窗口背景
    card = "#FFFFFF"            # 卡片底
    border = "#E5E7EB"          # 卡片描边 / 输入框描边
    divider = "#F1F2F4"         # 内部分隔线

    # 文字
    text = "#111827"            # 主文字
    text_secondary = "#6B7280"  # 次要文字
    text_muted = "#9CA3AF"      # 最弱（占位、单位）

    # 主色
    primary = "#2563EB"
    primary_hover = "#1D4ED8"
    primary_light = "#EFF4FF"   # 选中 / 高亮底

    # 语义色（A 股习惯：红涨绿跌）
    up = "#D93F3F"
    down = "#2E9E5B"
    ok = "#047857"
    ok_bg = "#ECFDF5"
    warn = "#B45309"
    warn_bg = "#FFFBEB"
    danger = "#B91C1C"

    # 表格
    table_header = "#F9FAFB"
    table_alt = "#FAFBFC"
    table_line = "#EEF0F3"
    table_selected = "#EFF4FF"

    # 其它
    nav_hover = "#EFF1F5"
    status_bg = "#ECEFF3"


#: 圆角与间距（8px 基准）
RADIUS_CARD = 10
RADIUS_BTN = 6
PAD = 16
GAP = 12

#: 字号（pt）
FONT_PAGE_TITLE = 16
FONT_CARD_TITLE = 11
FONT_BODY = 10
FONT_SMALL = 9

#: 字体族
FONT_FAMILY = "Microsoft YaHei UI"
FONT_FAMILY_FALLBACK = "Microsoft YaHei"
FONT_MONO = "Consolas"

#: 图表配色（与界面同源）
CHART_COLORS = ("#2563EB", "#D93F3F", "#2E9E5B", "#B45309", "#7C3AED", "#0891B2")


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    """把 #RRGGBB 转成 (r, g, b)。"""
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def sign_colour(value) -> str | None:
    """按正负返回涨/跌颜色（用于表格与指标卡）。"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number > 0:
        return C.up
    if number < 0:
        return C.down
    return C.text_secondary


_APPLIED = False


def apply_matplotlib_theme() -> None:
    """把 matplotlib 的默认样式换成与界面一致的浅色扁平风。

    重复调用无副作用（只生效一次）。
    """
    global _APPLIED
    if _APPLIED:
        return
    try:
        import matplotlib
        from cycler import cycler
        import matplotlib.pyplot as plt
    except Exception:  # pragma: no cover - matplotlib 缺失
        logger.debug("matplotlib 不可用，跳过图表主题", exc_info=True)
        return

    family = None
    try:
        from matplotlib import font_manager

        names = {f.name.lower() for f in font_manager.fontManager.ttflist}
        for candidate in (FONT_FAMILY, FONT_FAMILY_FALLBACK, "SimHei",
                          "Noto Sans CJK SC", "Arial Unicode MS"):
            if candidate.lower() in names:
                family = candidate
                break
    except Exception:  # pragma: no cover
        logger.debug("字体探测失败", exc_info=True)

    rc = {
        "axes.unicode_minus": False,
        "figure.facecolor": C.card,
        "axes.facecolor": C.card,
        "savefig.facecolor": C.card,
        "figure.edgecolor": C.card,
        "axes.edgecolor": C.border,
        "axes.labelcolor": C.text_secondary,
        "axes.titlecolor": C.text,
        "axes.titlesize": FONT_CARD_TITLE,
        "axes.labelsize": FONT_SMALL,
        "axes.titleweight": "bold",
        "axes.linewidth": 0.8,
        "axes.grid": True,
        "axes.axisbelow": True,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "grid.color": C.table_line,
        "grid.linewidth": 0.8,
        "grid.linestyle": "-",
        "xtick.color": C.text_secondary,
        "ytick.color": C.text_secondary,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "xtick.major.size": 3,
        "ytick.major.size": 3,
        "legend.frameon": False,
        "legend.fontsize": 8,
        "lines.linewidth": 1.4,
        "axes.prop_cycle": cycler(color=list(CHART_COLORS)),
    }
    if family:
        rc["font.sans-serif"] = [family]

    try:
        plt.rcParams.update(rc)
        matplotlib.rcParams.update(rc)
    except Exception:  # pragma: no cover
        logger.debug("应用图表主题失败", exc_info=True)
        return
    _APPLIED = True


def report() -> dict[str, str]:
    """当前配色（给设置页/文档用）。"""
    return {name: value for name, value in vars(C).items() if not name.startswith("_")}
