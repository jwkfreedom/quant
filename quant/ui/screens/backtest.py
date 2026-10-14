"""P4 策略回测：参数表单 + 结果卡 + 净值曲线 + 成交明细。"""

from __future__ import annotations

import wx

from quant.ui import charts, viewmodels as vm
from quant.ui.widgets import BusyRunner, DataFrameGrid, FigurePanel, MetricCards, ask_save_path, error_dialog

RANGE_CHOICES = ["2010-01-01", "2015-01-01", "2018-01-01", "2020-01-01", "2022-01-01"]


class BacktestPanel(wx.Panel):
    """策略回测页。"""

    def __init__(self, parent):
        super().__init__(parent)
        self.runner = BusyRunner(self)
        self.result = None
        self._last_strategy: str | None = None
        self.param_controls: dict[str, wx.TextCtrl] = {}

        root = wx.BoxSizer(wx.HORIZONTAL)

        # ---------------- 左侧参数 ----------------
        # 注意：StaticBoxSizer 的父窗口必须与 SetSizer 的面板一致，
        # 内部控件的父窗口也要是同一个面板，否则 wx 会断言失败。
        left_panel = wx.Panel(self)
        left = wx.StaticBoxSizer(wx.VERTICAL, left_panel, "回测设置")
        form = wx.FlexGridSizer(rows=0, cols=2, vgap=6, hgap=8)

        form.Add(wx.StaticText(left_panel, label="策略"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.strategy_choice = wx.Choice(
            left_panel, choices=[info.name for info in vm.list_backtest_strategies()])
        self.strategy_choice.SetSelection(0)
        self.strategy_choice.Bind(wx.EVT_CHOICE, lambda _evt: self.on_strategy_changed())
        form.Add(self.strategy_choice, 0)

        form.Add(wx.StaticText(left_panel, label="标的代码"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.symbol_input = wx.TextCtrl(left_panel, size=(110, -1))
        form.Add(self.symbol_input, 0)

        form.Add(wx.StaticText(left_panel, label="起始日期"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.start_choice = wx.ComboBox(left_panel, choices=RANGE_CHOICES, value="2018-01-01")
        form.Add(self.start_choice, 0)

        form.Add(wx.StaticText(left_panel, label="初始资金"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.cash_input = wx.TextCtrl(left_panel, size=(110, -1), value="100000")
        form.Add(self.cash_input, 0)

        form.Add(wx.StaticText(left_panel, label="手续费率"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.commission_input = wx.TextCtrl(left_panel, size=(110, -1), value="0.001")
        form.Add(self.commission_input, 0)

        left.Add(form, 0, wx.EXPAND | wx.ALL, 8)

        caption = wx.StaticText(left_panel, label="▼ 策略参数")
        font = caption.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        caption.SetFont(font)
        left.Add(caption, 0, wx.ALL, 6)

        self.params_sizer = wx.FlexGridSizer(rows=0, cols=2, vgap=6, hgap=8)
        left.Add(self.params_sizer, 0, wx.EXPAND | wx.ALL, 8)

        run_button = wx.Button(left_panel, label="运行回测")
        run_button.Bind(wx.EVT_BUTTON, lambda _evt: self.on_run())
        left.Add(run_button, 0, wx.ALL, 8)

        export_button = wx.Button(left_panel, label="导出成交明细")
        export_button.Bind(wx.EVT_BUTTON, lambda _evt: self.on_export())
        left.Add(export_button, 0, wx.ALL, 8)

        self._left_panel = left_panel
        left_panel.SetSizer(left)
        left_panel.SetMinSize((320, -1))
        root.Add(left_panel, 0, wx.EXPAND | wx.ALL, 6)

        # ---------------- 右侧结果 ----------------
        right = wx.BoxSizer(wx.VERTICAL)
        self.notebook = wx.Notebook(self)

        # --- 页签 1：单次回测结果 ---
        result_page = wx.Panel(self.notebook)
        result_sizer = wx.BoxSizer(wx.VERTICAL)
        self.cards = MetricCards(result_page, columns=4)
        result_sizer.Add(self.cards, 0, wx.EXPAND | wx.ALL, 6)

        self.figure_panel = FigurePanel(result_page)
        self.figure_panel.SetMinSize((-1, 240))
        result_sizer.Add(self.figure_panel, 1, wx.EXPAND | wx.ALL, 6)

        self.grid = DataFrameGrid(result_page)
        self.grid.SetMinSize((-1, 150))
        result_sizer.Add(self.grid, 1, wx.EXPAND | wx.ALL, 6)
        result_page.SetSizer(result_sizer)
        self.notebook.AddPage(result_page, "回测结果")

        # --- 页签 2：参数扫描 ---
        sweep_page = wx.Panel(self.notebook)
        sweep_sizer = wx.BoxSizer(wx.VERTICAL)

        sweep_controls = wx.BoxSizer(wx.HORIZONTAL)
        sweep_controls.Add(wx.StaticText(sweep_page, label="参数"), 0,
                           wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
        self.sweep_param = wx.Choice(sweep_page, choices=[])
        sweep_controls.Add(self.sweep_param, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)

        self.sweep_start = wx.TextCtrl(sweep_page, size=(70, -1))
        self.sweep_stop = wx.TextCtrl(sweep_page, size=(70, -1))
        self.sweep_step = wx.TextCtrl(sweep_page, size=(70, -1))
        for label, control, hint in (("从", self.sweep_start, "起始值"),
                                     ("到", self.sweep_stop, "结束值"),
                                     ("步长", self.sweep_step, "步长")):
            sweep_controls.Add(wx.StaticText(sweep_page, label=label), 0,
                               wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 6)
            control.SetHint(hint)
            sweep_controls.Add(control, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 2)

        sweep_button = wx.Button(sweep_page, label="开始扫描")
        sweep_button.Bind(wx.EVT_BUTTON, lambda _evt: self.on_sweep())
        sweep_controls.Add(sweep_button, 0, wx.ALL, 6)

        self.sweep_status = wx.StaticText(sweep_page, label="")
        self.sweep_status.SetForegroundColour(wx.Colour(110, 110, 110))
        sweep_controls.Add(self.sweep_status, 1, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 8)
        sweep_sizer.Add(sweep_controls, 0, wx.EXPAND | wx.ALL, 4)

        self.sweep_figure_panel = FigurePanel(sweep_page)
        self.sweep_figure_panel.SetMinSize((-1, 260))
        sweep_sizer.Add(self.sweep_figure_panel, 1, wx.EXPAND | wx.ALL, 6)

        self.sweep_grid = DataFrameGrid(sweep_page)
        self.sweep_grid.SetMinSize((-1, 140))
        sweep_sizer.Add(self.sweep_grid, 1, wx.EXPAND | wx.ALL, 6)
        sweep_page.SetSizer(sweep_sizer)
        self.notebook.AddPage(sweep_page, "参数扫描")

        right.Add(self.notebook, 1, wx.EXPAND)
        root.Add(right, 1, wx.EXPAND | wx.ALL, 6)
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

        # 参数扫描的可选参数跟着策略走
        if hasattr(self, "sweep_param"):
            self.sweep_param.Set([p["name"] for p in info.params])
            if info.params:
                self.sweep_param.SetSelection(0)
                self._fill_sweep_defaults(info.params[0])

        self.params_sizer.Clear(delete_windows=True)
        self.param_controls.clear()
        for param in info.params:
            label = wx.StaticText(self._left_panel, label=param.get("label", param["name"]))
            label.SetToolTip(param.get("help", ""))
            control = wx.TextCtrl(self._left_panel, size=(110, -1),
                                  value=str(param.get("default", "")))
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
             (198, 40, 40) if result.return_pct >= 0 else (46, 125, 50)),
            ("年化收益", f"{result.annual_return:.2f}%", None),
            ("夏普比率", f"{result.sharpe:.2f}", None),
            ("最大回撤", f"{result.max_drawdown_pct:.2f}%", (198, 40, 50)),
            ("交易次数", str(result.trades), None),
            ("胜率", f"{result.win_rate:.1f}%", None),
            ("最终市值", f"{result.final_value:,.0f}", None),
            ("区间", f"{result.start} ~ {result.end}", None),
        ])
        try:
            self.figure_panel.set_figure(charts.equity_figure(result))
        except Exception as exc:  # pragma: no cover
            error_dialog(self, exc)
        self.grid.SetDataFrame(__import__("pandas").DataFrame(result.trade_list),
                               display_names=True)
        self.Layout()

    def on_export(self):
        if self.result is None or not self.result.trade_list:
            wx.MessageBox("还没有成交记录", "提示", wx.OK | wx.ICON_INFORMATION, self)
            return
        import pandas as pd

        path = ask_save_path(self, default_name=f"trades_{self.result.symbol}.csv")
        if not path:
            return
        try:
            wx.MessageBox(f"已导出 {vm.export_frame(pd.DataFrame(self.result.trade_list), path, display_names=True)}",
                          "完成", wx.OK | wx.ICON_INFORMATION, self)
        except Exception as exc:
            error_dialog(self, exc)
