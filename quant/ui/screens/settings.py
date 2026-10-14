"""P6 设置 / 关于。"""

from __future__ import annotations

import importlib

import wx

from quant import config
from quant.ui import viewmodels as vm
from quant.ui.widgets import BusyRunner

DEPS = ["akshare", "backtrader", "pandas", "numpy", "matplotlib", "scipy",
        "mplfinance", "yfinance", "requests", "openpyxl", "ta", "talib", "statsmodels", "wx"]


class SettingsPanel(wx.Panel):
    """路径、版本、依赖、日志级别。"""

    def __init__(self, parent):
        super().__init__(parent)
        self.runner = BusyRunner(self)

        root = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(self, label="设置 / 关于")
        font = title.GetFont()
        font.SetPointSize(font.GetPointSize() + 3)
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        title.SetFont(font)
        root.Add(title, 0, wx.ALL, 10)

        box = wx.StaticBoxSizer(wx.VERTICAL, self, "路径（来自环境变量或 .env，只读）")
        self.paths = wx.FlexGridSizer(rows=0, cols=2, vgap=6, hgap=16)
        box.Add(self.paths, 0, wx.EXPAND | wx.ALL, 8)
        root.Add(box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        box2 = wx.StaticBoxSizer(wx.VERTICAL, self, "依赖")
        self.deps = wx.FlexGridSizer(rows=0, cols=4, vgap=4, hgap=14)
        box2.Add(self.deps, 0, wx.EXPAND | wx.ALL, 8)
        root.Add(box2, 0, wx.EXPAND | wx.ALL, 10)

        box3 = wx.StaticBoxSizer(wx.VERTICAL, self, "筛选方案")
        self.screens_label = wx.StaticText(self, label="")
        box3.Add(self.screens_label, 0, wx.ALL, 6)
        open_button = wx.Button(self, label="打开方案目录")
        open_button.Bind(wx.EVT_BUTTON, lambda _evt: self.open_screens_dir())
        box3.Add(open_button, 0, wx.ALL, 6)
        root.Add(box3, 0, wx.EXPAND | wx.ALL, 10)

        about = wx.StaticText(self, label="quant —— A股/美股选股研究与策略回测工具")
        root.Add(about, 0, wx.ALL, 10)

        self.SetSizer(root)
        self.refresh()

    def refresh(self):
        self.paths.Clear(delete_windows=True)
        for key, value in config.as_dict().items():
            label = wx.StaticText(self, label=key)
            label.SetMinSize((150, -1))
            self.paths.Add(label, 0)
            self.paths.Add(wx.StaticText(self, label=str(value)), 0)

        self.deps.Clear(delete_windows=True)
        for name in DEPS:
            try:
                module = importlib.import_module(name)
                text = f"{name} {getattr(module, '__version__', '?')}"
                colour = (46, 125, 50)
            except Exception:
                text = f"{name} 未安装"
                colour = (198, 40, 40)
            label = wx.StaticText(self, label=text)
            label.SetForegroundColour(wx.Colour(*colour))
            self.deps.Add(label, 0)

        try:
            screens = vm.list_screens()
            self.screens_label.SetLabel(
                f"目录：{vm.screens_dir()}\n已保存 {len(screens)} 个方案：{', '.join(screens) or '（无）'}"
            )
        except Exception as exc:  # pragma: no cover
            self.screens_label.SetLabel(f"读取失败：{exc}")
        self.Layout()

    def open_screens_dir(self):
        import subprocess
        import sys

        path = str(vm.screens_dir())
        try:
            if sys.platform.startswith("win"):
                subprocess.Popen(["explorer", path])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as exc:  # pragma: no cover
            wx.MessageBox(f"无法打开目录：{exc}", "提示", wx.OK | wx.ICON_WARNING, self)
