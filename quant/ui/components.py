"""可复用的自绘控件：卡片、扁平按钮、状态标签、侧边导航。

所有视觉参数来自 quant.ui.theme（色板/字号/圆角/间距）。
自绘控件的绘制逻辑都拆成 _paint(gc, width, height)，可以脱离真实窗口
用 MemoryDC 直接渲染，便于无头验证。
"""

from __future__ import annotations

import logging

import wx

from quant.ui import theme
from quant.ui.theme import C, PAD, RADIUS_BTN, RADIUS_CARD

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# 基础辅助
# --------------------------------------------------------------------------
def make_font(size: int = theme.FONT_BODY, *, bold: bool = False, mono: bool = False) -> wx.Font:
    """统一字体：正文微软雅黑，数字/代码等宽。"""
    family = theme.FONT_MONO if mono else theme.FONT_FAMILY
    info = wx.FontInfo(size).FaceName(family)
    if bold:
        info = info.Bold()
    font = wx.Font(info)
    if not font.IsOk() and not mono:      # 系统没有微软雅黑时退回默认
        info = wx.FontInfo(size).FaceName(theme.FONT_FAMILY_FALLBACK)
        if bold:
            info = info.Bold()
        font = wx.Font(info)
    return font


def qpen(colour: str, width: int = 1) -> wx.Pen:
    """颜色字符串 -> 画笔。"""
    return wx.Pen(wx.Colour(colour), max(1, int(width)))


def qbrush(colour: str) -> wx.Brush:
    """颜色字符串 -> 画刷。"""
    return wx.Brush(wx.Colour(colour))


_MEASURE_CACHE: dict[str, object] = {}


def measure_text(text: str, target: wx.Font, padding: int = 0) -> int:
    """量出文字像素宽度（自绘控件定宽用，避免文字被截断）。"""
    key = (text, target.GetNativeFontInfoDesc())
    cached = _MEASURE_CACHE.get(key)
    if cached is None:
        dc = _MEASURE_CACHE.get("__dc")
        if dc is None:
            dc = wx.MemoryDC(wx.Bitmap(8, 8))
            _MEASURE_CACHE["__dc"] = dc
        dc.SetFont(target)
        cached = dc.GetTextExtent(text).width
        _MEASURE_CACHE[key] = cached
    return int(cached) + padding


def text_label(parent, value: str, *, size: int = theme.FONT_BODY, bold: bool = False,
               mono: bool = False, colour: str | None = None,
               background: str | None = None) -> wx.StaticText:
    """统一风格的 StaticText。"""
    label = wx.StaticText(parent, label=str(value))
    label.SetFont(make_font(size, bold=bold, mono=mono))
    label.SetForegroundColour(wx.Colour(colour or C.text))
    if background:
        label.SetBackgroundColour(wx.Colour(background))
    return label


def hint_label(parent, value: str) -> wx.StaticText:
    """灰色小字说明。"""
    return text_label(parent, value, size=theme.FONT_SMALL, colour=C.text_secondary)


def style_input(control: wx.Window, *, width: int | None = None) -> wx.Window:
    """给 TextCtrl / Choice 之类套上统一字号与底色。"""
    control.SetFont(make_font(theme.FONT_BODY))
    try:
        control.SetBackgroundColour(wx.Colour(C.card))
        control.SetForegroundColour(wx.Colour(C.text))
    except Exception:  # pragma: no cover - 少数控件不支持
        logger.debug("设置底色失败", exc_info=True)
    if width:
        control.SetMinSize((width, -1))
    return control


def style_checkbox(box: wx.CheckBox) -> wx.CheckBox:
    box.SetFont(make_font(theme.FONT_BODY))
    box.SetForegroundColour(wx.Colour(C.text))
    return box


