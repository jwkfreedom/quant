"""P2 选股筛选：条件编辑 + 结果表 + 过滤过程 + 方案保存 + 导出。"""

from __future__ import annotations

import inspect

import wx

from quant.filter import available_filters, get_filter_class
from quant.ui import theme
from quant.ui import viewmodels as vm
from quant.ui.components import (Card, PageHeader, hint_label, make_button, style_checkbox,
                                style_input, text_label)
from quant.ui.theme import C
from quant.ui.widgets import (
    BusyRunner,
    DataFrameGrid,
    ask_save_path,
    error_dialog,
    relayout,
    show_text_dialog,
)

#: 条件分组：过滤器名 -> 分组标题
GROUPS: list[tuple[str, list[str]]] = [
    ("基础", ["exclude_st", "min_listing"]),
    ("估值", ["market_cap", "pe", "pb", "ps",
              "pe_percentile", "pb_percentile", "ps_percentile"]),
    ("财务", ["roe", "debt_ratio", "gross_margin", "growth"]),
    ("行情技术", ["break_ma", "ma_align", "ma_trend", "ma_cross",
                  "price_change", "price_range", "volume_ratio", "turnover_rate"]),
]

DEFAULT_COLUMNS = ["symbol", "name", "close_org", "market_cap", "pe", "pe_pct_10y",
                   "pb", "pb_pct_10y", "ps", "roe", "debt_ratio", "season_income_growth"]

LEFT_WIDTH = 470


