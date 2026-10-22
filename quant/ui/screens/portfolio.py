"""P7 资产管理：账户 / 持仓 / 流水 / 分红。"""

from __future__ import annotations

import datetime

import pandas as pd
import wx

from quant.portfolio import schema as pschema
from quant.ui import charts, theme
from quant.ui import viewmodels as vm
from quant.ui.components import (Card, PageHeader, hint_label, make_button, make_notebook,
                                style_checkbox, style_input, text_label)
from quant.ui.theme import C
from quant.ui.widgets import (BusyRunner, DataFrameGrid, FigurePanel, MetricCards,
                             ask_save_path, error_dialog, relayout)

#: 账户下拉框里「全部」的位置
ALL_ACCOUNTS = "全部账户"


class TradeDialog(wx.Dialog):
    """买入 / 卖出 / 数量调整 / 现金存取的输入框。"""

    MODES = {
        "buy": "买入",
        "sell": "卖出",
        "adjust": "数量调整（期初导入）",
        "cash_in": "存入现金",
        "cash_out": "取出资金",
    }

    def __init__(self, parent, mode: str, *, account_label: str = "", currency: str = "CNY"):
        title = self.MODES.get(mode, "操作")
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.mode = mode
        self.SetBackgroundColour(wx.Colour(C.card))

        root = wx.BoxSizer(wx.VERTICAL)
        root.Add(text_label(self, f"{title}", size=theme.FONT_PAGE_TITLE, bold=True),
                 0, wx.LEFT | wx.TOP, theme.PAD)
        root.Add(hint_label(self, f"账户：{account_label}　币种：{currency}"),
                 0, wx.LEFT | wx.TOP | wx.BOTTOM, theme.PAD)
        root.AddSpacer(6)

        form = wx.FlexGridSizer(rows=0, cols=2, vgap=10, hgap=12)
        form.AddGrowableCol(1, 1)
        self.controls: dict[str, wx.Window] = {}
        self._captions: dict[str, wx.Window] = {}

        def add_row(name: str, label: str, control):
            caption = text_label(self, label, colour=C.text_secondary)
            form.Add(caption, 0, wx.ALIGN_CENTER_VERTICAL)
            form.Add(control, 0)
            self.controls[name] = control
            self._captions[name] = caption
            return caption

        kind_choice = style_input(wx.Choice(self, choices=["stock", "etf", "fund"]))
        kind_choice.SetStringSelection("stock")
        add_row("kind", "产品类型", kind_choice)
        self.kind_labels = {"stock": "股票", "etf": "场内基金", "fund": "场外基金"}

        market_choice = style_input(wx.Choice(self, choices=["CN", "HK", "US"]))
        market_choice.SetStringSelection("CN")
        add_row("market", "市场", market_choice)

        add_row("symbol", "代码", style_input(wx.TextCtrl(self, size=(160, -1)), width=160))
        add_row("name", "名称", style_input(wx.TextCtrl(self, size=(160, -1)), width=160))
        add_row("quantity", "数量", style_input(wx.TextCtrl(self, size=(160, -1)), width=160))
        add_row("price", "成交价", style_input(wx.TextCtrl(self, size=(160, -1)), width=160))
        add_row("fee", "手续费", style_input(wx.TextCtrl(self, size=(160, -1), value="0"), width=160))
        add_row("cost_price", "成本价", style_input(wx.TextCtrl(self, size=(160, -1)), width=160))
        add_row("amount", "金额", style_input(wx.TextCtrl(self, size=(160, -1)), width=160))

        today = datetime.date.today().isoformat()
        add_row("trade_date", "日期", style_input(wx.TextCtrl(self, value=today, size=(160, -1)),
                                                 width=160))
        add_row("note", "备注", style_input(wx.TextCtrl(self, size=(220, -1)), width=220))

        root.Add(form, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.PAD)
        root.AddSpacer(theme.PAD)

        buttons = wx.BoxSizer(wx.HORIZONTAL)
        buttons.AddStretchSpacer()
        buttons.Add(make_button(self, "取消", self._on_cancel), 0, wx.RIGHT, 8)
        buttons.Add(make_button(self, "确定", self._on_ok, primary=True), 0)
        root.Add(buttons, 0, wx.EXPAND | wx.ALL, theme.PAD)

        self.SetSizer(root)
        self._apply_mode()
        self.Fit()
        self.SetMinSize((420, 300))
        self.Centre()

    # ------------------------------------------------------------------
    def _show(self, name: str, visible: bool):
        control = self.controls.get(name)
        caption = self._captions.get(name)
        if control is not None:
            control.Show(visible)
        if caption is not None:
            caption.Show(visible)

    def _apply_mode(self):
        is_cash = self.mode in ("cash_in", "cash_out")
        for name in ("kind", "market", "symbol", "name", "quantity", "trade_date", "note"):
            self._show(name, not is_cash)
        for name in ("price", "fee"):
            self._show(name, (not is_cash) and self.mode in ("buy", "sell"))
        self._show("cost_price", (not is_cash) and self.mode == "adjust")
        self._show("amount", is_cash)
        self.Layout()

    def _on_cancel(self, _evt=None):
        self.EndModal(wx.ID_CANCEL)

    def _on_ok(self, _evt=None):
        try:
            self.collect()
        except ValueError as exc:
            wx.MessageBox(str(exc), "填写有误", wx.OK | wx.ICON_WARNING, self)
            return
        self.EndModal(wx.ID_OK)

    def collect(self) -> dict:
        """把界面上的值读成参数字典（顺便校验）。"""
        if self.mode in ("cash_in", "cash_out"):
            text = self.controls["amount"].GetValue().strip()
            if not text:
                raise ValueError("请填写金额")
            amount = float(text)
            if amount <= 0:
                raise ValueError("金额必须大于 0")
            return {"amount": amount,
                    "trade_date": self.controls["trade_date"].GetValue().strip() or None,
                    "note": self.controls["note"].GetValue().strip()}

        symbol = self.controls["symbol"].GetValue().strip()
        if not symbol:
            raise ValueError("请填写代码")
        try:
            quantity = float(self.controls["quantity"].GetValue().strip() or 0)
        except ValueError as exc:
            raise ValueError("数量必须是数字") from exc
        if quantity <= 0:
            raise ValueError("数量必须大于 0")

        data = {
            "kind": self.controls["kind"].GetStringSelection(),
            "market": self.controls["market"].GetStringSelection(),
            "symbol": symbol,
            "name": self.controls["name"].GetValue().strip(),
            "quantity": quantity,
            "trade_date": self.controls["trade_date"].GetValue().strip() or None,
            "note": self.controls["note"].GetValue().strip(),
        }
        if self.mode in ("buy", "sell"):
            try:
                data["price"] = float(self.controls["price"].GetValue().strip() or 0)
                data["fee"] = float(self.controls["fee"].GetValue().strip() or 0)
            except ValueError as exc:
                raise ValueError("价格和手续费必须是数字") from exc
            if data["price"] < 0:
                raise ValueError("价格不能为负")
        else:
            try:
                data["cost_price"] = float(self.controls["cost_price"].GetValue().strip() or 0)
            except ValueError as exc:
                raise ValueError("成本价必须是数字") from exc
        return data


