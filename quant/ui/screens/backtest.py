"""P4 策略回测：参数表单 + 结果卡 + 净值曲线 + 成交明细。"""

from __future__ import annotations

import pandas as pd
import wx

from quant.ui import charts, theme, viewmodels as vm
from quant.ui.components import (Card, PageHeader, make_button, make_notebook,
                                style_input, text_label)
from quant.ui.theme import C
from quant.ui.widgets import (BusyRunner, DataFrameGrid, FigurePanel, MetricCards,
                             ask_save_path, error_dialog)

RANGE_CHOICES = ["2010-01-01", "2015-01-01", "2018-01-01", "2020-01-01", "2022-01-01"]

LEFT_WIDTH = 400


class BacktestPanel(wx.Panel):
    """策略回测页。"""

    def __init__(self, parent):
        super().__init__(parent)
        self.SetBackgroundColour(wx.Colour(C.bg))
        self.runner = BusyRunner(self)
        self.result = None
        self._last_strategy: str | None = None
        self.param_controls: dict[str, wx.TextCtrl] = {}

        root = wx.BoxSizer(wx.VERTICAL)

        self.header = PageHeader(
            self, "策略回测",
            subtitle="选择策略与标的，设置参数后运行；左侧说明显示当前策略的参数与算法",
            actions=[("运行回测", lambda _evt: self.on_run(), True)],
        )
        root.Add(self.header, 0, wx.EXPAND | wx.ALL, theme.PAD)

        columns = wx.BoxSizer(wx.HORIZONTAL)

        # ---------------- 左侧参数 ----------------
        left_panel = wx.Panel(self)
        left_panel.SetBackgroundColour(wx.Colour(C.bg))
        left_panel.SetMinSize((LEFT_WIDTH, -1))
        left = wx.BoxSizer(wx.VERTICAL)

        setting_card = Card(left_panel, "回测设置")
        body = setting_card.body
        form = wx.FlexGridSizer(rows=0, cols=2, vgap=10, hgap=12)
        form.AddGrowableCol(1, 1)

        form.Add(text_label(body, "策略", colour=C.text_secondary), 0, wx.ALIGN_CENTER_VERTICAL)
        self.strategy_choice = style_input(wx.Choice(
            body, choices=[info.name for info in vm.list_backtest_strategies()]))
        self.strategy_choice.SetSelection(0)
        self.strategy_choice.Bind(wx.EVT_CHOICE, lambda _evt: self.on_strategy_changed())
        form.Add(self.strategy_choice, 0)

        form.Add(text_label(body, "标的代码", colour=C.text_secondary), 0, wx.ALIGN_CENTER_VERTICAL)
        self.symbol_input = style_input(wx.TextCtrl(body, size=(110, -1)))
        form.Add(self.symbol_input, 0)

        form.Add(text_label(body, "起始日期", colour=C.text_secondary), 0, wx.ALIGN_CENTER_VERTICAL)
        self.start_choice = style_input(wx.ComboBox(body, choices=RANGE_CHOICES,
                                                    value="2018-01-01"))
        form.Add(self.start_choice, 0)

        form.Add(text_label(body, "初始资金", colour=C.text_secondary), 0, wx.ALIGN_CENTER_VERTICAL)
        self.cash_input = style_input(wx.TextCtrl(body, size=(110, -1), value="100000"))
        form.Add(self.cash_input, 0)

        form.Add(text_label(body, "手续费率", colour=C.text_secondary), 0, wx.ALIGN_CENTER_VERTICAL)
        self.commission_input = style_input(wx.TextCtrl(body, size=(110, -1), value="0.001"))
        form.Add(self.commission_input, 0)

        setting_card.add(form, 0, wx.EXPAND)
        setting_card.add_spacer(12)

        setting_card.add(text_label(body, "策略参数", size=theme.FONT_SMALL, bold=True,
                                    colour=C.text_secondary), 0, wx.EXPAND)
        setting_card.add_spacer(6)
        self.params_sizer = wx.FlexGridSizer(rows=0, cols=2, vgap=10, hgap=12)
        self.params_sizer.AddGrowableCol(1, 1)
        setting_card.add(self.params_sizer, 0, wx.EXPAND)
        setting_card.add_spacer(14)

        buttons = wx.BoxSizer(wx.HORIZONTAL)
        buttons.Add(make_button(body, "运行回测", lambda _evt: self.on_run(), primary=True), 0,
                    wx.RIGHT, 8)
        buttons.Add(make_button(body, "导出成交明细", lambda _evt: self.on_export()), 0)
        setting_card.add(buttons, 0, wx.EXPAND)

        self._left_panel = body
        left.Add(setting_card, 0, wx.EXPAND | wx.BOTTOM, theme.GAP)

        # ---- 策略说明（参数 + 算法，内容由策略声明生成）----
        explain_card = Card(left_panel, "策略说明", "参数含义与买卖算法，随策略切换自动更新")
        self.explain_text = wx.TextCtrl(
            explain_card.body,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP | wx.TE_RICH2,
        )
        self.explain_text.SetMinSize((340, 190))
        self.explain_text.SetFont(theme_font())
        self.explain_text.SetBackgroundColour(wx.Colour(C.card))
        self.explain_text.SetForegroundColour(wx.Colour(C.text))
        explain_card.add(self.explain_text, 1, wx.EXPAND)
        left.Add(explain_card, 1, wx.EXPAND)

        left_panel.SetSizer(left)
        columns.Add(left_panel, 0, wx.EXPAND | wx.RIGHT, theme.GAP)

        # ---------------- 右侧结果 ----------------
        tab_card = Card(self)
        self.notebook = make_notebook(tab_card.body)

        # --- 页签 1：单次回测结果 ---
        result_page = wx.Panel(self.notebook)
        result_page.SetBackgroundColour(wx.Colour(C.card))
        result_sizer = wx.BoxSizer(wx.VERTICAL)

        self.result_text = text_label(result_page, "尚未运行", size=theme.FONT_SMALL,
                                      colour=C.text_secondary)
        result_sizer.Add(self.result_text, 0, wx.EXPAND | wx.BOTTOM, 8)

        self.cards = MetricCards(result_page, columns=4)
        result_sizer.Add(self.cards, 0, wx.EXPAND | wx.BOTTOM, 8)

        self.figure_panel = FigurePanel(result_page)
        self.figure_panel.SetMinSize((-1, 240))
        result_sizer.Add(self.figure_panel, 1, wx.EXPAND | wx.BOTTOM, 8)

        self.grid = DataFrameGrid(result_page)
        self.grid.SetMinSize((-1, 150))
        result_sizer.Add(self.grid, 1, wx.EXPAND)
        result_page.SetSizer(result_sizer)
        self.notebook.AddPage(result_page, "回测结果")

        # --- 页签 2：参数扫描 ---
        sweep_page = wx.Panel(self.notebook)
        sweep_page.SetBackgroundColour(wx.Colour(C.card))
        sweep_sizer = wx.BoxSizer(wx.VERTICAL)

        sweep_controls = wx.BoxSizer(wx.HORIZONTAL)
        sweep_controls.Add(text_label(sweep_page, "参数", colour=C.text_secondary), 0,
                           wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.sweep_param = style_input(wx.Choice(sweep_page, choices=[]))
        sweep_controls.Add(self.sweep_param, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 16)

        self.sweep_start = style_input(wx.TextCtrl(sweep_page, size=(70, -1)))
        self.sweep_stop = style_input(wx.TextCtrl(sweep_page, size=(70, -1)))
        self.sweep_step = style_input(wx.TextCtrl(sweep_page, size=(70, -1)))
        for label, control, hint in (("从", self.sweep_start, "起始值"),
                                     ("到", self.sweep_stop, "结束值"),
                                     ("步长", self.sweep_step, "步长")):
            sweep_controls.Add(text_label(sweep_page, label, colour=C.text_secondary), 0,
                               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
            control.SetHint(hint)
            sweep_controls.Add(control, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        sweep_controls.Add(make_button(sweep_page, "开始扫描",
                                       lambda _evt: self.on_sweep(), primary=True), 0,
                           wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)

        self.sweep_status = text_label(sweep_page, "", size=theme.FONT_SMALL,
                                       colour=C.text_secondary)
        sweep_controls.Add(self.sweep_status, 1, wx.ALIGN_CENTER_VERTICAL)
        sweep_sizer.Add(sweep_controls, 0, wx.EXPAND | wx.BOTTOM, 10)

        self.sweep_figure_panel = FigurePanel(sweep_page)
        self.sweep_figure_panel.SetMinSize((-1, 260))
        sweep_sizer.Add(self.sweep_figure_panel, 1, wx.EXPAND | wx.BOTTOM, 8)

        self.sweep_grid = DataFrameGrid(sweep_page)
        self.sweep_grid.SetMinSize((-1, 140))
        sweep_sizer.Add(self.sweep_grid, 1, wx.EXPAND)
        sweep_page.SetSizer(sweep_sizer)
        self.notebook.AddPage(sweep_page, "参数扫描")

        tab_card.add(self.notebook, 1, wx.EXPAND)
        columns.Add(tab_card, 1, wx.EXPAND)

        root.Add(columns, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, theme.PAD)
        self.SetSizer(root)

        self.on_strategy_changed()

    # ------------------------------------------------------------------
    @property
    def strategy_name(self) -> str:
        return self.strategy_choice.GetStringSelection()

    def on_strategy_changed(self):
        """切换策略时重建参数表单，并填入默认标的。"""
        info = next((i for i in vm.list_backtest_strategies() if i.name == self.strategy_name), None)
        if info is None:
            return

        # 首次进入、或切换策略时，把标的换成该策略的默认标的
        current = self.symbol_input.GetValue().strip()
        if not current or self._last_strategy not in (None, info.name):
            self.symbol_input.SetValue(info.default_symbol)
        self._last_strategy = info.name

        # 策略说明：参数含义 + 算法步骤
        if hasattr(self, "explain_text"):
            self.explain_text.SetValue(info.explain())
            self.explain_text.SetInsertionPoint(0)

        # 参数扫描的可选参数跟着策略走
        if hasattr(self, "sweep_param"):
            self.sweep_param.Set([p["name"] for p in info.params])
            if info.params:
                self.sweep_param.SetSelection(0)
                self._fill_sweep_defaults(info.params[0])

        self.params_sizer.Clear(delete_windows=True)
        self.param_controls.clear()
        for param in info.params:
            label = text_label(self._left_panel, param.get("label", param["name"]),
                               colour=C.text_secondary)
            label.SetToolTip(param.get("help", ""))
            control = style_input(wx.TextCtrl(self._left_panel, size=(110, -1),
                                              value=str(param.get("default", ""))))
            self.params_sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL)
            self.params_sizer.Add(control, 0)
            self.param_controls[param["name"]] = control
        self.Layout()

    def _fill_sweep_defaults(self, param: dict):
        """按参数类型给出默认的扫描区间。"""
        default = param.get("default")
        if not isinstance(default, (int, float)):
            return
        low = param.get("min", 1)
        high = param.get("max", max(default * 3, 10))
        step = 1 if isinstance(default, int) else round((high - low) / 20, 4) or 0.05
        self.sweep_start.SetValue(str(low))
        self.sweep_stop.SetValue(str(high))
        self.sweep_step.SetValue(str(step))

    def on_sweep(self):
        """参数扫描：对选定参数逐个取值跑回测。"""
        name = self.strategy_name
        symbol = self.symbol_input.GetValue().strip()
        if not symbol:
            wx.MessageBox("请先填写标的代码", "提示", wx.OK | wx.ICON_INFORMATION, self)
            return

        param = self.sweep_param.GetStringSelection()
        if not param:
            return

        try:
            start = float(self.sweep_start.GetValue())
            stop = float(self.sweep_stop.GetValue())
            step = float(self.sweep_step.GetValue())
            values = vm.sweep_values(start, stop, step)
        except ValueError as exc:
            error_dialog(self, exc)
            return

        if len(values) > 200:
            if wx.MessageBox(f"将执行 {len(values)} 次回测，可能耗时较久，继续吗？",
                             "确认", wx.YES_NO | wx.ICON_QUESTION, self) != wx.YES:
                return

        cash = float(self.cash_input.GetValue() or 100000)
        commission = float(self.commission_input.GetValue() or 0.001)

        def work():
            return vm.sweep_backtest(
                name, symbol, param, values,
                progress=lambda done, total, value: wx.CallAfter(
                    self.sweep_status.SetLabel, f"进度 {done}/{total}（{param}={value}）"),
                cash=cash, commission=commission,
            )

        def done(table):
            self.sweep_status.SetLabel(f"完成 {len(table)} 组")
            self.sweep_grid.SetDataFrame(table)
            try:
                self.sweep_figure_panel.set_figure(
                    charts.sweep_figure(table, x_column=param,
                                        title=f"{name} @ {symbol}：{param} 扫描"))
            except Exception as exc:  # pragma: no cover
                error_dialog(self, exc)
            self.Layout()

        self.runner.run(work, done, on_error=lambda exc: error_dialog(self, exc),
                        busy_message=f"参数扫描 {param}…")

    def _collect_params(self) -> dict:
        params = {}
        for name, control in self.param_controls.items():
            text = control.GetValue().strip()
            if not text:
                continue
            try:
                params[name] = float(text) if ("." in text) else int(text)
            except ValueError as exc:
                raise ValueError(f"参数 {name} 不是数字: {text}") from exc
        return params

    def on_run(self):
        name = self.strategy_name
        symbol = self.symbol_input.GetValue().strip()
        cash = float(self.cash_input.GetValue() or 100000)
        commission = float(self.commission_input.GetValue() or 0.001)
        start = self.start_choice.GetValue().strip()

        try:
            params = self._collect_params()
        except ValueError as exc:
            error_dialog(self, exc)
            return

        def work():
            from datetime import datetime

            kwargs = {"cash": cash, "commission": commission, **params}
            if name == "volume_breakout":
                kwargs["fromdate"] = datetime.strptime(start, "%Y-%m-%d")
            return vm.run_backtest(name, symbol=symbol, **kwargs)

        self.runner.run(work, self._render, on_error=lambda exc: error_dialog(self, exc),
                        busy_message=f"回测 {name} @ {symbol} …")

    def _render(self, result):
        self.result = result
        self.cards.set_metrics([
            ("总收益率", f"{result.return_pct:.2f}%",
             C.up if result.return_pct >= 0 else C.down),
            ("年化收益", f"{result.annual_return:.2f}%", None),
            ("夏普比率", f"{result.sharpe:.2f}", None),
            ("最大回撤", f"{result.max_drawdown_pct:.2f}%", C.down),
            ("交易次数", str(result.trades), None),
            ("胜率", f"{result.win_rate:.1f}%", None),
            ("最终市值", f"{result.final_value:,.0f}", None),
            ("区间", f"{result.start} ~ {result.end}", None),
        ])
        try:
            self.figure_panel.set_figure(charts.equity_figure(result))
        except Exception as exc:  # pragma: no cover
            error_dialog(self, exc)
        self.grid.SetDataFrame(pd.DataFrame(result.trade_list), display_names=True)

        # 结果文字摘要：即使卡片/图表出问题，用户也能看到结果
        self.result_text.SetLabel(result.report().replace("\n", "    "))
        self.relayout()

    def relayout(self):
        """控件重建后强制重新布局与重绘（wx 不会自动跟着 sizer 变化刷新）。"""
        for window in (self.notebook.GetCurrentPage(), self.notebook, self):
            if window is not None:
                window.Layout()
                window.Refresh()
        self.Update()

    def on_export(self):
        if self.result is None or not self.result.trade_list:
            wx.MessageBox("还没有成交记录", "提示", wx.OK | wx.ICON_INFORMATION, self)
            return
        path = ask_save_path(self, default_name=f"trades_{self.result.symbol}.csv")
        if not path:
            return
        try:
            wx.MessageBox(f"已导出 {vm.export_frame(pd.DataFrame(self.result.trade_list), path, display_names=True)}",
                          "完成", wx.OK | wx.ICON_INFORMATION, self)
        except Exception as exc:
            error_dialog(self, exc)


def theme_font():
    """策略说明用的等宽字体（参数表靠它对齐）。"""
    from quant.ui.components import make_font

    return make_font(theme.FONT_SMALL, mono=True)
