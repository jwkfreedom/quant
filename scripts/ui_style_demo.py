"""UI 样式 demo —— 用来确认"美化之后长什么样"。

用法（在项目根目录）：
    .venv/Scripts/python.exe scripts/ui_style_demo.py              # 打开真窗口看效果
    .venv/Scripts/python.exe scripts/ui_style_demo.py --png a.png  # 渲染成图片（无显示器也能跑）

这里定义的配色 / 字号 / 圆角 / 间距就是正式界面要用的那一套（见 docs/ui_theme.md）。
"""

from __future__ import annotations

import sys

import wx

# --------------------------------------------------------------------------
# 设计规范：改这里就能整体换肤
# --------------------------------------------------------------------------
class C:
    bg = "#F5F6F8"              # 窗口底色
    card = "#FFFFFF"            # 卡片底
    border = "#E5E7EB"          # 卡片描边
    divider = "#F1F2F4"         # 内部分隔线

    text = "#111827"            # 主文字
    text_secondary = "#6B7280"  # 次要文字
    text_muted = "#9CA3AF"      # 最弱

    primary = "#2563EB"         # 主色
    primary_hover = "#1D4ED8"
    primary_light = "#EFF4FF"   # 选中/高亮底

    up = "#D93F3F"              # 涨（A股红涨绿跌）
    down = "#2E9E5B"            # 跌
    ok = "#047857"
    ok_bg = "#ECFDF5"
    warn = "#B45309"
    warn_bg = "#FFFBEB"

    table_header = "#F9FAFB"
    table_alt = "#FAFBFC"
    table_line = "#EEF0F3"


RADIUS_CARD = 10
RADIUS_BTN = 6
PAD = 16


def qpen(colour: str, width: float = 1) -> wx.Pen:
    """颜色字符串 -> 画笔。"""
    return wx.Pen(wx.Colour(colour), max(1, int(round(width))))


def qbrush(colour: str) -> wx.Brush:
    """颜色字符串 -> 画刷。"""
    return wx.Brush(wx.Colour(colour))


_MEASURE = {}


def measure_text(text: str, target: wx.Font, padding: int = 0) -> int:
    """量出文字像素宽度（用于给自绘控件定宽，避免文字被截断）。"""
    key = (text, target.GetNativeFontInfoDesc())
    if key not in _MEASURE:
        if "__dc" not in _MEASURE:
            _MEASURE["__dc"] = wx.MemoryDC(wx.Bitmap(8, 8))
        dc = _MEASURE["__dc"]
        dc.SetFont(target)
        _MEASURE[key] = dc.GetTextExtent(text).width
    return _MEASURE[key] + padding


def make_font(size: int = 10, bold: bool = False, mono: bool = False) -> wx.Font:
    """统一字体：正文微软雅黑，数字用 Consolas（等宽对齐好看）。"""
    info = wx.FontInfo(size).FaceName("Consolas" if mono else "Microsoft YaHei UI")
    if bold:
        info = info.Bold()
    return wx.Font(info)


# --------------------------------------------------------------------------
# 自绘组件
# --------------------------------------------------------------------------
def draw_card(gc, x, y, w, h, *, radius=RADIUS_CARD):
    gc.SetBrush(qbrush(C.card))
    gc.SetPen(qpen(C.border, 1))
    gc.DrawRoundedRectangle(x + 0.5, y + 0.5, w - 1, h - 1, radius)


