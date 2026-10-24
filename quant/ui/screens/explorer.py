"""P5 数据浏览器：任意表分页浏览 + 条件过滤 + 导出。"""

from __future__ import annotations

import pandas as pd
import wx

from quant.ui import theme
from quant.ui import viewmodels as vm
from quant.ui.components import (Card, PageHeader, hint_label, make_button, style_checkbox,
                                style_input, text_label)
from quant.ui.theme import C
from quant.ui.widgets import (BusyRunner, DataFrameGrid, ask_save_path, error_dialog,
                             relayout)

PAGE_SIZES = ["100", "200", "500", "1000", "2000"]


class ExplorerPanel(wx.Panel):
    """数据库原始数据浏览与导出。"""

    def __init__(self, parent):
        super().__init__(parent)
        self.SetBackgroundColour(wx.Colour(C.bg))
        self.runner = BusyRunner(self)
        self.page = 1
        self.total = 0
        self._tables: list[str] = []
        self._raw_frame = pd.DataFrame()

        root = wx.BoxSizer(wx.VERTICAL)

        self.header = PageHeader(
            self, "数据浏览器",
            subtitle="浏览任意数据表、按条件过滤并导出",
            actions=[("查询", lambda _evt: self.on_query(reset_page=True), True)],
        )
        root.Add(self.header, 0, wx.EXPAND | wx.ALL, theme.PAD)

        # ---- 查询条件 ----
        query_card = Card(self, "查询条件")
        body = query_card.body

        line1 = wx.BoxSizer(wx.HORIZONTAL)
        line1.Add(text_label(body, "数据库", colour=C.text_secondary), 0,
                  wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.database_choice = style_input(wx.Choice(
            body, choices=[label for _key, label in vm.EXPLORER_DATABASES]))
        self.database_choice.SetSelection(0)
        self.database_choice.Bind(wx.EVT_CHOICE,
                                  lambda _evt: self.on_database_changed())
        line1.Add(self.database_choice, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 16)

        line1.Add(text_label(body, "数据表", colour=C.text_secondary), 0,
                  wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.table_choice = style_input(wx.Choice(body, choices=[]))
        self.table_choice.Bind(wx.EVT_CHOICE, lambda _evt: self.on_table_changed())
        line1.Add(self.table_choice, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 20)

        line1.Add(text_label(body, "代码", colour=C.text_secondary), 0,
                  wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.symbol_input = style_input(wx.TextCtrl(body, size=(200, -1)),
                                        width=200)
        self.symbol_input.SetHint("多个用空格分隔，如 000001 600519")
        line1.Add(self.symbol_input, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 20)

        line1.Add(text_label(body, "日期", colour=C.text_secondary), 0,
                  wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.date_start = style_input(wx.TextCtrl(body, size=(110, -1)))
        self.date_start.SetHint("2010-01-01")
        self.date_end = style_input(wx.TextCtrl(body, size=(110, -1)))
        self.date_end.SetHint("2026-12-31")
        line1.Add(self.date_start, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        line1.Add(text_label(body, "~", colour=C.text_muted), 0, wx.ALIGN_CENTER_VERTICAL)
        line1.Add(self.date_end, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 6)
        line1.AddStretchSpacer()
        query_card.add(line1, 0, wx.EXPAND)

        line2 = wx.BoxSizer(wx.HORIZONTAL)
        line2.Add(text_label(body, "附加条件", colour=C.text_secondary), 0,
                  wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.column_choice = style_input(wx.Choice(body, choices=[]))
        self.op_choice = style_input(wx.Choice(body, choices=[">", ">=", "<", "<=", "=", "!=", "like"]))
        self.op_choice.SetSelection(1)
        self.value_input = style_input(wx.TextCtrl(body, size=(140, -1)), width=140)
        self.value_input.SetHint("数值或文本")
        line2.Add(self.column_choice, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        line2.Add(self.op_choice, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        line2.Add(self.value_input, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)
        line2.Add(make_button(body, "清空", lambda _evt: self.value_input.SetValue("")), 0,
                  wx.ALIGN_CENTER_VERTICAL)
        line2.AddStretchSpacer()
        query_card.add_spacer(10)
        query_card.add(line2, 0, wx.EXPAND)

        root.Add(query_card, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.PAD)

        # ---- 结果 ----
        result_card = Card(self, "结果")
        self.grid = DataFrameGrid(result_card.body)
        result_card.add(self.grid, 1, wx.EXPAND)

        bottom = wx.BoxSizer(wx.HORIZONTAL)
        self.prev_button = make_button(result_card.body, "上一页", lambda _evt: self.on_page(-1))
        self.next_button = make_button(result_card.body, "下一页", lambda _evt: self.on_page(1))
        bottom.Add(self.prev_button, 0, wx.RIGHT, 8)
        bottom.Add(self.next_button, 0, wx.RIGHT, 16)

        bottom.Add(text_label(result_card.body, "每页", colour=C.text_secondary), 0,
                   wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.page_size_choice = style_input(wx.Choice(result_card.body, choices=PAGE_SIZES))
        self.page_size_choice.SetSelection(1)
        self.page_size_choice.Bind(wx.EVT_CHOICE, lambda _evt: self.on_query(reset_page=True))
        bottom.Add(self.page_size_choice, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 16)

        self.display_names = style_checkbox(wx.CheckBox(result_card.body, label="中文列名"))
        self.display_names.Bind(wx.EVT_CHECKBOX, lambda _evt: self.render())
        bottom.Add(self.display_names, 0, wx.ALIGN_CENTER_VERTICAL)

        bottom.AddStretchSpacer()
        self.status = text_label(result_card.body, "", size=theme.FONT_SMALL,
                                 colour=C.text_secondary)
        bottom.Add(self.status, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)

        export_current = make_button(result_card.body, "导出当前页",
                                     lambda _evt: self.on_export(limit_page=True))
        export_all = make_button(result_card.body, "导出全部",
                                 lambda _evt: self.on_export(limit_page=False))
        bottom.Add(export_current, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        bottom.Add(export_all, 0, wx.ALIGN_CENTER_VERTICAL)

        result_card.add_spacer(10)
        result_card.add(bottom, 0, wx.EXPAND)
        root.Add(result_card, 1, wx.EXPAND | wx.ALL, theme.PAD)

        self.SetSizer(root)
        self.on_database_changed()

    # ------------------------------------------------------------------
    @property
    def database(self) -> str:
        index = self.database_choice.GetSelection()
        if index < 0 or index >= len(vm.EXPLORER_DATABASES):
            return vm.EXPLORER_DATABASES[0][0]
        return vm.EXPLORER_DATABASES[index][0]

    @property
    def table(self) -> str:
        index = self.table_choice.GetSelection()
        if index < 0 or index >= len(self._tables):
            return ""
        return self._tables[index]

    @property
    def page_size(self) -> int:
        return int(PAGE_SIZES[self.page_size_choice.GetSelection()])

    def _clear_result(self, message: str = ""):
        self._raw_frame = pd.DataFrame()
        self.total = 0
        self.grid.SetDataFrame(pd.DataFrame())
        self.status.SetLabel(message)

    def on_database_changed(self):
        """切换数据库时重新读取全部用户表。"""
        self._tables = []
        self.table_choice.Set([])
        self.column_choice.Set([])
        self._clear_result("正在读取数据表…")
        try:
            tables = vm.explorer_tables(self.database)
        except Exception as exc:  # pragma: no cover - 本地库一般不会失败
            error_dialog(self, exc)
            self._clear_result("读取数据表失败")
            return
        self._tables = list(tables)
        self.table_choice.Set(self._tables)
        if self._tables:
            self.table_choice.SetSelection(0)
        self.on_table_changed()

    def on_table_changed(self):
        """切换表时刷新列下拉框。"""
        if not self.table:
            self._clear_result("没有可浏览的数据表")
            return
        database, table = self.database, self.table

        def work():
            with vm.explorer_db(database) as conn:
                return vm.table_columns(conn, table, database=database)

        def done(columns):
            self.column_choice.Set([name for name, _label in columns])
            if columns:
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
        if not self.table:
            self._clear_result("没有可浏览的数据表")
            return
        if reset_page:
            self.page = 1

        symbols = self.symbol_input.GetValue().split()
        date_start = self.date_start.GetValue().strip() or None
        date_end = self.date_end.GetValue().strip() or None
        conditions = self._conditions()
        database, table, page, page_size = self.database, self.table, self.page, self.page_size

        def work():
            return vm.query_table(
                table, symbols=symbols, date_start=date_start, date_end=date_end,
                extra_conditions=conditions, page=page, page_size=page_size,
                database=database,
            )

        self.runner.run(work, self._on_data, on_error=lambda exc: error_dialog(self, exc),
                        busy_message=f"查询 {table} …")

    def _on_data(self, payload):
        df, total = payload
        self._raw_frame = df
        self.total = total
        self.render()

    def render(self, update_grid: bool = True):
        if update_grid:
            data = self._raw_frame
            if self.display_names.GetValue():
                data = data.rename(columns=vm.explorer_display_map(self.database))
            self.grid.SetDataFrame(data)

        pages = max(1, (self.total + self.page_size - 1) // self.page_size)
        self.status.SetLabel(f"共 {self.total:,} 行 · 第 {self.page}/{pages} 页")
        self.prev_button.Enable(self.page > 1)
        self.next_button.Enable(self.page < pages)
        relayout(self, self.grid)

    def on_page(self, delta: int):
        self.page = max(1, self.page + delta)
        self.on_query()

    def on_export(self, *, limit_page: bool):
        if not self.table:
            wx.MessageBox("没有可导出的数据表", "提示", wx.OK | wx.ICON_INFORMATION, self)
            return
        path = ask_save_path(self, default_name=f"{self.table}.csv")
        if not path:
            return

        symbols = self.symbol_input.GetValue().split()
        date_start = self.date_start.GetValue().strip() or None
        date_end = self.date_end.GetValue().strip() or None
        conditions = self._conditions()
        database, table = self.database, self.table
        display_names = self.display_names.GetValue()
        page_size = self.page_size if limit_page else 500000
        page = self.page if limit_page else 1

        def work():
            df, _total = vm.query_table(
                table, symbols=symbols, date_start=date_start, date_end=date_end,
                extra_conditions=conditions, page=page, page_size=page_size,
                database=database,
            )
            return vm.export_frame(
                df, path, display_names=display_names,
                display_names_map=vm.explorer_display_map(database),
            )

        def done(saved):
            wx.MessageBox(f"已导出到\n{saved}", "完成", wx.OK | wx.ICON_INFORMATION, self)

        self.runner.run(work, done, on_error=lambda exc: error_dialog(self, exc),
                        busy_message="导出中…")