# --------------------------------------------------------------------------
# 卡片
# --------------------------------------------------------------------------
class Card(wx.Panel):
    """白底圆角卡片。内容加到 self.body 里。

    用法：
        card = Card(parent, "筛选条件", "勾选后点运行")
        wx.StaticText(card.body, label="...")
        card.add(widget, 0, wx.EXPAND)
    """

    def __init__(self, parent, title: str = "", subtitle: str = "", *, padding: int = PAD):
        super().__init__(parent)
        self._title = title
        self._subtitle = subtitle
        self._padding = padding
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetBackgroundColour(wx.Colour(C.bg))

        self.body = wx.Panel(self)
        self.body.SetBackgroundColour(wx.Colour(C.card))
        self.body_sizer = wx.BoxSizer(wx.VERTICAL)
        self.body.SetSizer(self.body_sizer)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.AddSpacer(self._top_space())
        outer.Add(self.body, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, padding)
        outer.AddSpacer(padding)
        self.SetSizer(outer)

        self.Bind(wx.EVT_PAINT, self._on_paint)

    # ------------------------------------------------------------------
    def _top_space(self) -> int:
        space = self._padding
        if self._title:
            space += 24
        if self._subtitle:
            space += 17
        return space

    def add(self, item, proportion: int = 0, flag: int = wx.EXPAND, border: int = 0):
        """往卡片内容区加控件或子 sizer。"""
        self.body_sizer.Add(item, proportion, flag, border)
        return item

    def add_spacer(self, size: int = theme.GAP):
        self.body_sizer.AddSpacer(size)

    def set_title(self, text: str):
        self._title = text
        self.Refresh()

    def set_subtitle(self, text: str):
        self._subtitle = text
        self.Refresh()

    # ------------------------------------------------------------------
    def _on_paint(self, _evt):
        dc = wx.BufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        if gc is None:
            return
        self._paint(gc, *self.GetSize())

    def _paint(self, gc, width: int, height: int):
        # 背景先铺页面底色，再画卡片
        gc.SetBrush(qbrush(C.bg))
        gc.SetPen(wx.Pen(wx.Colour(C.bg), 1, wx.PENSTYLE_TRANSPARENT))
        gc.DrawRectangle(0, 0, width, height)

        gc.SetBrush(qbrush(C.card))
        gc.SetPen(qpen(C.border, 1))
        gc.DrawRoundedRectangle(0.5, 0.5, width - 1, height - 1, RADIUS_CARD)

        y = self._padding - 4
        if self._title:
            gc.SetFont(make_font(theme.FONT_CARD_TITLE, bold=True), wx.Colour(C.text))
            gc.DrawText(self._title, self._padding, y)
            y += 21
        if self._subtitle:
            gc.SetFont(make_font(theme.FONT_SMALL), wx.Colour(C.text_secondary))
            gc.DrawText(self._subtitle, self._padding, y)