class FlatButton(wx.Control):
    """扁平按钮：primary=True 是蓝底白字主按钮，否则白底描边次按钮。"""

    def __init__(self, parent, label="", *, primary=False, height=34, width=None):
        width = width or measure_text(label, make_font(10, bold=primary), 30)
        super().__init__(parent, size=(width, height), style=wx.BORDER_NONE)
        self._label = label
        self._primary = primary
        self._hover = False
        self._pressed = False
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_ENTER_WINDOW, self._on_enter)
        self.Bind(wx.EVT_LEAVE_WINDOW, self._on_leave)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_down)
        self.Bind(wx.EVT_LEFT_UP, self._on_up)
        self.SetCursor(wx.Cursor(wx.CURSOR_HAND))

    def _on_enter(self, _evt):
        self._hover = True
        self.Refresh()

    def _on_leave(self, _evt):
        self._hover = self._pressed = False
        self.Refresh()

    def _on_down(self, _evt):
        self._pressed = True
        self.Refresh()

    def _on_up(self, evt):
        self._pressed = False
        self.Refresh()
        if self.GetClientRect().Contains(evt.GetPosition()):
            event = wx.CommandEvent(wx.EVT_BUTTON.typeId, self.GetId())
            event.SetEventObject(self)
            wx.PostEvent(self.GetEventHandler(), event)

    def _on_paint(self, _evt):
        dc = wx.BufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        if gc is None:
            return
        self._paint(gc, *self.GetSize())

    def _paint(self, gc, width, height):
        if self._primary:
            bg = C.primary_hover if (self._hover or self._pressed) else C.primary
            fg = "#FFFFFF"
            border = bg
        else:
            bg = "#F3F4F6" if self._pressed else ("#EDF1F7" if self._hover else C.card)
            fg, border = C.text, ("#CBD5E1" if self._hover else C.border)

        gc.SetBrush(qbrush(bg))
        gc.SetPen(qpen(border, 1))
        gc.DrawRoundedRectangle(0.5, 0.5, width - 1, height - 1, RADIUS_BTN)

        gc.SetFont(make_font(10, bold=self._primary), fg)
        text_w, text_h = gc.GetTextExtent(self._label)
        gc.DrawText(self._label, (width - text_w) / 2, (height - text_h) / 2)


class Card(wx.Panel):
    """白底圆角卡片，内容放进 self.body。"""

    def __init__(self, parent, title: str = "", subtitle: str = ""):
        super().__init__(parent)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetBackgroundColour(C.bg)
        self._title = title
        self._subtitle = subtitle

        outer = wx.BoxSizer(wx.VERTICAL)
        top = PAD + (24 if title else 0) + (18 if subtitle else 0)
        outer.AddSpacer(top)
        self.body = wx.Panel(self)
        self.body.SetBackgroundColour(C.card)
        outer.Add(self.body, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, PAD)
        outer.AddSpacer(PAD)
        self.SetSizer(outer)
        self.Bind(wx.EVT_PAINT, self._on_paint)

    def _on_paint(self, _evt):
        dc = wx.BufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        if gc is None:
            return
        self._paint(gc, *self.GetSize())

    def _paint(self, gc, width, height):
        draw_card(gc, 0, 0, width, height)
        y = PAD - 4
        if self._title:
            gc.SetFont(make_font(11, bold=True), C.text)
            gc.DrawText(self._title, PAD, y)
            y += 21
        if self._subtitle:
            gc.SetFont(make_font(9), C.text_secondary)
            gc.DrawText(self._subtitle, PAD, y)


class Badge(wx.Control):
    """圆角小标签：数据状态之类。"""

    def __init__(self, parent, text: str, *, kind: str = "ok"):
        self._text = text
        self._kind = kind
        super().__init__(parent, size=(measure_text(text, make_font(9), 24), 23), style=wx.BORDER_NONE)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self._on_paint)

    def _on_paint(self, _evt):
        dc = wx.BufferedPaintDC(self)
        dc.SetBackground(qbrush(C.card))
        dc.Clear()
        gc = wx.GraphicsContext.Create(dc)
        if gc is None:
            return
        self._paint(gc, *self.GetSize())

    def _paint(self, gc, width, height):
        fg, bg = {
            "ok": (C.ok, C.ok_bg),
            "warn": (C.warn, C.warn_bg),
            "info": (C.primary, C.primary_light),
        }.get(self._kind, (C.text_secondary, "#F3F4F6"))
        gc.SetBrush(qbrush(bg))
        gc.SetPen(qpen(bg, 1))
        gc.DrawRoundedRectangle(0, 0, width, height, height / 2)
        gc.SetFont(make_font(9), fg)
        text_w, text_h = gc.GetTextExtent(self._text)
        gc.DrawText(self._text, (width - text_w) / 2, (height - text_h) / 2)