class NewAccountDialog(wx.Dialog):
    """新建资产账户（人）或资金账户（券商）。"""

    def __init__(self, parent, mode: str, *, owners=None):
        from quant.portfolio import schema as pschema

        self.mode = mode
        title = "新建资产账户" if mode == "owner" else "新建资金账户"
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE)
        self.SetBackgroundColour(wx.Colour(C.card))

        root = wx.BoxSizer(wx.VERTICAL)
        root.Add(text_label(self, title, size=theme.FONT_PAGE_TITLE, bold=True),
                 0, wx.LEFT | wx.TOP, theme.PAD)
        hint = ("资产账户是「人」，例如：王大、李四"
                if mode == "owner"
                else "资金账户是某个人的一个券商/基金账户，例如：华泰证券、天天基金")
        root.Add(hint_label(self, hint), 0, wx.LEFT | wx.TOP | wx.BOTTOM, theme.PAD)
        root.AddSpacer(6)

        form = wx.FlexGridSizer(rows=0, cols=2, vgap=10, hgap=12)
        form.AddGrowableCol(1, 1)
        self.controls: dict[str, wx.Window] = {}

        def add_row(name: str, label: str, control):
            form.Add(text_label(self, label, colour=C.text_secondary), 0,
                     wx.ALIGN_CENTER_VERTICAL)
            form.Add(control, 0)
            self.controls[name] = control

        self._owners = list(owners or [])
        if mode == "account":
            owner_choice = style_input(wx.Choice(self, choices=self._owners or ["（无）"]))
            # 默认选中最后一个：通常是用户刚刚新建的那个
            owner_choice.SetSelection(max(len(self._owners) - 1, 0))
            add_row("owner", "所属资产账户", owner_choice)

        add_row("name", "名称",
                style_input(wx.TextCtrl(self, size=(220, -1), value=""), width=220))

        if mode == "account":
            type_choice = style_input(wx.Choice(
                self, choices=[pschema.ACCOUNT_TYPE_NAMES[t] for t in pschema.ACCOUNT_TYPES]))
            type_choice.SetSelection(0)
            add_row("account_type", "账户类型", type_choice)

            currency_choice = style_input(wx.Choice(
                self, choices=[f"{c} {pschema.CURRENCY_NAMES[c]}" for c in pschema.CURRENCIES]))
            currency_choice.SetSelection(0)
            add_row("currency", "结算币种", currency_choice)

        root.Add(form, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.PAD)
        root.AddSpacer(theme.PAD)

        buttons = wx.BoxSizer(wx.HORIZONTAL)
        buttons.AddStretchSpacer()
        buttons.Add(make_button(self, "取消", lambda _e: self.EndModal(wx.ID_CANCEL)),
                    0, wx.RIGHT, 8)
        buttons.Add(make_button(self, "创建", self._on_ok, primary=True), 0)
        root.Add(buttons, 0, wx.EXPAND | wx.ALL, theme.PAD)

        self.SetSizer(root)
        self.Fit()
        self.SetMinSize((440, 240))
        self.Centre()

    def _on_ok(self, _evt=None):
        try:
            self.collect()
        except ValueError as exc:
            wx.MessageBox(str(exc), "填写有误", wx.OK | wx.ICON_WARNING, self)
            return
        self.EndModal(wx.ID_OK)

    def collect(self) -> dict:
        from quant.portfolio import schema as pschema

        name = self.controls["name"].GetValue().strip()
        if not name:
            raise ValueError("名称不能为空")
        if self.mode == "owner":
            return {"name": name}

        index = self.controls["owner"].GetSelection()
        if index < 0 or index >= len(self._owners):
            raise ValueError("请选择所属资产账户")
        type_index = self.controls["account_type"].GetSelection()
        currency_index = self.controls["currency"].GetSelection()
        return {
            "name": name,
            "owner_index": index,
            "account_type": pschema.ACCOUNT_TYPES[max(type_index, 0)],
            "currency": pschema.CURRENCIES[max(currency_index, 0)],
        }