# --------------------------------------------------------------------------
# 按钮
# --------------------------------------------------------------------------
class FlatButton(wx.Control):
    """扁平按钮：primary=True 是蓝底白字主按钮，否则白底描边次按钮。"""

    def __init__(self, parent, label: str = "", *, primary: bool = False,
                 height: int = 34, width: int | None = None):
        self._primary = primary
        self._label = label
        self._hover = False
        self._pressed = False
        width = width or measure_text(label, make_font(theme.FONT_BODY, bold=primary), 30)
        super().__init__(parent, size=(width, height), style=wx.BORDER_NONE)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_ENTER_WINDOW, self._on_enter)
        self.Bind(wx.EVT_LEAVE_WINDOW, self._on_leave)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_down)
        self.Bind(wx.EVT_LEFT_UP, self._on_up)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda _evt: None)

    # 与 wx.Button 的常用 API 保持一致
    def SetLabel(self, label: str):  # noqa: N802 - 对齐 wx 命名
        self._label = label
        self.SetMinSize((measure_text(label, make_font(theme.FONT_BODY, bold=self._primary), 30),
                         self.GetSize().height))
        self.Refresh()

    def GetLabel(self) -> str:  # noqa: N802
        return self._label

    # ------------------------------------------------------------------
    def _on_enter(self, _evt):
        self._hover = True
        self.Refresh()

    def _on_leave(self, _evt):
        self._hover = False
        self._pressed = False
        self.Refresh()

    def _on_down(self, _evt):
        if not self.IsEnabled():
            return
        self._pressed = True
        self.Refresh()

    def _on_up(self, evt):
        if not self.IsEnabled():
            return
        self._pressed = False
        self.Refresh()
        if self.GetClientRect().Contains(evt.GetPosition()):
            event = wx.CommandEvent(wx.wxEVT_BUTTON, self.GetId())
            event.SetEventObject(self)
            wx.PostEvent(self.GetEventHandler(), event)

    def _on_paint(self, _evt):
        dc = wx.BufferedPaintDC(self)
        dc.SetBackground(qbrush(C.card))
        dc.Clear()
        gc = wx.GraphicsContext.Create(dc)
        if gc is None:
            return
        self._paint(gc, *self.GetSize())

    def _paint(self, gc, width: int, height: int):
        enabled = self.IsEnabled()
        if self._primary:
            if not enabled:
                bg = "#93B4F5"
            else:
                bg = C.primary_hover if (self._hover or self._pressed) else C.primary
            fg, border = "#FFFFFF", bg
        else:
            if not enabled:
                bg, fg, border = "#F3F4F6", C.text_muted, C.border
            else:
                bg = "#F3F4F6" if self._pressed else (C.primary_light if self._hover else C.card)
                fg = C.text
                border = C.border if not self._hover else "#CBD5E1"

        gc.SetBrush(qbrush(bg))
        gc.SetPen(qpen(border, 1))
        gc.DrawRoundedRectangle(0.5, 0.5, width - 1, height - 1, RADIUS_BTN)

        gc.SetFont(make_font(theme.FONT_BODY, bold=self._primary), wx.Colour(fg))
        text_w, text_h = gc.GetTextExtent(self._label)
        gc.DrawText(self._label, (width - text_w) / 2, (height - text_h) / 2)


class Badge(wx.Control):
    """圆角小标签，例如「行情 2026-10-14」「需更新」。"""

    KINDS = {
        "ok": (C.ok, C.ok_bg),
        "warn": (C.warn, C.warn_bg),
        "info": (C.primary, C.primary_light),
        "muted": (C.text_secondary, "#F3F4F6"),
    }

    def __init__(self, parent, text: str = "", *, kind: str = "ok"):
        self._text = text
        self._kind = kind
        super().__init__(parent, size=(measure_text(text, make_font(theme.FONT_SMALL), 24), 23),
                         style=wx.BORDER_NONE)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda _evt: None)

    def SetText(self, text: str, kind: str | None = None):  # noqa: N802
        self._text = text
        if kind:
            self._kind = kind
        self.SetMinSize((measure_text(text, make_font(theme.FONT_SMALL), 24), 23))
        self.Refresh()

    def GetLabel(self) -> str:  # noqa: N802
        return self._text

    def _on_paint(self, _evt):
        dc = wx.BufferedPaintDC(self)
        dc.SetBackground(qbrush(C.bg))
        dc.Clear()
        gc = wx.GraphicsContext.Create(dc)
        if gc is None:
            return
        self._paint(gc, *self.GetSize())

    def _paint(self, gc, width: int, height: int):
        fg, bg = self.KINDS.get(self._kind, self.KINDS["muted"])
        gc.SetBrush(qbrush(bg))
        gc.SetPen(wx.Pen(wx.Colour(bg), 1, wx.PENSTYLE_TRANSPARENT))
        gc.DrawRoundedRectangle(0, 0, width, height, height / 2)
        gc.SetFont(make_font(theme.FONT_SMALL), wx.Colour(fg))
        text_w, text_h = gc.GetTextExtent(self._text)
        gc.DrawText(self._text, (width - text_w) / 2, (height - text_h) / 2)