class SideNav(wx.Control):
    """左侧导航：选中项蓝竖条 + 浅蓝底，hover 灰底。"""

    ROW = 42
    GAP = 4

    def __init__(self, parent, items, *, width=190):
        height = len(items) * (self.ROW + self.GAP) + 16
        super().__init__(parent, size=(width, height), style=wx.BORDER_NONE)
        self._items = list(items)
        self._index = 0
        self._hover = -1
        self._on_select = None
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_MOTION, self._on_motion)
        self.Bind(wx.EVT_LEFT_UP, self._on_click)
        self.Bind(wx.EVT_LEAVE_WINDOW, lambda _e: self._set_hover(-1))
        self.SetCursor(wx.Cursor(wx.CURSOR_HAND))

    def _set_hover(self, index):
        if self._hover != index:
            self._hover = index
            self.Refresh()

    def _hit(self, y):
        index = (y - 8) // (self.ROW + self.GAP)
        return index if 0 <= index < len(self._items) else -1

    def _on_motion(self, evt):
        self._set_hover(self._hit(evt.GetPosition().y))

    def _on_click(self, evt):
        index = self._hit(evt.GetPosition().y)
        if index >= 0:
            self._index = index
            self.Refresh()
            if callable(self._on_select):
                self._on_select(index)

    def _on_paint(self, _evt):
        dc = wx.BufferedPaintDC(self)
        dc.SetBackground(qbrush(C.bg))
        dc.Clear()
        gc = wx.GraphicsContext.Create(dc)
        if gc is None:
            return
        pass
        self._paint(gc, *self.GetSize())

    def _paint(self, gc, width, height):
        for index, label in enumerate(self._items):
            top = 8 + index * (self.ROW + self.GAP)
            if index == self._index:
                gc.SetBrush(qbrush(C.primary_light))
                gc.SetPen(qpen(C.primary_light, 1))
                gc.DrawRoundedRectangle(8, top, width - 16, self.ROW, 8)
                gc.SetBrush(qbrush(C.primary))
                gc.SetPen(qpen(C.primary, 1))
                gc.DrawRoundedRectangle(12, top + 11, 3, self.ROW - 22, 1.5)
            elif index == self._hover:
                gc.SetBrush(qbrush("#EFF1F5"))
                gc.SetPen(qpen("#EFF1F5", 1))
                gc.DrawRoundedRectangle(8, top, width - 16, self.ROW, 8)
            gc.SetFont(make_font(10, bold=index == self._index),
                       C.primary if index == self._index else C.text_secondary)
            _, text_h = gc.GetTextExtent(label)
            gc.DrawText(label, 26, top + (self.ROW - text_h) / 2)


NAV_ITEMS = ["数据总览", "选股筛选", "个股分析", "策略回测", "数据浏览器", "设置"]


class DemoFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="quant UI 样式 demo", size=(1180, 740))
        self.SetBackgroundColour(C.bg)
        root = wx.BoxSizer(wx.HORIZONTAL)
        root.Add(SideNav(self, NAV_ITEMS), 0, wx.TOP | wx.LEFT, 10)

        right = wx.BoxSizer(wx.VERTICAL)
        head = wx.BoxSizer(wx.HORIZONTAL)
        title = wx.StaticText(self, label="选股筛选")
        title.SetFont(make_font(16, bold=True))
        title.SetForegroundColour(C.text)
        head.Add(title, 0, wx.ALIGN_CENTER_VERTICAL)
        head.AddSpacer(14)
        head.Add(Badge(self, "行情 2026-10-14"), 0, wx.ALIGN_CENTER_VERTICAL)
        head.AddSpacer(6)
        head.Add(Badge(self, "财务 2026-09-30", kind="warn"), 0, wx.ALIGN_CENTER_VERTICAL)
        head.AddStretchSpacer()
        head.Add(FlatButton(self, "筛选说明"), 0, wx.RIGHT, 8)
        head.Add(FlatButton(self, "运行选股", primary=True), 0)
        right.Add(head, 0, wx.EXPAND | wx.ALL, 16)

        row = wx.BoxSizer(wx.HORIZONTAL)
        cond = Card(self, "筛选条件", "勾选后点「运行选股」")
        inner = wx.BoxSizer(wx.VERTICAL)
        for label, value in (("剔除 ST / 退市", ""), ("上市满 N 日", "250"),
                             ("PE(TTM)", "0 ~ 20"), ("PE 历史分位", "近10年 ≤ 10%"),
                             ("ROE", "≥ 8%")):
            line = wx.BoxSizer(wx.HORIZONTAL)
            box = wx.CheckBox(cond.body, label=label)
            box.SetFont(make_font(10))
            box.SetForegroundColour(C.text)
            line.Add(box, 1, wx.ALIGN_CENTER_VERTICAL)
            if value:
                text = wx.StaticText(cond.body, label=value)
                text.SetFont(make_font(9, mono=True))
                text.SetForegroundColour(C.text_secondary)
                line.Add(text, 0, wx.ALIGN_CENTER_VERTICAL)
            inner.Add(line, 0, wx.EXPAND | wx.BOTTOM, 12)
        cond.body.SetSizer(inner)
        row.Add(cond, 1, wx.EXPAND | wx.RIGHT, 12)

        result = Card(self, "结果", "共 160 只　用时 1.8 秒")
        result.body.SetSizer(self._table(result.body))
        row.Add(result, 2, wx.EXPAND)

        right.Add(row, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 16)
        root.Add(right, 1, wx.EXPAND)
        self.SetSizer(root)

        self.CreateStatusBar()
        self.GetStatusBar().SetBackgroundColour("#ECEFF3")
        self.SetStatusText("就绪")

    def _table(self, parent):
        headers = ("代码", "名称", "收盘", "PB", "PE", "PE分位", "涨跌幅")
        rows = [("605118", "力鼎光电", "14.80", "3.70", "19.76", "8%", "+2.31%"),
                ("600105", "永鼎股份", "5.48", "2.30", "19.35", "12%", "-0.72%"),
                ("300444", "双杰电气", "7.40", "9.12", "19.04", "15%", "+1.09%"),
                ("300743", "天地数码", "14.08", "3.25", "18.85", "6%", "+4.44%"),
                ("300910", "瑞丰新材", "42.45", "3.81", "18.17", "9%", "-1.55%"),
                ("603871", "嘉友国际", "17.23", "3.62", "17.99", "11%", "+0.35%")]

        grid = wx.FlexGridSizer(rows=0, cols=len(headers), vgap=0, hgap=0)
        grid.AddGrowableCol(1, 1)

        def cell(text, *, background, head=False, right=False, mono=False, colour=None):
            holder = wx.Panel(parent, size=(-1, 34 if head else 30))
            holder.SetBackgroundColour(background)
            label = wx.StaticText(holder, label=text)
            label.SetFont(make_font(9, bold=head, mono=mono))
            label.SetForegroundColour(colour or (C.text_secondary if head else C.text))
            box = wx.BoxSizer(wx.HORIZONTAL)
            if right:
                box.AddStretchSpacer()
                box.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
            else:
                box.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10)
            holder.SetSizer(box)
            grid.Add(holder, 1, wx.EXPAND)

        for index, name in enumerate(headers):
            cell(name, background=C.table_header, head=True, right=index > 1)

        for row_index, row_values in enumerate(rows):
            background = C.card if row_index % 2 == 0 else C.table_alt
            for column, value in enumerate(row_values):
                colour = None
                if column == len(row_values) - 1:
                    colour = C.up if value.startswith("+") else C.down
                cell(value, background=background, right=column > 1,
                     mono=column != 1, colour=colour)
        return grid


