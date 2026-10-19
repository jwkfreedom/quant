"""P6 设置 / 关于。"""

from __future__ import annotations

import importlib

import wx

from quant import config
from quant.ui import theme
from quant.ui import viewmodels as vm
from quant.ui.components import Card, PageHeader, make_button, text_label
from quant.ui.theme import C
from quant.ui.widgets import BusyRunner

DEPS = ["akshare", "backtrader", "pandas", "numpy", "matplotlib", "scipy",
        "mplfinance", "yfinance", "requests", "openpyxl", "ta", "talib", "statsmodels", "wx"]


class SettingsPanel(wx.Panel):
    """路径、版本、依赖、日志级别。"""

    def __init__(self, parent):
        super().__init__(parent)
        self.SetBackgroundColour(wx.Colour(C.bg))
        self.runner = BusyRunner(self)

        root = wx.BoxSizer(wx.VERTICAL)

        self.header = PageHeader(self, "设置 / 关于", subtitle="运行环境与依赖状态")
        root.Add(self.header, 0, wx.EXPAND | wx.ALL, theme.PAD)

        # ---- 路径 ----
        path_card = Card(self, "路径", "来自环境变量或 .env，只读")
        self.paths = wx.FlexGridSizer(rows=0, cols=2, vgap=8, hgap=20)
        self.paths.AddGrowableCol(1, 1)
        path_card.add(self.paths, 0, wx.EXPAND)
        self._path_parent = path_card.body
        root.Add(path_card, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.PAD)

        # ---- 依赖 ----
        dep_card = Card(self, "依赖", "绿色已安装，红色缺失")
        self.deps = wx.FlexGridSizer(rows=0, cols=4, vgap=8, hgap=20)
        dep_card.add(self.deps, 0, wx.EXPAND)
        self._dep_parent = dep_card.body
        root.Add(dep_card, 0, wx.EXPAND | wx.ALL, theme.PAD)

        # ---- 筛选方案 ----
        screen_card = Card(self, "筛选方案", "方案以 JSON 保存在项目目录，可手工编辑")
        self.screens_label = text_label(screen_card.body, "", colour=C.text_secondary)
        screen_card.add(self.screens_label, 0, wx.EXPAND)
        screen_card.add_spacer(10)
        screen_card.add(make_button(screen_card.body, "打开方案目录",
                                    lambda _evt: self.open_screens_dir()), 0, wx.ALIGN_LEFT)
        root.Add(screen_card, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.PAD)

        about = text_label(self, "quant —— A股/美股选股研究与策略回测工具  ·  "
                                 "配色规范见 docs/ui_theme.md",
                           size=theme.FONT_SMALL, colour=C.text_muted)
        root.Add(about, 0, wx.ALL, theme.PAD)

        self.SetSizer(root)
        self.refresh()

    def refresh(self):
        self.paths.Clear(delete_windows=True)
        for key, value in config.as_dict().items():
            label = text_label(self._path_parent, key, colour=C.text_secondary)
            label.SetMinSize((140, -1))
            self.paths.Add(label, 0, wx.ALIGN_CENTER_VERTICAL)
            self.paths.Add(text_label(self._path_parent, str(value), size=theme.FONT_SMALL,
                                      mono=True, colour=C.text), 0, wx.ALIGN_CENTER_VERTICAL)

        self.deps.Clear(delete_windows=True)
        for name in DEPS:
            try:
                module = importlib.import_module(name)
                text = f"{name} {getattr(module, '__version__', '?')}"
                colour = C.ok
            except Exception:
                text = f"{name} 未安装"
                colour = C.warn
            self.deps.Add(text_label(self._dep_parent, text, size=theme.FONT_SMALL,
                                     mono=True, colour=colour), 0, wx.ALIGN_CENTER_VERTICAL)

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
