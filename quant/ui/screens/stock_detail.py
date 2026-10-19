"""P3 个股分析：指标卡 + K线 / 估值带 / 财务 / 估值历史 / 原始数据。"""

from __future__ import annotations

import wx

from quant.ui import charts, theme, viewmodels as vm
from quant.ui.components import (Card, PageHeader, make_button, make_notebook,
                                style_checkbox, style_input, text_label)
from quant.ui.theme import C
from quant.ui.widgets import (
    BusyRunner,
    DataFrameGrid,
    FigurePanel,
    MetricCards,
    ask_save_path,
    error_dialog,
    relayout,
)

RANGES = [("近 3 月", 60), ("近 1 年", 250), ("近 3 年", 750), ("近 5 年", 1250), ("全部", 0)]

#: K 线周期：显示名 -> 重采样频率
FREQS = [("日线", "D"), ("周线", "W"), ("月线", "M")]

#: 价格口径：显示名 -> charts.kline_figure 的 adjust
PRICE_MODES = [("前复权", "qfq"), ("不复权", "raw")]


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
        self.SetBackgroundColour(wx.Colour(C.bg))
        self.runner = BusyRunner(self)
        self.detail: vm.StockDetail | None = None

        root = wx.BoxSizer(wx.VERTICAL)

        self.header = PageHeader(
            self, "个股分析",
            subtitle="K 线、估值带、财务指标、估值历史与原始数据",
            actions=[("载入", lambda _evt: self.on_load(), True)],
        )
        root.Add(self.header, 0, wx.EXPAND | wx.ALL, theme.PAD)

        # ---- 查询条 ----
        query_card = Card(self)
        body = query_card.body

        line1 = wx.BoxSizer(wx.HORIZONTAL)
        line1.Add(text_label(body, "股票代码", colour=C.text_secondary), 0,
                  wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        # 绑定了 EVT_TEXT_ENTER 的 TextCtrl 必须带 wx.TE_PROCESS_ENTER 样式
        self.symbol_input = wx.TextCtrl(body, size=(100, -1), value="000001",
                                        style=wx.TE_PROCESS_ENTER)
        style_input(self.symbol_input)
        self.symbol_input.Bind(wx.EVT_TEXT_ENTER, lambda _evt: self.on_load())
        line1.Add(self.symbol_input, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        line1.Add(make_button(body, "载入", lambda _evt: self.on_load()), 0,
                  wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 24)

        self.search_input = style_input(wx.TextCtrl(body, size=(170, -1)), width=170)
        self.search_input.SetHint("按名称搜索，如 平安")
        line1.Add(self.search_input, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        line1.Add(make_button(body, "搜索", lambda _evt: self.on_search()), 0,
                  wx.ALIGN_CENTER_VERTICAL)

        line1.AddStretchSpacer()
        self.title = text_label(body, "", size=theme.FONT_PAGE_TITLE, bold=True, colour=C.text)
        line1.Add(self.title, 0, wx.ALIGN_CENTER_VERTICAL)
        query_card.add(line1, 0, wx.EXPAND)

        line2 = wx.BoxSizer(wx.HORIZONTAL)
        line2.Add(text_label(body, "区间", colour=C.text_secondary), 0,
                  wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.range_choice = style_input(wx.Choice(body, choices=[name for name, _ in RANGES]))
        self.range_choice.SetSelection(1)
        self.range_choice.Bind(wx.EVT_CHOICE, lambda _evt: self.render())
        line2.Add(self.range_choice, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 20)

        line2.Add(text_label(body, "周期", colour=C.text_secondary), 0,
                  wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.freq_choice = style_input(wx.Choice(body, choices=[name for name, _ in FREQS]))
        self.freq_choice.SetSelection(0)
        self.freq_choice.Bind(wx.EVT_CHOICE, lambda _evt: self.render())
        line2.Add(self.freq_choice, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 20)

        line2.Add(text_label(body, "复权", colour=C.text_secondary), 0,
                  wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.price_choice = style_input(wx.Choice(body, choices=[name for name, _ in PRICE_MODES]))
        self.price_choice.SetSelection(0)
        self.price_choice.Bind(wx.EVT_CHOICE, lambda _evt: self.render())
        line2.Add(self.price_choice, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 20)

        self.macd_check = style_checkbox(wx.CheckBox(body, label="MACD"))
        self.rsi_check = style_checkbox(wx.CheckBox(body, label="RSI"))
        for checkbox in (self.macd_check, self.rsi_check):
            checkbox.Bind(wx.EVT_CHECKBOX, lambda _evt: self.render())
            line2.Add(checkbox, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)
        line2.AddStretchSpacer()
        query_card.add_spacer(10)
        query_card.add(line2, 0, wx.EXPAND)

        root.Add(query_card, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.PAD)

        # ---- 指标卡 ----
        self.cards = MetricCards(self, columns=6)
        root.Add(self.cards, 0, wx.EXPAND | wx.ALL, theme.PAD)

        # ---- 页签 ----
        tab_card = Card(self)
        self.notebook = make_notebook(tab_card.body)
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
        raw_panel.SetBackgroundColour(wx.Colour(C.card))
        raw_sizer = wx.BoxSizer(wx.VERTICAL)
        raw_head = wx.BoxSizer(wx.HORIZONTAL)
        self.raw_choice = style_input(wx.Choice(raw_panel, choices=[
            "日线", "财务指标", "基本面", "单季增长", "估值", "分位"]))
        self.raw_choice.SetSelection(0)
        self.raw_choice.Bind(wx.EVT_CHOICE, lambda _evt: self.render_raw())
        raw_head.Add(self.raw_choice, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        raw_head.Add(make_button(raw_panel, "导出当前表",
                                 lambda _evt: self.on_export_raw()), 0,
                     wx.ALIGN_CENTER_VERTICAL)
        raw_head.AddStretchSpacer()
        raw_sizer.Add(raw_head, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 8)
        self.raw_grid = DataFrameGrid(raw_panel)
        raw_sizer.Add(self.raw_grid, 1, wx.EXPAND)
        raw_panel.SetSizer(raw_sizer)
        self.notebook.AddPage(raw_panel, "原始数据")
        self.tabs["raw"] = raw_panel

        tab_card.add(self.notebook, 1, wx.EXPAND)
        root.Add(tab_card, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, theme.PAD)

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
        relayout(self, self.notebook, self.notebook.GetCurrentPage())

    def _render_cards(self):
        metrics = self.detail.metrics if self.detail else {}
        change = metrics.get("pct_change") or 0
        items = [
            ("最新价", _fmt(metrics.get("close")), None),
            ("涨跌幅", _fmt(metrics.get("pct_change"), percent=True),
             C.up if change >= 0 else C.down),
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

    @property
    def freq(self) -> str:
        return FREQS[self.freq_choice.GetSelection()][1]

    @property
    def adjust(self) -> str:
        return PRICE_MODES[self.price_choice.GetSelection()][1]

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

        freq = self.freq
        adjust = self.adjust
        freq_label = FREQS[self.freq_choice.GetSelection()][0]
        mode_label = PRICE_MODES[self.price_choice.GetSelection()][0]

        try:
            kline_source = charts.resample_ohlc(price, freq) if freq != "D" else price
            self.kline_panel.set_figure(charts.kline_figure(
                kline_source,
                title=f"{title} {freq_label}（{mode_label}）",
                adjust=adjust,
                ma_periods=(5, 10, 20, 60) if freq == "D" else (5, 10, 20),
                macd=self.macd_check.GetValue(),
                rsi=self.rsi_check.GetValue(),
            ))
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