# --------------------------------------------------------------------------
# 侧边导航
# --------------------------------------------------------------------------
class SideNav(wx.Control):
    """左侧导航：选中项浅蓝底 + 左侧蓝色竖条，hover 灰底。"""

    ROW = 42
    GAP = 4
    MARGIN_X = 8

    def __init__(self, parent, items, *, width: int = 190, on_select=None):
        self._items = list(items)
        self._index = 0
        self._hover = -1
        self.on_select = on_select
        height = len(self._items) * (self.ROW + self.GAP) + 16
        super().__init__(parent, size=(width, height), style=wx.BORDER_NONE)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_MOTION, self._on_motion)
        self.Bind(wx.EVT_LEFT_UP, self._on_click)
        self.Bind(wx.EVT_LEAVE_WINDOW, lambda _evt: self._set_hover(-1))
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda _evt: None)

    # ------------------------------------------------------------------
    def SetSelection(self, index: int):  # noqa: N802
        if 0 <= index < len(self._items) and index != self._index:
            self._index = index
            self.Refresh()

    def GetSelection(self) -> int:  # noqa: N802
        return self._index

    def set_items(self, items):
        self._items = list(items)
        self.SetMinSize((self.GetSize().width, len(self._items) * (self.ROW + self.GAP) + 16))
        self.Refresh()

    # ------------------------------------------------------------------
    def _set_hover(self, index: int):
        if self._hover != index:
            self._hover = index
            self.Refresh()

    def _hit(self, y: int) -> int:
        index = (y - 8) // (self.ROW + self.GAP)
        return index if 0 <= index < len(self._items) else -1

    def _on_motion(self, evt):
        self._set_hover(self._hit(evt.GetPosition().y))

    def _on_click(self, evt):
        index = self._hit(evt.GetPosition().y)
        if index < 0:
            return
        self._index = index
        self.Refresh()
        if callable(self.on_select):
            self.on_select(index, self._items[index])

    def _on_paint(self, _evt):
        dc = wx.BufferedPaintDC(self)
        dc.SetBackground(qbrush(C.bg))
        dc.Clear()
        gc = wx.GraphicsContext.Create(dc)
        if gc is None:
            return
        self._paint(gc, *self.GetSize())

    def _paint(self, gc, width: int, height: int):
        for index, label in enumerate(self._items):
            top = self.MARGIN_X + index * (self.ROW + self.GAP)
            if index == self._index:
                gc.SetBrush(qbrush(C.primary_light))
                gc.SetPen(wx.Pen(wx.Colour(C.primary_light), 1, wx.PENSTYLE_TRANSPARENT))
                gc.DrawRoundedRectangle(self.MARGIN_X, top, width - 2 * self.MARGIN_X,
                                        self.ROW, 8)
                gc.SetBrush(qbrush(C.primary))
                gc.SetPen(wx.Pen(wx.Colour(C.primary), 1, wx.PENSTYLE_TRANSPARENT))
                gc.DrawRoundedRectangle(self.MARGIN_X + 4, top + 11, 3, self.ROW - 22, 1)
            elif index == self._hover:
                gc.SetBrush(qbrush(C.nav_hover))
                gc.SetPen(wx.Pen(wx.Colour(C.nav_hover), 1, wx.PENSTYLE_TRANSPARENT))
                gc.DrawRoundedRectangle(self.MARGIN_X, top, width - 2 * self.MARGIN_X,
                                        self.ROW, 8)

            selected = index == self._index
            gc.SetFont(make_font(theme.FONT_BODY, bold=selected),
                       wx.Colour(C.primary if selected else C.text_secondary))
            _, text_h = gc.GetTextExtent(label)
            gc.DrawText(label, self.MARGIN_X + 18, top + (self.ROW - text_h) / 2)


