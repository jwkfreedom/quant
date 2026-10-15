"""P5 数据浏览器：任意表分页浏览 + 条件过滤 + 导出。"""

from __future__ import annotations

import wx

from quant.data import schema, store
from quant.ui import viewmodels as vm
from quant.ui.widgets import BusyRunner, DataFrameGrid, ask_save_path, error_dialog, relayout

PAGE_SIZES = ["100", "200", "500", "1000", "2000"]


class ExplorerPanel(wx.Panel):
    """数据库原始数据浏览与导出。"""

    def __init__(self, parent):
        super().__init__(parent)
        self.runner = BusyRunner(self)
        self.page = 1
        self.total = 0

        root = wx.BoxSizer(wx.VERTICAL)

        # ---- 查询条件 ----
        top = wx.StaticBoxSizer(wx.HORIZONTAL, self, "查询条件")
        top.Add(wx.StaticText(self, label="表"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
        self.table_choice = wx.Choice(self, choices=list(vm.EXPLORER_TABLES))
        self.table_choice.SetSelection(0)
        self.table_choice.Bind(wx.EVT_CHOICE, lambda _evt: self.on_table_changed())
        top.Add(self.table_choice, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)

        top.Add(wx.StaticText(self, label="代码"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
        self.symbol_input = wx.TextCtrl(self, size=(160, -1))
        self.symbol_input.SetHint("多个用空格分隔，如 000001 600519")
        top.Add(self.symbol_input, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)

        top.Add(wx.StaticText(self, label="日期"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
        self.date_start = wx.TextCtrl(self, size=(110, -1))
        self.date_start.SetHint("2010-01-01")
        self.date_end = wx.TextCtrl(self, size=(110, -1))
        self.date_end.SetHint("2026-12-31")
        top.Add(self.date_start, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 2)
        top.Add(wx.StaticText(self, label="~"), 0, wx.ALIGN_CENTER_VERTICAL)
        top.Add(self.date_end, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 2)

        query_button = wx.Button(self, label="查询")
        query_button.Bind(wx.EVT_BUTTON, lambda _evt: self.on_query(reset_page=True))
        top.Add(query_button, 0, wx.ALL, 6)
        root.Add(top, 0, wx.EXPAND | wx.ALL, 8)

        # ---- 附加条件 ----
        cond = wx.StaticBoxSizer(wx.HORIZONTAL, self, "附加条件（可选）")
        self.column_choice = wx.Choice(self, choices=[])
        self.op_choice = wx.Choice(self, choices=[">", ">=", "<", "<=", "=", "!=", "like"])
        self.op_choice.SetSelection(1)
        self.value_input = wx.TextCtrl(self, size=(120, -1))
        cond.Add(self.column_choice, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
        cond.Add(self.op_choice, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
        cond.Add(self.value_input, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
        clear = wx.Button(self, label="清空")
        clear.Bind(wx.EVT_BUTTON, lambda _evt: self.value_input.SetValue(""))
        cond.Add(clear, 0, wx.ALL, 4)
        root.Add(cond, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        # ---- 表格 ----
        self.grid = DataFrameGrid(self)
        root.Add(self.grid, 1, wx.EXPAND | wx.ALL, 8)

        # ---- 底部 ----
        bottom = wx.BoxSizer(wx.HORIZONTAL)
        self.prev_button = wx.Button(self, label="上一页")
        self.next_button = wx.Button(self, label="下一页")
        self.prev_button.Bind(wx.EVT_BUTTON, lambda _evt: self.on_page(-1))
        self.next_button.Bind(wx.EVT_BUTTON, lambda _evt: self.on_page(1))
        bottom.Add(self.prev_button, 0, wx.ALL, 4)
        bottom.Add(self.next_button, 0, wx.ALL, 4)

        bottom.Add(wx.StaticText(self, label="每页"), 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 12)
        self.page_size_choice = wx.Choice(self, choices=PAGE_SIZES)
        self.page_size_choice.SetSelection(1)
        self.page_size_choice.Bind(wx.EVT_CHOICE, lambda _evt: self.on_query(reset_page=True))
        bottom.Add(self.page_size_choice, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)

        self.display_names = wx.CheckBox(self, label="中文列名")
        self.display_names.Bind(wx.EVT_CHECKBOX, lambda _evt: self.render())
        bottom.Add(self.display_names, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 12)

        bottom.AddStretchSpacer()
        self.status = wx.StaticText(self, label="")
        bottom.Add(self.status, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)

        export_current = wx.Button(self, label="导出当前页")
        export_current.Bind(wx.EVT_BUTTON, lambda _evt: self.on_export(limit_page=True))
        bottom.Add(export_current, 0, wx.ALL, 4)
        export_all = wx.Button(self, label="导出全部")
        export_all.Bind(wx.EVT_BUTTON, lambda _evt: self.on_export(limit_page=False))
        bottom.Add(export_all, 0, wx.ALL, 4)
        root.Add(bottom, 0, wx.EXPAND | wx.ALL, 8)

        self.SetSizer(root)
        self.on_table_changed()

    # ------------------------------------------------------------------
    @property
    def table(self) -> str:
        return vm.EXPLORER_TABLES[self.table_choice.GetSelection()]

    @property
    def page_size(self) -> int:
        return int(PAGE_SIZES[self.page_size_choice.GetSelection()])

    def on_table_changed(self):
        """切换表时刷新列下拉框。"""
        def work():
            with store.open_db() as conn:
                return vm.table_columns(conn, self.table)

        def done(columns):
            self.column_choice.Set([f"{name}" for name, _label in columns])
            self.column_choice.SetSelection(0)
            self.on_query(reset_page=True)

        self.runner.run(work, done, on_error=lambda exc: error_dialog(self, exc))

    def _conditions(self):
        conditions = []
        if self.value_input.GetValue().strip() and self.column_choice.GetSelection() >= 0:
            column = self.column_choice.GetStringSelection()
            operator = self.op_choice.GetStringSelection()
            conditions.append((column, operator, self.value_input.GetValue().strip()))
        return conditions

    def on_query(self, reset_page: bool = False):
        if reset_page:
            self.page = 1

        symbols = self.symbol_input.GetValue().split()
        date_start = self.date_start.GetValue().strip() or None
        date_end = self.date_end.GetValue().strip() or None
        conditions = self._conditions()
        table, page, page_size = self.table, self.page, self.page_size

        def work():
            return vm.query_table(
                table, symbols=symbols, date_start=date_start, date_end=date_end,
                extra_conditions=conditions, page=page, page_size=page_size,
            )

        self.runner.run(work, self._on_data, on_error=lambda exc: error_dialog(self, exc),
                        busy_message=f"查询 {table} …")

    def _on_data(self, payload):
        df, total = payload
        self.total = total
        self.grid.SetDataFrame(df)
        self.render(update_grid=False)

    def render(self, update_grid: bool = True):
        if update_grid:
            self.grid.SetDataFrame(self.grid.frame, display_names=self.display_names.GetValue())

        pages = max(1, (self.total + self.page_size - 1) // self.page_size)
        self.status.SetLabel(f"共 {self.total:,} 行 · 第 {self.page}/{pages} 页")
        self.prev_button.Enable(self.page > 1)
        self.next_button.Enable(self.page < pages)
        relayout(self, self.grid)

    def on_page(self, delta: int):
        self.page = max(1, self.page + delta)
        self.on_query()

    def on_export(self, *, limit_page: bool):
        path = ask_save_path(self, default_name=f"{self.table}.csv")
        if not path:
            return

        symbols = self.symbol_input.GetValue().split()
        date_start = self.date_start.GetValue().strip() or None
        date_end = self.date_end.GetValue().strip() or None
        conditions = self._conditions()
        table = self.table
        display_names = self.display_names.GetValue()
        page_size = self.page_size if limit_page else 500000
        page = self.page if limit_page else 1

        def work():
            df, _total = vm.query_table(
                table, symbols=symbols, date_start=date_start, date_end=date_end,
                extra_conditions=conditions, page=page, page_size=page_size,
            )
            return vm.export_frame(df, path, display_names=display_names)

        def done(saved):
            wx.MessageBox(f"已导出到\n{saved}", "完成", wx.OK | wx.ICON_INFORMATION, self)

        self.runner.run(work, done, on_error=lambda exc: error_dialog(self, exc),
                        busy_message="导出中…")