# --------------------------------------------------------------------------
# 无显示器时的静态效果图（直接画到内存位图）
# --------------------------------------------------------------------------
def render_png(path: str, width: int = 1180, height: int = 740) -> None:
    bitmap = wx.Bitmap(width, height)
    dc = wx.MemoryDC(bitmap)
    dc.SetBackground(qbrush(C.bg))
    dc.Clear()

    gc = wx.GraphicsContext.Create(dc)
    if gc is None:
        raise RuntimeError("无法创建 GraphicsContext")

    def text(value, x, y, *, size=10, bold=False, mono=False, colour=C.text):
        gc.SetFont(make_font(size, bold=bold, mono=mono), colour)
        gc.DrawText(value, x, y)

    def button(x, y, label, *, primary=False, w=88, h=34):
        bg = C.primary if primary else C.card
        fg = "#FFFFFF" if primary else C.text
        border = C.primary if primary else C.border
        gc.SetBrush(qbrush(bg))
        gc.SetPen(qpen(border, 1))
        gc.DrawRoundedRectangle(x + 0.5, y + 0.5, w - 1, h - 1, RADIUS_BTN)
        gc.SetFont(make_font(10, bold=primary), fg)
        tw, th = gc.GetTextExtent(label)
        gc.DrawText(label, x + (w - tw) / 2, y + (h - th) / 2)

    def badge(x, y, label, *, kind="ok"):
        fg, bg = {"ok": (C.ok, C.ok_bg), "warn": (C.warn, C.warn_bg),
                  "info": (C.primary, C.primary_light)}[kind]
        w, h = measure_text(label, make_font(9), 24), 23
        gc.SetBrush(qbrush(bg))
        gc.SetPen(qpen(bg, 1))
        gc.DrawRoundedRectangle(x, y, w, h, h / 2)
        gc.SetFont(make_font(9), fg)
        tw, th = gc.GetTextExtent(label)
        gc.DrawText(label, x + (w - tw) / 2, y + (h - th) / 2)
        return w

    # 左导航
    nav_w, row, gap = 190, 42, 4
    for index, label in enumerate(NAV_ITEMS):
        top = 8 + index * (row + gap) + 10
        if index == 0:
            gc.SetBrush(qbrush(C.primary_light))
            gc.SetPen(qpen(C.primary_light, 1))
            gc.DrawRoundedRectangle(18, top, nav_w - 16, row, 8)
            gc.SetBrush(qbrush(C.primary))
            gc.SetPen(qpen(C.primary, 1))
            gc.DrawRoundedRectangle(22, top + 11, 3, row - 22, 1.5)
        text(label, 36, top + 12, bold=index == 0,
             colour=C.primary if index == 0 else C.text_secondary)

    # 顶栏
    left = nav_w + 26
    text("选股筛选", left, 26, size=16, bold=True)
    x = left + 100
    x += badge(x, 30, "行情 2026-10-14") + 6
    badge(x, 30, "财务 2026-09-30", kind="warn")
    button(width - 130, 22, "运行选股", primary=True, w=104)
    button(width - 130 - 96, 22, "筛选说明", w=88)

    # 左卡片
    card_y, card_h = 78, height - 78 - 40
    cond_w = 340
    draw_card(gc, left, card_y, cond_w, card_h)
    text("筛选条件", left + PAD, card_y + 14, size=11, bold=True)
    text("勾选后点「运行选股」", left + PAD, card_y + 38, size=9, colour=C.text_secondary)
    yy = card_y + 72
    for label, value in (("剔除 ST / 退市", ""), ("上市满 N 日", "250"),
                         ("PE(TTM)", "0 ~ 20"), ("PE 历史分位", "近10年 ≤ 10%"),
                         ("ROE", "≥ 8%"), ("毛利率", "≥ 20%")):
        gc.SetBrush(qbrush("#FFFFFF"))
        gc.SetPen(qpen(C.text_muted, 1.4))
        gc.DrawRoundedRectangle(left + PAD, yy + 1, 15, 15, 3)
        text(label, left + PAD + 24, yy, size=10)
        if value:
            gc.SetFont(make_font(9, mono=True), C.text_secondary)
            tw, _ = gc.GetTextExtent(value)
            text(value, left + cond_w - PAD - tw, yy)
        yy += 34

    # 右卡片
    res_x = left + cond_w + 12
    res_w = width - res_x - 16
    draw_card(gc, res_x, card_y, res_w, card_h)
    text("结果", res_x + PAD, card_y + 14, size=11, bold=True)
    text("共 160 只　用时 1.8 秒", res_x + PAD, card_y + 38, size=9, colour=C.text_secondary)

    headers = ("代码", "名称", "收盘", "PB", "PE", "PE分位", "涨跌幅")
    rows = [("605118", "力鼎光电", "14.80", "3.70", "19.76", "8%", "+2.31%"),
            ("600105", "永鼎股份", "5.48", "2.30", "19.35", "12%", "-0.72%"),
            ("300444", "双杰电气", "7.40", "9.12", "19.04", "15%", "+1.09%"),
            ("300743", "天地数码", "14.08", "3.25", "18.85", "6%", "+4.44%"),
            ("300910", "瑞丰新材", "42.45", "3.81", "18.17", "9%", "-1.55%"),
            ("603871", "嘉友国际", "17.23", "3.62", "17.99", "11%", "+0.35%"),
            ("002749", "国光股份", "8.91", "2.86", "17.62", "7%", "+0.68%"),
            ("601218", "吉鑫科技", "4.12", "1.94", "17.48", "13%", "-2.10%")]
    col_w = [78, 96, 74, 60, 60, 70, 74]
    table_x = res_x + PAD
    table_y = card_y + 66
    table_w = min(sum(col_w), res_w - 2 * PAD)

    gc.SetBrush(qbrush(C.table_header))
    gc.SetPen(qpen(C.table_header, 1))
    gc.DrawRectangle(table_x, table_y, table_w, 34)
    x = table_x
    for index, name in enumerate(headers):
        cell_w = col_w[index] if index < 1 else (table_w - col_w[0] - col_w[1]) / (len(headers) - 2)
        if index < 2:
            text(name, x + 10, table_y + 10, size=9, bold=True, colour=C.text_secondary)
        else:
            gc.SetFont(make_font(9, bold=True), C.text_secondary)
            tw, _ = gc.GetTextExtent(name)
            text(name, x + cell_w - 10 - tw, table_y + 10, size=9, bold=True, colour=C.text_secondary)
        x += col_w[index] if index < 2 else cell_w

    y = table_y + 34
    for index, row_values in enumerate(rows):
        if index % 2 == 1:
            gc.SetBrush(qbrush(C.table_alt))
            gc.SetPen(qpen(C.table_alt, 1))
            gc.DrawRectangle(table_x, y, table_w, 30)
        gc.SetBrush(qbrush(C.table_line))
        gc.SetPen(qpen(C.table_line, 1))
        gc.DrawRectangle(table_x, y + 29, table_w, 1)
        x = table_x
        for column, value in enumerate(row_values):
            cell_w = col_w[column] if column < 2 else (table_w - col_w[0] - col_w[1]) / (len(headers) - 2)
            colour = C.text
            if column == len(row_values) - 1:
                colour = C.up if value.startswith("+") else C.down
            if column < 2:
                text(value, x + 10, y + 8, size=9, mono=column == 0, colour=colour)
            else:
                gc.SetFont(make_font(9, mono=True), colour)
                tw, _ = gc.GetTextExtent(value)
                gc.DrawText(value, x + cell_w - 10 - tw, y + 8)
            x += cell_w
        y += 30

    del gc, dc
    bitmap.SaveFile(path, wx.BITMAP_TYPE_PNG)


def main() -> int:
    if "--png" in sys.argv:
        app_wx = wx.App(False)
        out = sys.argv[sys.argv.index("--png") + 1] if len(sys.argv) > sys.argv.index("--png") + 1 else "ui_mockup.png"
        render_png(out)
        print(f"saved {out}")
        del app_wx
        return 0

    app_wx = wx.App(False)
    frame = DemoFrame()
    frame.Centre()
    frame.Show()
    app_wx.MainLoop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
