"""主窗口与导航。

用法：python -m quant ui
"""

from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)

try:
    import wx
except ImportError as exc:  # pragma: no cover - 依赖缺失时的友好提示
    raise SystemExit(
        "未安装 wxPython，无法启动桌面界面。\n"
        "请执行： .venv\\Scripts\\python.exe -m pip install wxPython\n"
        f"（原始错误：{exc}）"
    ) from exc

from quant import config  # noqa: E402
from quant.ui import theme  # noqa: E402
from quant.ui.components import SideNav, make_font, text_label  # noqa: E402
from quant.ui.screens.backtest import BacktestPanel  # noqa: E402
from quant.ui.screens.dashboard import DashboardPanel  # noqa: E402
from quant.ui.screens.explorer import ExplorerPanel  # noqa: E402
from quant.ui.screens.screener import ScreenerPanel  # noqa: E402
from quant.ui.screens.settings import SettingsPanel  # noqa: E402
from quant.ui.screens.stock_detail import StockDetailPanel  # noqa: E402
from quant.ui.theme import C  # noqa: E402

PAGES = [
    ("数据总览", DashboardPanel),
    ("选股筛选", ScreenerPanel),
    ("个股分析", StockDetailPanel),
    ("策略回测", BacktestPanel),
    ("数据浏览器", ExplorerPanel),
    ("设置/关于", SettingsPanel),
]

NAV_WIDTH = 190


