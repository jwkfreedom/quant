"""P2 选股筛选：条件编辑 + 结果表 + 过滤过程 + 方案保存 + 导出。"""

from __future__ import annotations

import inspect

import wx

from quant.filter import available_filters, get_filter_class
from quant.ui import viewmodels as vm
from quant.ui.widgets import BusyRunner, DataFrameGrid, ask_save_path, error_dialog

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


class ConditionRow:
    """一个过滤器的界面行：复选框 + 参数输入框。"""

    def __init__(self, panel: wx.Panel, sizer: wx.Sizer, name: str):
        self.name = name
        cls = get_filter_class(name)
        signature = inspect.signature(cls.__init__)
        self.fields: list[tuple[str, wx.TextCtrl, object]] = []

        self.checkbox = wx.CheckBox(panel, label=name)
        self.checkbox.SetMinSize((150, -1))
        self.checkbox.SetToolTip(getattr(cls, "description", ""))
        # 注意：sizer 是垂直 BoxSizer，不能带 ALIGN_CENTER_VERTICAL（wx 会断言失败）
        sizer.Add(self.checkbox, 0, wx.ALL, 3)

        params_sizer = wx.BoxSizer(wx.HORIZONTAL)
        for param_name, param in signature.parameters.items():
            if param_name == "self":
                continue
            default = "" if param.default is inspect.Parameter.empty else param.default
            label = wx.StaticText(panel, label=f"{param_name}")
            label.SetForegroundColour(wx.Colour(120, 120, 120))
            control = wx.TextCtrl(panel, size=(70, -1), value=str(default) if default != "" else "")
            params_sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 4)
            params_sizer.Add(control, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 2)
            self.fields.append((param_name, control, default))
        sizer.Add(params_sizer, 1, wx.EXPAND)

    @property
    def enabled(self) -> bool:
        return self.checkbox.GetValue()

    def spec(self) -> str | None:
        """生成 `name:k=v` 描述；未启用返回 None。"""
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
        self.runner = BusyRunner(self)
        self.rows: list[ConditionRow] = []

        root = wx.BoxSizer(wx.HORIZONTAL)

        # ---------------- 左侧：条件 ----------------
        # 注意：StaticBoxSizer 的父窗口必须与 SetSizer 的面板一致，
        # 里面的控件也要用同一个面板做父窗口，否则 wx 会断言失败。
        left_panel = wx.Panel(self)
        left_box = wx.StaticBoxSizer(wx.VERTICAL, left_panel, "筛选条件")
        self.conditions = wx.ScrolledWindow(left_panel, style=wx.VSCROLL)
        self.conditions.SetScrollRate(0, 12)
        cond_sizer = wx.BoxSizer(wx.VERTICAL)

        registered = set(available_filters())
        for group_title, names in GROUPS:
            present = [n for n in names if n in registered]
            if not present:
                continue
            caption = wx.StaticText(self.conditions, label=f"▼ {group_title}")
            font = caption.GetFont()
            font.SetWeight(wx.FONTWEIGHT_BOLD)
            caption.SetFont(font)
            cond_sizer.Add(caption, 0, wx.ALL, 4)
            for name in present:
                self.rows.append(ConditionRow(self.conditions, cond_sizer, name))

        others = sorted(registered - {n for _g, names in GROUPS for n in names})
        if others:
            caption = wx.StaticText(self.conditions, label="▼ 其它")
            cond_sizer.Add(caption, 0, wx.ALL, 4)
            for name in others:
                self.rows.append(ConditionRow(self.conditions, cond_sizer, name))

        self.conditions.SetSizer(cond_sizer)
        left_box.Add(self.conditions, 1, wx.EXPAND | wx.ALL, 6)

        # 方案管理
        plan = wx.BoxSizer(wx.HORIZONTAL)
        self.screen_choice = wx.Choice(left_panel, choices=vm.list_screens())
        plan.Add(self.screen_choice, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 3)
        load_button = wx.Button(left_panel, label="载入")
        load_button.Bind(wx.EVT_BUTTON, lambda _evt: self.on_load())
        save_button = wx.Button(left_panel, label="保存为…")
        save_button.Bind(wx.EVT_BUTTON, lambda _evt: self.on_save())
        delete_button = wx.Button(left_panel, label="删除")
        delete_button.Bind(wx.EVT_BUTTON, lambda _evt: self.on_delete())
        for button in (load_button, save_button, delete_button):
            plan.Add(button, 0, wx.ALL, 3)
        left_box.Add(plan, 0, wx.EXPAND | wx.ALL, 4)

        # 快照日期 + 运行
        run_row = wx.BoxSizer(wx.HORIZONTAL)
        self.as_of = wx.TextCtrl(left_panel, size=(110, -1))
        self.as_of.SetHint("YYYYMMDD")
        run_row.Add(wx.StaticText(left_panel, label="快照日期"), 0,
                    wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 4)
        run_row.Add(self.as_of, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
        run_button = wx.Button(left_panel, label="运行选股")
        run_button.Bind(wx.EVT_BUTTON, lambda _evt: self.on_run())
        run_row.Add(run_button, 0, wx.ALL, 4)
        reset_button = wx.Button(left_panel, label="全部清空")
        reset_button.Bind(wx.EVT_BUTTON, lambda _evt: self.on_reset())
        run_row.Add(reset_button, 0, wx.ALL, 4)
        left_box.Add(run_row, 0, wx.EXPAND | wx.ALL, 4)

        left_panel.SetSizer(left_box)
        left_panel.SetMinSize((430, -1))
        root.Add(left_panel, 0, wx.EXPAND | wx.ALL, 6)

        # ---------------- 右侧：结果 ----------------
        right = wx.BoxSizer(wx.VERTICAL)

        head = wx.BoxSizer(wx.HORIZONTAL)
        self.summary = wx.StaticText(self, label="尚未运行")
        font = self.summary.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.summary.SetFont(font)
        head.Add(self.summary, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 6)

        copy_button = wx.Button(self, label="复制命令行")
        copy_button.Bind(wx.EVT_BUTTON, lambda _evt: self.on_copy_command())
        export_button = wx.Button(self, label="导出 CSV")
        export_button.Bind(wx.EVT_BUTTON, lambda _evt: self.on_export())
        head.Add(copy_button, 0, wx.ALL, 4)
        head.Add(export_button, 0, wx.ALL, 4)
        right.Add(head, 0, wx.EXPAND)

        self.steps = wx.StaticText(self, label="")
        self.steps.SetForegroundColour(wx.Colour(90, 90, 90))
        right.Add(self.steps, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        self.grid = DataFrameGrid(self)
        self.grid.on_row_activated = self.jump_to_stock
        self.grid.on_context_menu = self.build_context_menu
        right.Add(self.grid, 1, wx.EXPAND | wx.ALL, 6)

        hint = wx.StaticText(self, label="提示：双击某一行可以跳到「个股分析」查看图表")
        hint.SetForegroundColour(wx.Colour(120, 120, 120))
        right.Add(hint, 0, wx.ALL, 6)

        root.Add(right, 1, wx.EXPAND | wx.ALL, 6)
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
        self.Layout()

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
