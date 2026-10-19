"""P1 数据总览。"""

from __future__ import annotations

import wx

from quant.ui import theme
from quant.ui.components import Card, PageHeader, make_button, text_label
from quant.ui.theme import C
from quant.ui import viewmodels as vm
from quant.ui.widgets import BusyRunner, error_dialog


class DashboardPanel(wx.Panel):
    """数据新鲜度 + 数据量 + 更新入口。"""

    def __init__(self, parent):
        super().__init__(parent)
        self.SetBackgroundColour(wx.Colour(C.bg))
        self.runner = BusyRunner(self)

        root = wx.BoxSizer(wx.VERTICAL)

        self.header = PageHeader(
            self, "数据总览",
            subtitle="检查数据新鲜度、数据量，并就地触发更新",
            actions=[("刷新", self.refresh, True)],
        )
        root.Add(self.header, 0, wx.EXPAND | wx.ALL, theme.PAD)

        row = wx.BoxSizer(wx.HORIZONTAL)

        # ---- 数据新鲜度 ----
        fresh_card = Card(self, "数据新鲜度", "绿色为最新，橙色表示需要更新")
        self.freshness = wx.FlexGridSizer(rows=0, cols=3, vgap=10, hgap=20)
        self.freshness.AddGrowableCol(0, 1)
        fresh_card.add(self.freshness, 1, wx.EXPAND)
        self._fresh_parent = fresh_card.body
        row.Add(fresh_card, 1, wx.EXPAND | wx.RIGHT, theme.GAP)

        # ---- 数据量 ----
        count_card = Card(self, "数据量", "各表行数与磁盘占用")
        self.counts = wx.FlexGridSizer(rows=0, cols=3, vgap=10, hgap=20)
        self.counts.AddGrowableCol(0, 1)
        count_card.add(self.counts, 1, wx.EXPAND)
        self._count_parent = count_card.body
        row.Add(count_card, 1, wx.EXPAND)

        root.Add(row, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.PAD)

        # ---- 快捷操作 ----
        action_card = Card(
            self, "快捷操作",
            "后台执行、需要联网，耗时较长；执行期间可以继续使用其它页面",
        )
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        for action in vm.available_updates():
            button = make_button(action_card.body, action["label"],
                                 lambda _evt, key=action["key"]: self.on_update(key))
            button.SetToolTip(action["desc"])
            buttons.Add(button, 0, wx.RIGHT, 8)
        action_card.add(buttons, 0, wx.EXPAND)
        root.Add(action_card, 0, wx.EXPAND | wx.ALL, theme.PAD)

        self.SetSizer(root)
        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self):
        """重新读取数据状态（后台线程查库）。"""
        self.runner.run(lambda: vm.data_status(), self._render, busy_message="读取数据状态…")

    def _render(self, status: vm.DataStatus):
        self.freshness.Clear(delete_windows=True)
        self.counts.Clear(delete_windows=True)

        for name, value, stale in status.report():
            self._add_row(self.freshness, self._fresh_parent, name, value, stale)

        for table, rows in sorted(status.counts.items()):
            self._add_row(self.counts, self._count_parent, table, f"{rows:,}", False)
        self._add_row(self.counts, self._count_parent, "数据库大小",
                      f"{status.db_size_mb:,.0f} MB", False)
        self._add_row(self.counts, self._count_parent, "原始件归档",
                      f"{status.archive_size_mb:,.0f} MB", False)
        self.Layout()

    def _add_row(self, sizer: wx.FlexGridSizer, parent, name: str, value: str, warn: bool):
        label = text_label(parent, name, colour=C.text)
        label.SetMinSize((160, -1))
        colour = C.warn if warn else C.ok
        number = text_label(parent, str(value), mono=True, bold=True, colour=colour)
        note = text_label(parent, "需要更新" if warn else "正常",
                          size=theme.FONT_SMALL, colour=colour)
        sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(number, 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(note, 0, wx.ALIGN_CENTER_VERTICAL)

    # ------------------------------------------------------------------
    def on_update(self, key: str):
        action = next((a for a in vm.available_updates() if a["key"] == key), None)
        if action is None:
            return

        message = (f"确定要执行「{action['label']}」吗？\n\n{action['desc']}\n\n"
                   f"等价命令：{action['command']}\n\n执行期间需要联网，可能持续几分钟。")
        if wx.MessageBox(message, "确认", wx.YES_NO | wx.ICON_QUESTION, self) != wx.YES:
            return

        def work():
            import datetime

            from quant.data import store, update

            store.init_db()
            year = datetime.date.today().year
            if key == "price":
                return update.update_price(workers=4, delay=0.1)
            if key == "jibenmian":
                return update.update_jibenmian(from_year=year - 1, to_year=year)
            if key == "financial":
                return update.update_financial(stale_days=180, workers=4, delay=0.2)
            if key == "valuation":
                from quant.foundation.valuation import rebuild_fundamental_ttm, rebuild_valuation

                with store.open_db() as conn:
                    rebuild_fundamental_ttm(conn)
                    return rebuild_valuation(workers=4, conn=conn)
            raise ValueError(key)

        def done(result):
            wx.MessageBox(f"{action['label']}完成：\n{result}", "完成",
                          wx.OK | wx.ICON_INFORMATION, self)
            self.refresh()

        self.runner.run(work, done, on_error=lambda exc: error_dialog(self, exc),
                        busy_message=f"{action['label']}中…")