class ConditionRow:
    """一个过滤器的界面行：复选框 + 参数输入框。

    右键条件名可以弹出该条件的详细说明（参数含义 + 例子）。
    """

    def __init__(self, panel: wx.Panel, sizer: wx.Sizer, name: str,
                 on_help_requested=None):
        self.name = name
        cls = get_filter_class(name)
        signature = inspect.signature(cls.__init__)
        self.fields: list[tuple[str, wx.TextCtrl, object]] = []

        line = wx.BoxSizer(wx.HORIZONTAL)

        self.checkbox = style_checkbox(wx.CheckBox(panel, label=name))
        self.checkbox.SetMinSize((150, -1))
        self.checkbox.SetToolTip(getattr(cls, "description", "") + "\n（右键查看详细说明）")
        if on_help_requested is not None:
            self.checkbox.Bind(wx.EVT_RIGHT_UP,
                               lambda _evt, n=name: on_help_requested(n))
        line.Add(self.checkbox, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)

        for param_name, param in signature.parameters.items():
            if param_name == "self":
                continue
            default = "" if param.default is inspect.Parameter.empty else param.default
            label = text_label(panel, param_name, size=theme.FONT_SMALL, colour=C.text_muted)
            control = wx.TextCtrl(panel, size=(64, -1), value=str(default) if default != "" else "")
            style_input(control)
            line.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
            line.Add(control, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
            self.fields.append((param_name, control, default))

        line.AddStretchSpacer()
        sizer.Add(line, 0, wx.EXPAND | wx.BOTTOM, 8)

    @property
    def enabled(self) -> bool:
        return self.checkbox.GetValue()

    def spec(self) -> str | None:
        """生成 name:k=v 描述；未启用返回 None。"""
        if not self.enabled:
            return None
        parts = []
        for param_name, control, default in self.fields:
            value = control.GetValue().strip()
            if value == "" or value == str(default):
                continue
            parts.append(f"{param_name}={value}")
        return self.name + (":" + ",".join(parts) if parts else "")


class ScreenerPanel(wx.Panel):
    """选股筛选页。"""

    def __init__(self, parent):
        super().__init__(parent)
        self.SetBackgroundColour(wx.Colour(C.bg))
        self.runner = BusyRunner(self)
        self.rows: list[ConditionRow] = []

        root = wx.BoxSizer(wx.VERTICAL)

        self.header = PageHeader(
            self, "选股筛选",
            subtitle="勾选条件后点「运行选股」，双击结果行可跳到个股分析",
            actions=[("筛选说明", lambda _evt: self.on_help(), False),
                     ("运行选股", lambda _evt: self.on_run(), True)],
        )
        root.Add(self.header, 0, wx.EXPAND | wx.ALL, theme.PAD)

        columns = wx.BoxSizer(wx.HORIZONTAL)

        # ---------------- 左侧：条件 ----------------
        left_card = Card(self, "筛选条件", "右键条件名可查看该条件的详细说明")
        left_card.SetMinSize((LEFT_WIDTH, -1))

        self.conditions = wx.ScrolledWindow(left_card.body, style=wx.VSCROLL)
        self.conditions.SetBackgroundColour(wx.Colour(C.card))
        self.conditions.SetScrollRate(0, 12)
        cond_sizer = wx.BoxSizer(wx.VERTICAL)

        registered = set(available_filters())
        for group_title, names in GROUPS:
            present = [n for n in names if n in registered]
            if not present:
                continue
            cond_sizer.Add(text_label(self.conditions, group_title, size=theme.FONT_SMALL,
                                      bold=True, colour=C.text_secondary),
                           0, wx.TOP | wx.BOTTOM, 6)
            for name in present:
                self.rows.append(ConditionRow(self.conditions, cond_sizer, name,
                                              on_help_requested=self.on_filter_help))

        others = sorted(registered - {n for _g, names in GROUPS for n in names})
        if others:
            cond_sizer.Add(text_label(self.conditions, "其它", size=theme.FONT_SMALL,
                                      bold=True, colour=C.text_secondary),
                           0, wx.TOP | wx.BOTTOM, 6)
            for name in others:
                self.rows.append(ConditionRow(self.conditions, cond_sizer, name,
                                              on_help_requested=self.on_filter_help))

        self.conditions.SetSizer(cond_sizer)
        left_card.add(self.conditions, 1, wx.EXPAND)

        # 方案管理
        left_card.add_spacer(10)
        plan = wx.BoxSizer(wx.HORIZONTAL)
        plan.Add(text_label(left_card.body, "方案", colour=C.text_secondary), 0,
                 wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.screen_choice = style_input(wx.Choice(left_card.body, choices=vm.list_screens()))
        plan.Add(self.screen_choice, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        plan.Add(make_button(left_card.body, "载入", lambda _evt: self.on_load()), 0,
                 wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        plan.Add(make_button(left_card.body, "保存为…", lambda _evt: self.on_save()), 0,
                 wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        plan.Add(make_button(left_card.body, "删除", lambda _evt: self.on_delete()), 0,
                 wx.ALIGN_CENTER_VERTICAL)
        left_card.add(plan, 0, wx.EXPAND)

        # 快照日期
        left_card.add_spacer(10)
        run_row = wx.BoxSizer(wx.HORIZONTAL)
        run_row.Add(text_label(left_card.body, "快照日期", colour=C.text_secondary), 0,
                    wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.as_of = style_input(wx.TextCtrl(left_card.body, size=(120, -1)))
        self.as_of.SetHint("YYYYMMDD，留空取最新")
        run_row.Add(self.as_of, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)
        run_row.Add(make_button(left_card.body, "全部清空", lambda _evt: self.on_reset()), 0,
                    wx.ALIGN_CENTER_VERTICAL)
        left_card.add(run_row, 0, wx.EXPAND)

        columns.Add(left_card, 0, wx.EXPAND | wx.RIGHT, theme.GAP)

        # ---------------- 右侧：结果 ----------------
        result_card = Card(self)
        body = result_card.body

        head = wx.BoxSizer(wx.HORIZONTAL)
        self.summary = text_label(body, "尚未运行", size=theme.FONT_CARD_TITLE,
                                  bold=True, colour=C.text)
        head.Add(self.summary, 1, wx.ALIGN_CENTER_VERTICAL)
        head.Add(make_button(body, "复制命令行", lambda _evt: self.on_copy_command()), 0,
                 wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        head.Add(make_button(body, "导出 CSV", lambda _evt: self.on_export()), 0,
                 wx.ALIGN_CENTER_VERTICAL)
        result_card.add(head, 0, wx.EXPAND)
        result_card.add_spacer(6)

        self.steps = text_label(body, "", size=theme.FONT_SMALL, colour=C.text_secondary)
        self.steps.Wrap(900)
        result_card.add(self.steps, 0, wx.EXPAND)
        result_card.add_spacer(8)

        self.grid = DataFrameGrid(body)
        self.grid.on_row_activated = self.jump_to_stock
        self.grid.on_context_menu = self.build_context_menu
        result_card.add(self.grid, 1, wx.EXPAND)
        result_card.add_spacer(6)
        result_card.add(hint_label(body, "提示：双击某一行可以跳到「个股分析」查看图表"),
                        0, wx.EXPAND)

        columns.Add(result_card, 1, wx.EXPAND)
        root.Add(columns, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, theme.PAD)

        self.SetSizer(root)
        self._result = None

    # ------------------------------------------------------------------
    def specs(self) -> list[str]:
        return [spec for row in self.rows if (spec := row.spec())]

    # ------------------------------------------------------------------
    # 结果表交互
    # ------------------------------------------------------------------
    @staticmethod
    def _code_of(row: dict) -> str:
        return str(row.get("symbol", "")).zfill(6)

    def jump_to_stock(self, row: dict):
        """双击结果行 -> 跳到个股分析页。"""
        symbol = self._code_of(row)
        frame = wx.GetTopLevelParent(self)
        if hasattr(frame, "jump_to"):
            frame.jump_to("个股分析", symbol=symbol)

    def build_context_menu(self, row: dict, menu):
        """结果表右键菜单。"""
        symbol = self._code_of(row)
        menu.separator()
        menu.add("查看个股分析", lambda r: self.jump_to_stock(r))
        menu.add(f"复制代码 {symbol}", lambda _r: self._copy_text(symbol))
        menu.add("导出选中到 CSV", lambda _r: self.on_export_selected())

    def _copy_text(self, text: str):
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(text))
            wx.TheClipboard.Close()

    def on_export_selected(self):
        selected = self.grid.selected_rows()
        if selected.empty:
            wx.MessageBox("没有选中的行", "提示", wx.OK | wx.ICON_INFORMATION, self)
            return
        path = ask_save_path(self, default_name="picks_selected.csv")
        if not path:
            return
        try:
            wx.MessageBox(f"已导出 {vm.export_frame(selected, path)}（{len(selected)} 行）",
                          "完成", wx.OK | wx.ICON_INFORMATION, self)
        except Exception as exc:
            error_dialog(self, exc)

    def on_help(self):
        """弹出筛选条件说明书（含快照日期说明）。"""
        from quant.filter.guide import build_guide

        show_text_dialog(self, "筛选条件说明", build_guide(GROUPS))

    def on_filter_help(self, name: str):
        """单个条件的说明。"""
        from quant.filter.guide import describe_filter

        show_text_dialog(self, f"条件说明 · {name}", describe_filter(name))

    def on_reset(self):
        for row in self.rows:
            row.checkbox.SetValue(False)
        self.grid.SetDataFrame(None)
        self.summary.SetLabel("尚未运行")
        self.steps.SetLabel("")

    def on_run(self):
        specs = self.specs()
        as_of_text = self.as_of.GetValue().strip()
        as_of = int(as_of_text) if as_of_text.isdigit() else None

        def work():
            return vm.run_screen(specs, as_of=as_of, columns=DEFAULT_COLUMNS)

        self.runner.run(work, self._render, on_error=lambda exc: error_dialog(self, exc),
                        busy_message="选股计算中…（首次读取历史行情可能较慢）")

    def _render(self, summary: vm.ScreenSummary):
        self._result = summary
        self.grid.SetDataFrame(summary.frame)
        self.summary.SetLabel(f"结果 {summary.count} 只　（快照 {summary.as_of}）")
        self.steps.SetLabel(summary.step_text())
        relayout(self, self.grid)

    def on_copy_command(self):
        specs = self.specs()
        command = "quant screen " + " ".join(f'--filter "{spec}"' for spec in specs)
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(command))
            wx.TheClipboard.Close()
            wx.MessageBox(f"已复制：\n{command}", "提示", wx.OK | wx.ICON_INFORMATION, self)
        else:
            wx.MessageBox(command, "命令行", wx.OK, self)

    def on_export(self):
        if self._result is None or self._result.frame.empty:
            wx.MessageBox("还没有结果可以导出", "提示", wx.OK | wx.ICON_INFORMATION, self)
            return
        path = ask_save_path(self, default_name="picks.csv")
        if not path:
            return
        try:
            saved = vm.export_frame(self._result.frame, path)
            wx.MessageBox(f"已导出 {saved}", "完成", wx.OK | wx.ICON_INFORMATION, self)
        except Exception as exc:
            error_dialog(self, exc)

    # ------------------------------------------------------------------
    def on_save(self):
        name = wx.GetTextFromUser("方案名称", "保存筛选方案", "", self)
        if not name:
            return
        try:
            path = vm.save_screen(name, self.specs())
            self.screen_choice.Set(vm.list_screens())
            wx.MessageBox(f"已保存到\n{path}", "完成", wx.OK | wx.ICON_INFORMATION, self)
        except Exception as exc:
            error_dialog(self, exc)

    def on_load(self):
        name = self.screen_choice.GetStringSelection()
        if not name:
            return
        try:
            payload = vm.load_screen(name)
        except Exception as exc:
            error_dialog(self, exc)
            return

        wanted = set(payload.get("specs", []))
        for row in self.rows:
            matched = next((spec for spec in wanted
                            if spec == row.name or spec.startswith(row.name + ":")), None)
            row.checkbox.SetValue(matched is not None)
            if matched and ":" in matched:
                for pair in matched.split(":", 1)[1].split(","):
                    if "=" not in pair:
                        continue
                    key, _, value = pair.partition("=")
                    for param_name, control, _default in row.fields:
                        if param_name == key.strip():
                            control.SetValue(value.strip())

    def on_delete(self):
        name = self.screen_choice.GetStringSelection()
        if not name:
            return
        if wx.MessageBox(f"删除方案「{name}」？", "确认", wx.YES_NO | wx.ICON_QUESTION, self) != wx.YES:
            return
        vm.delete_screen(name)
        self.screen_choice.Set(vm.list_screens())