def _fmt_money(value, digits: int = 2) -> str:
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return "—"


class PortfolioPanel(wx.Panel):
    """资产管理页。"""

    def __init__(self, parent):
        super().__init__(parent)
        self.SetBackgroundColour(wx.Colour(C.bg))
        self.runner = BusyRunner(self)
        self._accounts: list[dict] = []
        self._owners: list[dict] = []
        self._dividend_frame = pd.DataFrame()
        self._flash: str | None = None

        root = wx.BoxSizer(wx.VERTICAL)
        self.header = PageHeader(
            self, "资产管理",
            subtitle="资产账户 → 资金账户 → 持仓；风险占比按市值（人民币）折算",
            actions=[("刷新价格与汇率", lambda _evt: self.on_refresh(), False),
                     ("刷新数据", lambda _evt: self.refresh(), True)],
        )
        root.Add(self.header, 0, wx.EXPAND | wx.ALL, theme.PAD)

        self.notebook = make_notebook(self)
        root.Add(self.notebook, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, theme.PAD)

        self._build_overview()
        self._build_positions()
        self._build_txns()
        self._build_dividends()

        self.SetSizer(root)
        self.refresh()

    # ------------------------------------------------------------------
    # 页面构建
    # ------------------------------------------------------------------
    def _new_page(self, title: str) -> wx.Panel:
        page = wx.Panel(self.notebook)
        page.SetBackgroundColour(wx.Colour(C.bg))
        self.notebook.AddPage(page, title)
        return page

    def _build_overview(self):
        page = self._new_page("总览")
        sizer = wx.BoxSizer(wx.VERTICAL)

        bar = wx.BoxSizer(wx.HORIZONTAL)
        bar.Add(make_button(page, "新建资产账户", lambda _evt: self.on_new_owner(),
                            primary=True), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        bar.Add(make_button(page, "新建资金账户", lambda _evt: self.on_new_account()),
                0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)
        bar.AddStretchSpacer()
        self.account_hint = hint_label(page, "")
        bar.Add(self.account_hint, 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(bar, 0, wx.EXPAND | wx.BOTTOM, 10)

        self.cards = MetricCards(page, columns=6)
        sizer.Add(self.cards, 0, wx.EXPAND | wx.BOTTOM, theme.GAP)

        row = wx.BoxSizer(wx.HORIZONTAL)

        account_card = Card(page, "资产账户", "资产账户 → 资金账户两级，含各账户现金")
        self.account_grid = DataFrameGrid(account_card.body)
        account_card.add(self.account_grid, 1, wx.EXPAND)
        row.Add(account_card, 1, wx.EXPAND | wx.RIGHT, theme.GAP)

        risk_card = Card(page, "风险占比", "高 / 中 / 低风险按市值折算")
        self.risk_figure = FigurePanel(risk_card.body)
        self.risk_figure.SetMinSize((-1, 250))
        risk_card.add(self.risk_figure, 1, wx.EXPAND)
        self.risk_grid = DataFrameGrid(risk_card.body)
        self.risk_grid.SetMinSize((-1, 140))
        risk_card.add(self.risk_grid, 0, wx.EXPAND | wx.TOP, 8)
        row.Add(risk_card, 1, wx.EXPAND)

        sizer.Add(row, 1, wx.EXPAND)
        page.SetSizer(sizer)

    def _build_positions(self):
        page = self._new_page("持仓")
        sizer = wx.BoxSizer(wx.VERTICAL)

        bar = wx.BoxSizer(wx.HORIZONTAL)
        bar.Add(text_label(page, "资金账户", colour=C.text_secondary), 0,
                wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.position_account = style_input(wx.Choice(page, choices=[ALL_ACCOUNTS]))
        self.position_account.SetSelection(0)
        self.position_account.Bind(wx.EVT_CHOICE, lambda _evt: self.render_positions())
        bar.Add(self.position_account, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 20)

        for label, mode, primary in (("买入", "buy", True), ("卖出", "sell", False),
                                     ("数量调整", "adjust", False),
                                     ("存入现金", "cash_in", False),
                                     ("取出资金", "cash_out", False)):
            button = make_button(page, label, lambda _evt, m=mode: self.on_trade(m),
                                 primary=primary)
            bar.Add(button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)

        bar.AddStretchSpacer()
        self.position_status = text_label(page, "", size=theme.FONT_SMALL,
                                          colour=C.text_secondary)
        bar.Add(self.position_status, 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(bar, 0, wx.EXPAND | wx.BOTTOM, 10)

        self.position_grid = DataFrameGrid(page)
        sizer.Add(self.position_grid, 1, wx.EXPAND)
        page.SetSizer(sizer)

    def _build_txns(self):
        page = self._new_page("流水")
        sizer = wx.BoxSizer(wx.VERTICAL)

        bar = wx.BoxSizer(wx.HORIZONTAL)
        bar.Add(text_label(page, "资金账户", colour=C.text_secondary), 0,
                wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.txn_account = style_input(wx.Choice(page, choices=[ALL_ACCOUNTS]))
        self.txn_account.SetSelection(0)
        self.txn_account.Bind(wx.EVT_CHOICE, lambda _evt: self.render_txns())
        bar.Add(self.txn_account, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 16)
        bar.Add(make_button(page, "导出", lambda _evt: self.on_export(self._txn_frame,
                                                                      "portfolio_txns.csv")),
                0, wx.ALIGN_CENTER_VERTICAL)
        bar.AddStretchSpacer()
        self.txn_status = text_label(page, "", size=theme.FONT_SMALL, colour=C.text_secondary)
        bar.Add(self.txn_status, 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(bar, 0, wx.EXPAND | wx.BOTTOM, 10)

        self._txn_frame = pd.DataFrame()
        self.txn_grid = DataFrameGrid(page)
        sizer.Add(self.txn_grid, 1, wx.EXPAND)
        page.SetSizer(sizer)

    def _build_dividends(self):
        page = self._new_page("分红")
        sizer = wx.BoxSizer(wx.VERTICAL)

        bar = wx.BoxSizer(wx.HORIZONTAL)
        bar.Add(text_label(page, "资金账户", colour=C.text_secondary), 0,
                wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.dividend_account = style_input(wx.Choice(page, choices=[ALL_ACCOUNTS]))
        self.dividend_account.SetSelection(0)
        self.dividend_account.Bind(wx.EVT_CHOICE, lambda _evt: self.render_dividends())
        bar.Add(self.dividend_account, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 16)

        bar.Add(text_label(page, "年度", colour=C.text_secondary), 0,
                wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.dividend_year = style_input(wx.Choice(page, choices=["全部"]))
        self.dividend_year.SetSelection(0)
        self.dividend_year.Bind(wx.EVT_CHOICE, lambda _evt: self.render_dividends())
        bar.Add(self.dividend_year, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 16)

        bar.Add(make_button(page, "拉取分红", lambda _evt: self.on_refresh_dividends()), 0,
                wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        bar.Add(make_button(page, "记入现金", lambda _evt: self.on_record_dividend()), 0,
                wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        bar.Add(make_button(page, "导出", lambda _evt: self.on_export(self._dividend_frame,
                                                                      "dividends.csv")), 0,
                wx.ALIGN_CENTER_VERTICAL)
        bar.AddStretchSpacer()
        sizer.Add(bar, 0, wx.EXPAND | wx.BOTTOM, 8)

        self.dividend_status = text_label(page, "", size=theme.FONT_CARD_TITLE, bold=True,
                                          colour=C.text)
        sizer.Add(self.dividend_status, 0, wx.BOTTOM, 8)

        self.dividend_grid = DataFrameGrid(page)
        self.dividend_grid.SetMinSize((-1, 200))
        sizer.Add(self.dividend_grid, 1, wx.EXPAND)
        page.SetSizer(sizer)

    # ------------------------------------------------------------------
    # 数据加载
    # ------------------------------------------------------------------
    def refresh(self):
        self.runner.run(self._load, self._render_all,
                        on_error=lambda exc: error_dialog(self, exc),
                        busy_message="读取资产数据…")

    def _load(self) -> dict:
        return {
            "owners": vm.portfolio_owners(),
            "accounts": vm.portfolio_accounts(),
            "positions": vm.portfolio_positions(),
            "summary": vm.portfolio_summary(),
            "risk": vm.portfolio_risk(),
            "txns": vm.portfolio_txns(limit=500),
            "years": vm.portfolio_years(),
        }

    def _render_all(self, data: dict):
        self._owners = data["owners"]
        self._accounts = data["accounts"]
        self._sync_account_choices()
        self._render_cards(data["summary"])
        self._update_account_hint()
        self._render_accounts(data)
        self._render_risk(data["risk"])
        self._txn_frame = data["txns"]
        self.render_positions(data["positions"])
        self.render_txns(data["txns"])
        self._sync_years(data["years"])
        self.render_dividends()
        relayout(self, self.notebook, self.notebook.GetCurrentPage())

    def _sync_account_choices(self):
        labels = [ALL_ACCOUNTS] + [a["label"] for a in self._accounts]
        for choice in (self.position_account, self.txn_account, self.dividend_account):
            previous = choice.GetStringSelection()
            choice.Set(labels)
            index = labels.index(previous) if previous in labels else 0
            choice.SetSelection(index)

    def _sync_years(self, years):
        labels = ["全部"] + [str(y) for y in years]
        previous = self.dividend_year.GetStringSelection()
        self.dividend_year.Set(labels)
        index = labels.index(previous) if previous in labels else 0
        self.dividend_year.SetSelection(index)

    def _selected_account_id(self, choice) -> int | None:
        label = choice.GetStringSelection()
        if not label or label == ALL_ACCOUNTS:
            return None
        for account in self._accounts:
            if account["label"] == label:
                return account["id"]
        return None

    # ------------------------------------------------------------------
    # 渲染
    # ------------------------------------------------------------------
    def _render_cards(self, summary: dict):
        pnl_colour = C.up if summary["pnl"] >= 0 else C.down
        items = [
            ("总资产", _fmt_money(summary["total_value"]), None),
            ("持仓成本", _fmt_money(summary["total_cost"]), None),
            ("浮动盈亏", _fmt_money(summary["pnl"]), pnl_colour),
            ("盈亏比例", f"{summary['pnl_pct']:+.2f}%", pnl_colour),
            ("现金合计",
             _fmt_money(sum(summary["cash_by_currency"].values())), None),
            ("缺价格", str(summary["missing_price"]),
             C.warn if summary["missing_price"] else C.text),
        ]
        self.cards.set_metrics(items)

        notes = []
        if summary["missing_price"]:
            notes.append(f"{summary['missing_price']} 个产品没有价格，未计入总资产")
        notes.extend(summary["negative_cash"])

        if self._flash:
            self.header.set_subtitle(self._flash)
            self._flash = None
        else:
            self.header.set_subtitle(
                "　".join(notes) if notes
                else "资产账户 → 资金账户 → 持仓；风险占比按市值（人民币）折算"
            )

    def _update_account_hint(self):
        if not self._owners:
            self.account_hint.SetLabel("还没有账户：先点「新建资产账户」，再点「新建资金账户」")
        elif not any(owner["accounts"] for owner in self._owners):
            self.account_hint.SetLabel("已有资产账户，接着点「新建资金账户」")
        else:
            total = sum(len(owner["accounts"]) for owner in self._owners)
            self.account_hint.SetLabel(f"{len(self._owners)} 个资产账户 / {total} 个资金账户")

    def _render_accounts(self, data: dict):
        positions = data["positions"]
        values = {}
        counts = {}
        if positions is not None and not positions.empty:
            for row in positions.itertuples():
                if row.market_value is None or pd.isna(row.market_value):
                    continue
                values[row.account_id] = values.get(row.account_id, 0.0) + float(row.market_value)
                counts[row.account_id] = counts.get(row.account_id, 0) + 1

        rows = []
        for owner in data["owners"]:
            if not owner["accounts"]:
                # 只建了资产账户、还没建资金账户：也必须显示出来，
                # 否则新建完看起来像"没建成"
                rows.append({
                    "资产账户": owner["name"],
                    "资金账户": "（还没有资金账户）",
                    "币种": "",
                    "现金": 0.0,
                    "持仓市值": 0.0,
                    "持仓数": 0,
                })
                continue
            for account in owner["accounts"]:
                rows.append({
                    "资产账户": owner["name"],
                    "资金账户": account["name"],
                    "币种": account["currency"],
                    "现金": round(account["cash"], 2),
                    "持仓市值": round(values.get(account["id"], 0.0), 2),
                    "持仓数": counts.get(account["id"], 0),
                })
        frame = pd.DataFrame(rows)
        self.account_grid.SetDataFrame(frame)

    def _render_risk(self, table: pd.DataFrame):
        try:
            self.risk_figure.set_figure(charts.risk_pie_figure(table))
        except Exception as exc:  # pragma: no cover
            error_dialog(self, exc)
        display = table.copy()
        display["risk_name"] = [pschema.RISK_NAMES.get(r, r) for r in display["risk"]]
        self.risk_grid.SetDataFrame(display[["risk_name", "value", "weight", "count", "missing"]],
                                    display_names=True)

    def render_positions(self, frame: pd.DataFrame | None = None):
        account_id = self._selected_account_id(self.position_account)
        if frame is None:
            try:
                frame = vm.portfolio_positions(account_id=account_id)
            except Exception as exc:  # pragma: no cover
                error_dialog(self, exc)
                return
        elif account_id is not None:
            frame = frame[frame["account_id"] == account_id]

        display = vm.portfolio_display(frame) if not frame.empty else frame
        self.position_grid.SetDataFrame(display)
        if frame is None or frame.empty:
            self.position_status.SetLabel("还没有持仓，用「买入」或「数量调整」录入")
        else:
            total = 0.0
            for row in frame.itertuples():
                if row.market_value is not None and not pd.isna(row.market_value):
                    total += float(row.market_value)
            self.position_status.SetLabel(f"{len(frame)} 个持仓　市值合计 {total:,.2f}")

    def render_txns(self, frame: pd.DataFrame | None = None):
        account_id = self._selected_account_id(self.txn_account)
        if frame is None:
            try:
                frame = vm.portfolio_txns(account_id=account_id, limit=500)
            except Exception as exc:  # pragma: no cover
                error_dialog(self, exc)
                return
        elif account_id is not None:
            frame = frame[frame["account_id"] == account_id]

        self._txn_frame = frame
        if frame is None or frame.empty:
            self.txn_grid.SetDataFrame(pd.DataFrame())
            self.txn_status.SetLabel("还没有交易记录")
            return
        display = frame.copy()
        display["action"] = [pschema.ACTION_NAMES.get(a, a) for a in display["action"]]
        display = vm.portfolio_display(display)
        self.txn_grid.SetDataFrame(display)
        self.txn_status.SetLabel(f"共 {len(frame)} 条")

    def render_dividends(self):
        account_id = self._selected_account_id(self.dividend_account)
        year_text = self.dividend_year.GetStringSelection()
        year = int(year_text) if year_text.isdigit() else None
        try:
            frame, summary = vm.portfolio_dividends(account_id=account_id, year=year)
        except Exception as exc:  # pragma: no cover
            error_dialog(self, exc)
            return

        self._dividend_frame = frame
        scope = f"{year} 年" if year else "全部"
        self.dividend_status.SetLabel(
            f"{scope}分红合计 {summary['total']:,.2f} 元（共 {summary['count']} 笔）"
        )
        if frame is None or frame.empty:
            self.dividend_grid.SetDataFrame(pd.DataFrame())
            return
        display = frame.copy()
        display["recorded"] = ["是" if v else "否" for v in display["recorded"]]
        display = vm.portfolio_display(display)
        self.dividend_grid.SetDataFrame(display)

    # ------------------------------------------------------------------
    # 操作
    # ------------------------------------------------------------------
    def on_refresh(self):
        """刷新价格与汇率，过程中把进度写到副标题上。"""

        frame = wx.GetTopLevelParent(self)

        def report(done: int, total: int, label: str):
            text = f"刷新中 {done}/{total}：{label}" if total else label
            wx.CallAfter(self.header.set_subtitle, text)
            if hasattr(frame, "set_status"):
                wx.CallAfter(frame.set_status, text)

        self.runner.run(lambda: vm.portfolio_refresh(progress=report),
                        self._after_refresh,
                        on_error=lambda exc: error_dialog(self, exc),
                        busy_message="刷新价格与汇率…（联网，可能需要几十秒）")

    def _after_refresh(self, result: dict):
        message = [f"价格更新 {result['updated']}/{result.get('total', result['updated'])} 个"]
        if result.get("skipped"):
            message.append(f"跳过 {result['skipped']} 个现金")
        fx = result.get("fx") or {}
        if fx:
            message.append("汇率 " + "、".join(f"{k} {v} 天" for k, v in fx.items()))
        if result["failed"]:
            message.append("失败：" + "、".join(result["failed"]))
        self._flash = "　".join(message)
        self.refresh()

    def on_refresh_dividends(self):
        self.runner.run(lambda: vm.portfolio_refresh_dividends(),
                        lambda result: self._after_dividend_refresh(result),
                        on_error=lambda exc: error_dialog(self, exc),
                        busy_message="拉取分红数据…（联网）")

    def _after_dividend_refresh(self, result: dict):
        text = f"写入/更新 {result['saved']} 条分红"
        if result["failed"]:
            text += "；未取到：" + "、".join(result["failed"][:6])
        wx.MessageBox(text, "分红拉取完成", wx.OK | wx.ICON_INFORMATION, self)
        self._sync_years(vm.portfolio_years())
        self.render_dividends()

    # ------------------------------------------------------------------
    # 新建账户
    # ------------------------------------------------------------------
    def on_new_owner(self):
        dialog = NewAccountDialog(self, "owner")
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            values = dialog.collect()
        except ValueError as exc:
            error_dialog(self, exc)
            return
        finally:
            dialog.Destroy()

        self.runner.run(
            lambda: vm.portfolio_add_owner(values["name"]),
            lambda _owner_id: self._after_new_account(f"已新建资产账户「{values['name']}」"),
            on_error=lambda exc: error_dialog(self, exc),
            busy_message="创建中…",
        )

    def on_new_account(self):
        if not self._owners:
            wx.MessageBox("请先新建一个资产账户（人）", "提示",
                          wx.OK | wx.ICON_INFORMATION, self)
            return

        dialog = NewAccountDialog(self, "account",
                                  owners=[owner["name"] for owner in self._owners])
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            values = dialog.collect()
        except ValueError as exc:
            error_dialog(self, exc)
            return
        finally:
            dialog.Destroy()

        owner = self._owners[values["owner_index"]]
        name, account_type, currency = (values["name"], values["account_type"],
                                        values["currency"])
        self.runner.run(
            lambda: vm.portfolio_add_account(owner["id"], name, account_type=account_type,
                                             currency=currency),
            lambda _account_id: self._after_new_account(
                f"已新建资金账户「{owner['name']} / {name}」（{currency}）"),
            on_error=lambda exc: error_dialog(self, exc),
            busy_message="创建中…",
        )

    def _after_new_account(self, message: str):
        # 先记下来，等 refresh 的渲染完成后由 _render_cards 显示，
        # 否则会被刷新流程里的副标题覆盖掉，用户看不到任何反馈
        self._flash = message
        self.refresh()

    def on_trade(self, mode: str):
        account_id = self._selected_account_id(self.position_account)
        if account_id is None:
            wx.MessageBox("请先在上方选择「资金账户」", "提示", wx.OK | wx.ICON_INFORMATION, self)
            return
        account = next((a for a in self._accounts if a["id"] == account_id), None)
        if account is None:
            return

        dialog = TradeDialog(self, mode, account_label=account["label"],
                             currency=account["currency"])
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            values = dialog.collect()
        except ValueError as exc:
            error_dialog(self, exc)
            return
        finally:
            dialog.Destroy()

        self._submit_trade(mode, account_id, values)

    def _submit_trade(self, mode: str, account_id: int, values: dict):
        def work():
            if mode == "buy":
                return vm.portfolio_buy(account_id, **values)
            if mode == "sell":
                return vm.portfolio_sell(account_id, **values)
            if mode == "adjust":
                return vm.portfolio_adjust(account_id, **values)
            return vm.portfolio_cash_move(account_id, values["amount"],
                                          deposit=(mode == "cash_in"),
                                          trade_date=values.get("trade_date"),
                                          note=values.get("note", ""))

        def done(result):
            for warning in (result.get("warnings", []) if isinstance(result, dict) else []):
                wx.MessageBox(warning, "提示", wx.OK | wx.ICON_WARNING, self)
            self.refresh()

        self.runner.run(work, done, on_error=lambda exc: error_dialog(self, exc),
                        busy_message="提交中…")

    def on_record_dividend(self):
        row = self.dividend_grid.selected_row()
        if not row:
            wx.MessageBox("请先在表格里选中一行分红", "提示", wx.OK | wx.ICON_INFORMATION, self)
            return
        record_id = None
        for key, value in row.items():
            if key in ("id", "序号"):
                record_id = int(value)
                break
        if record_id is None:
            wx.MessageBox("这一行没有分红编号，无法入账", "提示", wx.OK | wx.ICON_WARNING, self)
            return

        account_id = None
        for key, value in row.items():
            if key in ("account_id", "资金账户_id"):
                account_id = int(value)
                break
        if account_id is None:
            account_id = self._selected_account_id(self.dividend_account)
        if account_id is None:
            wx.MessageBox("请先选择资金账户", "提示", wx.OK | wx.ICON_INFORMATION, self)
            return

        if wx.MessageBox("把这笔分红记入该账户现金？", "确认",
                         wx.YES_NO | wx.ICON_QUESTION, self) != wx.YES:
            return

        self.runner.run(
            lambda: vm.portfolio_record_dividend(record_id, account_id),
            lambda balance: self._after_record(balance),
            on_error=lambda exc: error_dialog(self, exc),
            busy_message="入账中…",
        )

    def _after_record(self, balance):
        wx.MessageBox(f"已记入现金，当前余额 {balance:,.2f}", "完成",
                      wx.OK | wx.ICON_INFORMATION, self)
        self.refresh()

    def on_export(self, frame: pd.DataFrame, default_name: str):
        if frame is None or frame.empty:
            wx.MessageBox("没有数据可导出", "提示", wx.OK | wx.ICON_INFORMATION, self)
            return
        path = ask_save_path(self, default_name=default_name)
        if not path:
            return
        try:
            saved = vm.export_frame(frame, path)
            wx.MessageBox(f"已导出 {saved}", "完成", wx.OK | wx.ICON_INFORMATION, self)
        except Exception as exc:
            error_dialog(self, exc)