class MainFrame(wx.Frame):
    """主窗口：左侧自绘导航 + 右侧页面（Simplebook，无页签）。"""

    def __init__(self, parent=None):
        super().__init__(parent, title="quant —— 选股研究与策略回测", size=(1440, 900))
        self.SetBackgroundColour(wx.Colour(C.bg))

        # 注意顺序：状态栏必须**先**创建，页面在构造时就会调用 set_status
        self.CreateStatusBar(2)
        self.SetStatusWidths([-1, 340])
        self._style_status_bar()
        self._build_menu()

        root = wx.BoxSizer(wx.HORIZONTAL)

        # ---- 左侧导航 ----
        side = wx.Panel(self)
        side.SetBackgroundColour(wx.Colour(C.bg))
        side.SetMinSize((NAV_WIDTH, -1))
        side_sizer = wx.BoxSizer(wx.VERTICAL)

        brand = text_label(side, "quant", size=15, bold=True, colour=C.text)
        side_sizer.Add(brand, 0, wx.LEFT | wx.TOP, theme.PAD + 4)
        side_sizer.Add(text_label(side, "选股研究 · 策略回测", size=theme.FONT_SMALL,
                                  colour=C.text_muted), 0, wx.LEFT | wx.TOP | wx.BOTTOM,
                       theme.PAD + 4)
        side_sizer.AddSpacer(6)

        self.nav = SideNav(side, [title for title, _ in PAGES], width=NAV_WIDTH,
                           on_select=self._on_nav_select)
        side_sizer.Add(self.nav, 0, wx.EXPAND)
        side_sizer.AddStretchSpacer()
        side.SetSizer(side_sizer)
        root.Add(side, 0, wx.EXPAND)

        # ---- 右侧页面 ----
        self.book = wx.Simplebook(self)
        self.book.SetBackgroundColour(wx.Colour(C.bg))
        self.panels: dict[str, wx.Window] = {}
        for title, panel_class in PAGES:
            panel = panel_class(self.book)
            self.book.AddPage(panel, title)
            self.panels[title] = panel
        self.book.SetSelection(0)
        root.Add(self.book, 1, wx.EXPAND)

        self.SetSizer(root)

        self.set_status("就绪")
        self.SetStatusText(f"数据库 {config.DB_PATH}", 1)
        self.Centre()

    # ------------------------------------------------------------------
    # 外观
    # ------------------------------------------------------------------
    def _style_status_bar(self):
        bar = self.GetStatusBar()
        if bar is None:
            return
        bar.SetBackgroundColour(wx.Colour(C.status_bg))
        bar.SetForegroundColour(wx.Colour(C.text_secondary))
        bar.SetFont(make_font(theme.FONT_SMALL))
        for index in range(bar.GetFieldsCount()):
            bar.SetStatusText("", index)

    def _build_menu(self):
        menu_bar = wx.MenuBar()

        file_menu = wx.Menu()
        item = file_menu.Append(wx.ID_EXIT, "退出\tCtrl+Q")
        self.Bind(wx.EVT_MENU, lambda _evt: self.Close(), item)
        menu_bar.Append(file_menu, "文件")

        tools_menu = wx.Menu()
        item = tools_menu.Append(wx.ID_REFRESH, "刷新当前页\tF5")
        self.Bind(wx.EVT_MENU, lambda _evt: self.refresh_current(), item)
        menu_bar.Append(tools_menu, "工具")

        help_menu = wx.Menu()
        item = help_menu.Append(wx.ID_ABOUT, "关于")
        self.Bind(wx.EVT_MENU, lambda _evt: self.on_about(), item)
        docs = help_menu.Append(wx.ID_ANY, "打开文档目录")
        self.Bind(wx.EVT_MENU, lambda _evt: self.open_docs(), docs)
        menu_bar.Append(help_menu, "帮助")

        self.SetMenuBar(menu_bar)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key)

    def on_key(self, event):
        if event.GetKeyCode() == wx.WXK_F5:
            self.refresh_current()
        else:
            event.Skip()

    # ------------------------------------------------------------------
    # 页面切换
    # ------------------------------------------------------------------
    @property
    def current_title(self) -> str:
        index = self.book.GetSelection()
        return self.book.GetPageText(index) if index >= 0 else ""

    def switch_page(self, title: str) -> bool:
        """切换到指定页面（导航与 jump_to 都走这里）。"""
        if title not in self.panels:
            return False
        index = list(self.panels).index(title)
        self.book.SetSelection(index)
        self.nav.SetSelection(index)
        return True

    def _on_nav_select(self, index: int, title: str):
        self.book.SetSelection(index)

    def set_status(self, text: str):
        """状态栏左侧文本（后台任务会调用它）。

        防御性判断：页面构造阶段或状态栏被销毁后调用不应抛异常。
        """
        if self.GetStatusBar() is not None:
            self.SetStatusText(str(text), 0)

    def refresh_current(self):
        panel = self.panels.get(self.current_title)
        if panel is not None and hasattr(panel, "refresh"):
            panel.refresh()
        else:
            self.set_status("就绪")

    def jump_to(self, title: str, **kwargs):
        """切换页面并可选地把参数传给该页（例如跳到个股分析）。"""
        page = self.panels.get(title)
        if page is None:
            return
        self.switch_page(title)
        if kwargs and hasattr(page, "on_load"):
            symbol = kwargs.get("symbol")
            if symbol:
                page.on_load(symbol)

    # ------------------------------------------------------------------
    def on_about(self):
        from quant import __version__

        wx.MessageBox(
            f"quant {__version__}\n\n"
            f"A股/美股选股研究与策略回测工具\n"
            f"数据目录：{config.DATA_DIR}\n"
            f"数据库：{config.DB_PATH}\n"
            f"Python：{sys.version.split()[0]}\n"
            f"wxPython：{wx.version()}",
            "关于", wx.OK | wx.ICON_INFORMATION, self,
        )

    def open_docs(self):
        import subprocess

        path = str(config.PROJECT_ROOT / "docs")
        command = ["explorer", path] if sys.platform.startswith("win") else ["xdg-open", path]
        try:
            subprocess.Popen(command)
        except Exception as exc:  # pragma: no cover
            wx.MessageBox(f"无法打开目录：{exc}", "提示", wx.OK | wx.ICON_WARNING, self)


def run(argv=None) -> int:
    """启动界面主循环。"""
    config.setup_logging()
    app = wx.App(False)
    frame = MainFrame()
    frame.Show()

    # 支持 quant ui 000001 直接打开某只股票
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0].isdigit():
        frame.jump_to("个股分析", symbol=args[0])

    app.MainLoop()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run())