# --------------------------------------------------------------------------
# 页面标题条
# --------------------------------------------------------------------------
class PageHeader(wx.Panel):
    """页面顶部：大标题 + 状态标签 + 右侧按钮。"""

    def __init__(self, parent, title: str, *, subtitle: str = "",
                 badges: list[tuple[str, str]] | None = None,
                 actions: list[tuple[str, object, bool]] | None = None):
        super().__init__(parent)
        self.SetBackgroundColour(wx.Colour(C.bg))

        outer = wx.BoxSizer(wx.VERTICAL)
        row = wx.BoxSizer(wx.HORIZONTAL)

        self.title = text_label(self, title, size=theme.FONT_PAGE_TITLE, bold=True, colour=C.text)
        row.Add(self.title, 0, wx.ALIGN_CENTER_VERTICAL)
        row.AddSpacer(14)

        self.badges: list[Badge] = []
        for index, (text, kind) in enumerate(badges or []):
            badge = Badge(self, text, kind=kind)
            self.badges.append(badge)
            row.Add(badge, 0, wx.ALIGN_CENTER_VERTICAL)
            if index < len(badges or []) - 1:
                row.AddSpacer(6)

        row.AddStretchSpacer()

        self.buttons: dict[str, FlatButton] = {}
        for index, (label, callback, primary) in enumerate(actions or []):
            button = FlatButton(self, label, primary=primary)
            if callback is not None:
                button.Bind(wx.EVT_BUTTON, lambda evt, cb=callback: cb(evt))
            self.buttons[label] = button
            row.Add(button, 0, wx.ALIGN_CENTER_VERTICAL)
            if index < len(actions or []) - 1:
                row.AddSpacer(8)

        outer.Add(row, 0, wx.EXPAND)
        if subtitle:
            self.subtitle = hint_label(self, subtitle)
            outer.Add(self.subtitle, 0, wx.TOP, 2)
        else:
            self.subtitle = None
        self.SetSizer(outer)

    def set_subtitle(self, text: str):
        if self.subtitle is not None:
            self.subtitle.SetLabel(text)
            self.Layout()


# --------------------------------------------------------------------------
# 页签
# --------------------------------------------------------------------------
def make_notebook(parent):
    """扁平页签。优先用 agw.FlatNotebook，不可用则退回 wx.Notebook。"""
    try:
        import wx.lib.agw.flatnotebook as fnb
    except Exception:  # pragma: no cover - 极少数环境缺 agw
        logger.debug("FlatNotebook 不可用，回退 wx.Notebook", exc_info=True)
        return wx.Notebook(parent)

    style = 0
    for name in ("FNB_NO_X_BUTTON", "FNB_NO_NAV_BUTTONS", "FNB_NODRAG",
                 "FNB_NO_TAB_FOCUS", "FNB_TABS_BORDER_SIMPLE"):
        style |= getattr(fnb, name, 0)
    try:
        book = fnb.FlatNotebook(parent, agwStyle=style)
        book.SetTabAreaColour(wx.Colour(C.card))
        book.SetActiveTabColour(wx.Colour(C.card))
        book.SetActiveTabTextColour(wx.Colour(C.primary))
        book.SetNonActiveTabTextColour(wx.Colour(C.text_secondary))
        if hasattr(book, "SetFont"):        # 老版本没有 SetTabFont
            book.SetFont(make_font(theme.FONT_BODY))
    except Exception:  # pragma: no cover
        logger.debug("FlatNotebook 创建失败，回退 wx.Notebook", exc_info=True)
        return wx.Notebook(parent)
    book.SetBackgroundColour(wx.Colour(C.card))
    return book


def make_button(parent, label: str, callback=None, *, primary: bool = False) -> FlatButton:
    """便捷函数：造一个扁平按钮并绑定事件。"""
    button = FlatButton(parent, label, primary=primary)
    if callback is not None:
        button.Bind(wx.EVT_BUTTON, lambda evt, cb=callback: cb(evt))
    return button
