"""P1 数据总览。"""

from __future__ import annotations

import wx

from quant.ui import viewmodels as vm
from quant.ui.widgets import BusyRunner, error_dialog

COLOUR_OK = (46, 125, 50)
COLOUR_WARN = (198, 40, 40)


class DashboardPanel(wx.Panel):
    """数据新鲜度 + 数据量 + 更新入口。"""

    def __init__(self, parent):
        super().__init__(parent)
        self.runner = BusyRunner(self)

        root = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(self, label="数据总览")
        font = title.GetFont()
        font.SetPointSize(font.GetPointSize() + 3)
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        title.SetFont(font)
        root.Add(title, 0, wx.ALL, 10)

        box = wx.StaticBoxSizer(wx.VERTICAL, self, "数据新鲜度")
        self.freshness = wx.FlexGridSizer(rows=0, cols=3, vgap=6, hgap=16)
        box.Add(self.freshness, 0, wx.EXPAND | wx.ALL, 8)
        root.Add(box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        box2 = wx.StaticBoxSizer(wx.VERTICAL, self, "数据量")
        self.counts = wx.FlexGridSizer(rows=0, cols=3, vgap=6, hgap=16)
        box2.Add(self.counts, 0, wx.EXPAND | wx.ALL, 8)
        root.Add(box2, 0, wx.EXPAND | wx.ALL, 10)

        box3 = wx.StaticBoxSizer(wx.VERTICAL, self, "快捷操作（后台执行，需要联网）")
        hint = wx.StaticText(self, label="更新较慢，执行期间可以继续用其它页面；完成后会自动刷新状态。")
        hint.SetForegroundColour(wx.Colour(120, 120, 120))
        box3.Add(hint, 0, wx.ALL, 6)

        buttons = wx.BoxSizer(wx.HORIZONTAL)
        for action in vm.available_updates():
            button = wx.Button(self, label=action["label"])
            button.Bind(wx.EVT_BUTTON, lambda _evt, key=action["key"]: self.on_update(key))
            button.SetToolTip(action["desc"])
            buttons.Add(button, 0, wx.ALL, 4)
        box3.Add(buttons, 0, wx.ALL, 4)
        root.Add(box3, 0, wx.EXPAND | wx.ALL, 10)

        refresh = wx.Button(self, label="刷新")
        refresh.Bind(wx.EVT_BUTTON, lambda _evt: self.refresh())
        root.Add(refresh, 0, wx.ALL, 10)

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
            self._add_row(self.freshness, name, value, stale)

        for table, rows in sorted(status.counts.items()):
            self._add_row(self.counts, table, f"{rows:,}", False)
        self._add_row(self.counts, "数据库大小", f"{status.db_size_mb:,.0f} MB", False)
        self._add_row(self.counts, "原始件归档", f"{status.archive_size_mb:,.0f} MB", False)
        self.Layout()

    def _add_row(self, sizer: wx.FlexGridSizer, name: str, value: str, warn: bool):
        label = wx.StaticText(self, label=name)
        label.SetMinSize((150, -1))
        text = wx.StaticText(self, label=str(value))
        text.SetForegroundColour(wx.Colour(*(COLOUR_WARN if warn else COLOUR_OK)))
        note = wx.StaticText(self, label="需要更新" if warn else "正常")
        sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(text, 0, wx.ALIGN_CENTER_VERTICAL)
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
