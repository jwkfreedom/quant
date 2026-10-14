"""P3 个股分析：指标卡 + K线 / 估值带 / 财务 / 估值历史 / 原始数据。"""

from __future__ import annotations

import wx

from quant.ui import charts, viewmodels as vm
from quant.ui.widgets import BusyRunner, DataFrameGrid, FigurePanel, error_dialog, ask_save_path

RANGES = [("近 3 月", 60), ("近 1 年", 250), ("近 3 年", 750), ("近 5 年", 1250), ("全部", 0)]


def _fmt(value, digits: int = 2, unit: str = "", percent: bool = False) -> str:
    if value is None:
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    text = f"{number:,.{digits}f}"
    if percent:
        text += "%"
    if unit:
        text += unit
    return text


class StockDetailPanel(wx.Panel):
    """个股图表与分析。"""

    def __init__(self, parent):
        super().__init__(parent)
        self.runner = BusyRunner(self)
        self.detail: vm.StockDetail | None = None

        root = wx.BoxSizer(wx.VERTICAL)

        # ---- 顶部：代码输入 ----
        top = wx.BoxSizer(wx.HORIZONTAL)
        top.Add(wx.StaticText(self, label="股票代码"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 6)
        # 绑定了 EVT_TEXT_ENTER 的 TextCtrl 必须带 wx.TE_PROCESS_ENTER 样式
        self.symbol_input = wx.TextCtrl(self, size=(100, -1), value="000001",
                                        style=wx.TE_PROCESS_ENTER)
        self.symbol_input.Bind(wx.EVT_TEXT_ENTER, lambda _evt: self.on_load())
        top.Add(self.symbol_input, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)

        load_button = wx.Button(self, label="载入")
        load_button.Bind(wx.EVT_BUTTON, lambda _evt: self.on_load())
        top.Add(load_button, 0, wx.ALL, 4)

        self.search_input = wx.TextCtrl(self, size=(150, -1))
        self.search_input.SetHint("按名称搜索")
        search_button = wx.Button(self, label="搜索")
        search_button.Bind(wx.EVT_BUTTON, lambda _evt: self.on_search())
        top.Add(self.search_input, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 8)
        top.Add(search_button, 0, wx.ALL, 4)

        top.Add(wx.StaticText(self, label="区间"), 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 12)
        self.range_choice = wx.Choice(self, choices=[name for name, _ in RANGES])
        self.range_choice.SetSelection(1)
        self.range_choice.Bind(wx.EVT_CHOICE, lambda _evt: self.render())
        top.Add(self.range_choice, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)

        top.AddStretchSpacer()
        self.title = wx.StaticText(self, label="")
        font = self.title.GetFont()
        font.SetPointSize(font.GetPointSize() + 2)
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.title.SetFont(font)
        top.Add(self.title, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        root.Add(top, 0, wx.EXPAND | wx.ALL, 6)

        # ---- 指标卡 ----
        from quant.ui.widgets import MetricCards

        self.cards = MetricCards(self, columns=6)
        root.Add(self.cards, 0, wx.EXPAND | wx.ALL, 6)

        # ---- 页签 ----
        self.notebook = wx.Notebook(self)
        self.tabs: dict[str, wx.Window] = {}

        self.kline_panel = FigurePanel(self.notebook)
        self.notebook.AddPage(self.kline_panel, "K线")
        self.tabs["kline"] = self.kline_panel

        self.band_panel = FigurePanel(self.notebook)
        self.notebook.AddPage(self.band_panel, "估值带")
        self.tabs["band"] = self.band_panel

        self.finance_panel = FigurePanel(self.notebook)
        self.notebook.AddPage(self.finance_panel, "财务指标")
        self.tabs["finance"] = self.finance_panel

        self.history_panel = FigurePanel(self.notebook)
        self.notebook.AddPage(self.history_panel, "估值历史")
        self.tabs["history"] = self.history_panel

        raw_panel = wx.Panel(self.notebook)
        raw_sizer = wx.BoxSizer(wx.VERTICAL)
        self.raw_choice = wx.Choice(raw_panel, choices=["日线", "财务指标", "基本面", "单季增长", "估值", "分位"])
        self.raw_choice.SetSelection(0)
        self.raw_choice.Bind(wx.EVT_CHOICE, lambda _evt: self.render_raw())
        raw_head = wx.BoxSizer(wx.HORIZONTAL)
        raw_head.Add(self.raw_choice, 0, wx.ALL, 4)
        export_button = wx.Button(raw_panel, label="导出当前表")
        export_button.Bind(wx.EVT_BUTTON, lambda _evt: self.on_export_raw())
        raw_head.Add(export_button, 0, wx.ALL, 4)
        raw_sizer.Add(raw_head, 0)
        self.raw_grid = DataFrameGrid(raw_panel)
        raw_sizer.Add(self.raw_grid, 1, wx.EXPAND | wx.ALL, 4)
        raw_panel.SetSizer(raw_sizer)
        self.notebook.AddPage(raw_panel, "原始数据")
        self.tabs["raw"] = raw_panel

        root.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 6)
        self.SetSizer(root)

    # ------------------------------------------------------------------
    def on_load(self, symbol: str | None = None):
        code = (symbol or self.symbol_input.GetValue()).strip()
        if not code:
            return
        self.symbol_input.SetValue(code)

        def work():
            return vm.stock_detail(code)

        self.runner.run(work, self._render_detail, on_error=lambda exc: error_dialog(self, exc),
                        busy_message=f"载入 {code} …")

    def on_search(self):
        keyword = self.search_input.GetValue().strip()
        if not keyword:
            return

        def work():
            return vm.stock_list(keyword=keyword)

        def done(frame):
            if frame.empty:
                wx.MessageBox("没有匹配的股票", "提示", wx.OK | wx.ICON_INFORMATION, self)
                return
            labels = [f"{row.symbol} {row.name}" for row in frame.head(200).itertuples()]
            dialog = wx.SingleChoiceDialog(self, "选择股票", "搜索结果", labels)
            if dialog.ShowModal() == wx.ID_OK:
                self.on_load(labels[dialog.GetSelection()].split()[0])
            dialog.Destroy()

        self.runner.run(work, done, on_error=lambda exc: error_dialog(self, exc))

    # ------------------------------------------------------------------
    def _render_detail(self, detail: vm.StockDetail):
        self.detail = detail
        self.title.SetLabel(f"{detail.symbol} {detail.name}")
        self._render_cards()
        self.render()
        self.render_raw()
        self.Layout()

    def _render_cards(self):
        metrics = self.detail.metrics if self.detail else {}
        items = [
            ("最新价", _fmt(metrics.get("close")), None),
            ("涨跌幅", _fmt(metrics.get("pct_change"), percent=True),
             (198, 40, 40) if (metrics.get("pct_change") or 0) >= 0 else (46, 125, 50)),
            ("总市值", _fmt((metrics.get("market_cap") or 0) / 1e8, 1, " 亿") if metrics.get("market_cap") else "—", None),
            ("PE(TTM)", _fmt(metrics.get("pe")), None),
            ("PE 十年分位", _fmt(metrics.get("pe_pct_10y"), 1, "%"), None),
            ("PB(TTM)", _fmt(metrics.get("pb")), None),
            ("PB 十年分位", _fmt(metrics.get("pb_pct_10y"), 1, "%"), None),
            ("PS(TTM)", _fmt(metrics.get("ps")), None),
            ("ROE", _fmt(metrics.get("roe"), percent=True), None),
            ("资产负债率", _fmt(metrics.get("debt_ratio"), percent=True), None),
            ("单季营收同比", _fmt(metrics.get("season_income_growth"), percent=True), None),
            ("单季利润同比", _fmt(metrics.get("season_profit_growth"), percent=True), None),
        ]
        self.cards.set_metrics([(t, v, c) for t, v, c in items])

    def _sliced(self, frame):
        if frame is None or frame.empty:
            return frame
        _, bars = RANGES[self.range_choice.GetSelection()]
        return frame if bars == 0 else frame.tail(bars)

    def render(self):
        if self.detail is None:
            return
        price = self._sliced(self.detail.price)
        valuation = self._sliced(self.detail.valuation)
        title = f"{self.detail.symbol} {self.detail.name}"

        try:
            self.kline_panel.set_figure(charts.kline_figure(price, title=f"{title} K线"))
            self.band_panel.set_figure(charts.valuation_band_figure(valuation, title=f"{title} 估值带"))
            self.finance_panel.set_figure(
                charts.financial_figure(self.detail.fundamental, self.detail.growth, title=f"{title} 财务"))
            self.history_panel.set_figure(
                charts.valuation_history_figure(valuation, title=f"{title} 估值历史"))
        except Exception as exc:  # pragma: no cover - 绘图失败不该让界面崩掉
            error_dialog(self, exc)

    def _raw_frame(self):
        if self.detail is None:
            return None
        return {
            "日线": self.detail.price,
            "财务指标": self.detail.financial,
            "基本面": self.detail.fundamental,
            "单季增长": self.detail.growth,
            "估值": self.detail.valuation,
            "分位": self.detail.percentiles,
        }.get(self.raw_choice.GetStringSelection())

    def render_raw(self):
        self.raw_grid.SetDataFrame(self._raw_frame())

    def on_export_raw(self):
        frame = self._raw_frame()
        if frame is None or frame.empty:
            wx.MessageBox("没有数据可导出", "提示", wx.OK | wx.ICON_INFORMATION, self)
            return
        path = ask_save_path(self, default_name=f"{self.detail.symbol}_{self.raw_choice.GetStringSelection()}.csv")
        if not path:
            return
        try:
            wx.MessageBox(f"已导出 {vm.export_frame(frame, path)}", "完成",
                          wx.OK | wx.ICON_INFORMATION, self)
        except Exception as exc:
            error_dialog(self, exc)
