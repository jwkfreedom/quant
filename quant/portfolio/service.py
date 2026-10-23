"""资产管理的业务逻辑：买卖、期初导入、现金存取、持仓估值、风险统计。

规则（与作者确认过）
--------------------
1. 成本用**移动加权平均**；买入手续费计入持仓成本，卖出手续费从卖出金额里扣。
2. 卖出数量不能超过持仓，否则抛 ValueError。
3. 现金是独立产品（每个币种一条），买卖会自动增减同币种现金。
4. 数量调整（adjust）用来录期初持仓或修正送股，直接设定目标数量与成本价。
5. 分红只统计，不自动入账；由界面/命令行手动「记入现金」。
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from quant.portfolio import schema, store

logger = logging.getLogger(__name__)

#: 金额与数量保留的小数位
PRECISION = 6


def _round(value: float) -> float:
    return round(float(value), PRECISION)


class Portfolio:
    """资产库的业务门面。持有一个 sqlite 连接。"""

    def __init__(self, conn):
        self.conn = conn

    # ------------------------------------------------------------------
    # 资产账户 / 资金账户
    # ------------------------------------------------------------------
    def create_owner(self, name: str, note: str = "") -> int:
        return store.create_owner(self.conn, name, note)

    def owners(self) -> list[dict]:
        return store.list_owners(self.conn)

    def add_account(self, owner_id: int, name: str, *, account_type: str = "securities",
                    currency: str = "CNY", note: str = "") -> int:
        """新建资金账户，并自动建好该币种的现金产品与零持仓。"""
        if currency not in schema.CURRENCIES:
            raise ValueError(f"不支持的币种: {currency}")
        account_id = store.create_account(
            self.conn, owner_id, name, account_type=account_type,
            currency=currency, note=note,
        )
        cash_id = store.cash_instrument(self.conn, currency)
        store.upsert_holding(self.conn, account_id, cash_id, quantity=0.0, cost_price=1.0)
        return account_id

    def accounts(self, owner_id: int | None = None) -> list[dict]:
        return store.list_accounts(self.conn, owner_id)

    def account_label(self, account_id: int) -> str:
        account = store.get_account(self.conn, account_id)
        if account is None:
            return f"#{account_id}"
        owner = store.get_owner(self.conn, account["owner_id"])
        prefix = f"{owner['name']} / " if owner else ""
        return f"{prefix}{account['name']}"

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _account_currency(self, account_id: int) -> str:
        account = store.get_account(self.conn, account_id)
        if account is None:
            raise ValueError(f"资金账户不存在: {account_id}")
        return account["currency"]

    def _cash_holding(self, account_id: int) -> tuple[int, float]:
        """返回 (现金产品 id, 现金余额)。"""
        currency = self._account_currency(account_id)
        cash_id = store.cash_instrument(self.conn, currency)
        holding = store.get_holding(self.conn, account_id, cash_id)
        return cash_id, (holding["quantity"] if holding else 0.0)

    def _move_cash(self, account_id: int, delta: float, *, trade_date: str,
                   action: str, note: str = "") -> float:
        """调整账户现金余额并写一条流水，返回调整后的余额。"""
        cash_id, balance = self._cash_holding(account_id)
        new_balance = _round(balance + delta)
        store.upsert_holding(self.conn, account_id, cash_id,
                             quantity=new_balance, cost_price=1.0)
        if action in (schema.ACTION_DEPOSIT, schema.ACTION_WITHDRAW,
                      schema.ACTION_DIVIDEND):
            store.add_txn(self.conn, account_id, cash_id, trade_date=trade_date,
                          action=action, quantity=abs(delta), price=1.0, note=note)
        return new_balance

    def _ensure_instrument(self, kind: str, market: str, symbol: str, name: str,
                           risk: str | None = None) -> dict:
        instrument_id = store.get_or_create_instrument(
            self.conn, kind, market, symbol, name=name, risk=risk,
        )
        instrument = store.get_instrument(self.conn, instrument_id)
        if name and instrument and not instrument["name"]:
            store.update_instrument(self.conn, instrument_id, name=name)
            instrument = store.get_instrument(self.conn, instrument_id)
        return instrument

    # ------------------------------------------------------------------
    # 买卖
    # ------------------------------------------------------------------
    def buy(self, account_id: int, *, kind: str, market: str, symbol: str,
            quantity: float, price: float, name: str = "", fee: float = 0.0,
            trade_date: str | None = None, note: str = "",
            risk: str | None = None) -> dict:
        """买入：加仓 + 扣现金。"""
        if quantity <= 0:
            raise ValueError("买入数量必须大于 0")
        if price < 0:
            raise ValueError("买入价格不能为负")
        trade_date = trade_date or store.today()
        instrument = self._ensure_instrument(kind, market, symbol, name, risk)

        holding = store.get_holding(self.conn, account_id, instrument["id"])
        old_qty = holding["quantity"] if holding else 0.0
        old_cost = holding["cost_price"] if holding else 0.0

        new_qty = _round(old_qty + quantity)
        # 买入费用计入成本
        total_cost = old_cost * old_qty + price * quantity + fee
        new_cost = _round(total_cost / new_qty) if new_qty else 0.0

        opened_at = holding["opened_at"] if holding and holding["opened_at"] else trade_date
        store.upsert_holding(self.conn, account_id, instrument["id"],
                             quantity=new_qty, cost_price=new_cost, opened_at=opened_at)
        store.add_txn(self.conn, account_id, instrument["id"], trade_date=trade_date,
                      action=schema.ACTION_BUY, quantity=quantity, price=price,
                      fee=fee, note=note)

        cash_after = self._move_cash(account_id, -(price * quantity + fee),
                                     trade_date=trade_date, action=schema.ACTION_BUY)
        warnings = []
        if cash_after < 0:
            warnings.append(f"买入后现金为负（{cash_after:,.2f}），请检查是否漏录了存入现金")
        return {
            "instrument_id": instrument["id"],
            "quantity": new_qty,
            "cost_price": new_cost,
            "cash": cash_after,
            "warnings": warnings,
        }

    def sell(self, account_id: int, *, kind: str, market: str, symbol: str,
             quantity: float, price: float, name: str = "", fee: float = 0.0,
             trade_date: str | None = None, note: str = "") -> dict:
        """卖出：减仓 + 加现金。数量不能超过持仓。"""
        if quantity <= 0:
            raise ValueError("卖出数量必须大于 0")
        trade_date = trade_date or store.today()
        instrument = self._ensure_instrument(kind, market, symbol, name)

        holding = store.get_holding(self.conn, account_id, instrument["id"])
        old_qty = holding["quantity"] if holding else 0.0
        if quantity > old_qty + 1e-9:
            raise ValueError(
                f"卖出数量 {quantity:g} 超过当前持有 {old_qty:g}（{symbol}），已拒绝"
            )

        old_cost = holding["cost_price"] if holding else 0.0
        realized = _round((price - old_cost) * quantity - fee)
        new_qty = _round(old_qty - quantity)

        if new_qty <= 1e-9:
            store.delete_holding(self.conn, account_id, instrument["id"])
            new_qty, new_cost = 0.0, 0.0
        else:
            # 移动加权平均：卖出不改变剩余持仓的成本价
            new_cost = old_cost
            store.upsert_holding(self.conn, account_id, instrument["id"],
                                 quantity=new_qty, cost_price=new_cost)

        store.add_txn(self.conn, account_id, instrument["id"], trade_date=trade_date,
                      action=schema.ACTION_SELL, quantity=quantity, price=price,
                      fee=fee, realized_pnl=realized, note=note)

        cash_after = self._move_cash(account_id, price * quantity - fee,
                                     trade_date=trade_date, action=schema.ACTION_SELL)
        return {
            "instrument_id": instrument["id"],
            "quantity": new_qty,
            "cost_price": new_cost,
            "realized_pnl": realized,
            "cash": cash_after,
            "warnings": [],
        }

    # ------------------------------------------------------------------
    # 数量调整（期初导入 / 送股修正）
    # ------------------------------------------------------------------
    def adjust(self, account_id: int, *, kind: str, market: str, symbol: str,
               quantity: float, cost_price: float = 0.0, name: str = "",
               trade_date: str | None = None, note: str = "",
               risk: str | None = None) -> dict:
        """把持仓数量直接设为目标值（不推荐用它代替买卖，只用于期初导入/修正）。"""
        if quantity < 0:
            raise ValueError("数量不能为负")
        if cost_price < 0:
            raise ValueError("成本价不能为负")
        trade_date = trade_date or store.today()
        instrument = self._ensure_instrument(kind, market, symbol, name, risk)

        holding = store.get_holding(self.conn, account_id, instrument["id"])
        old_qty = holding["quantity"] if holding else 0.0
        delta = _round(quantity - old_qty)

        if quantity <= 1e-9:
            store.delete_holding(self.conn, account_id, instrument["id"])
        else:
            store.upsert_holding(self.conn, account_id, instrument["id"],
                                 quantity=quantity, cost_price=cost_price,
                                 opened_at=trade_date)
        store.add_txn(self.conn, account_id, instrument["id"], trade_date=trade_date,
                      action=schema.ACTION_ADJUST, quantity=delta, price=cost_price, note=note)
        return {
            "instrument_id": instrument["id"],
            "quantity": _round(quantity),
            "cost_price": _round(cost_price),
            "delta": delta,
            "warnings": [],
        }

    # ------------------------------------------------------------------
    # 现金存取
    # ------------------------------------------------------------------
    def deposit(self, account_id: int, amount: float, *, trade_date: str | None = None,
                note: str = "") -> float:
        """存入现金，返回新余额。"""
        if amount <= 0:
            raise ValueError("存入金额必须大于 0")
        return self._move_cash(account_id, amount, trade_date=trade_date or store.today(),
                               action=schema.ACTION_DEPOSIT, note=note)

    def withdraw(self, account_id: int, amount: float, *, trade_date: str | None = None,
                 note: str = "") -> float:
        """取出资金，返回新余额（允许取到负数会给出警告但不阻止）。"""
        if amount <= 0:
            raise ValueError("取出金额必须大于 0")
        return self._move_cash(account_id, -amount, trade_date=trade_date or store.today(),
                               action=schema.ACTION_WITHDRAW, note=note)

    def record_dividend(self, account_id: int, amount: float, *,
                        trade_date: str | None = None, note: str = "") -> float:
        """把一笔分红记入账户现金（分红不会自动入账，必须显式调用）。"""
        if amount <= 0:
            raise ValueError("分红金额必须大于 0")
        return self._move_cash(account_id, amount, trade_date=trade_date or store.today(),
                               action=schema.ACTION_DIVIDEND, note=note)

    def cash_balance(self, account_id: int) -> float:
        return self._cash_holding(account_id)[1]

    # ------------------------------------------------------------------
    # 估值
    # ------------------------------------------------------------------
    def transaction_quantity(self, account_id: int, instrument_id: int,
                             as_of: str) -> float:
        """按流水重建某日收盘后的持仓数量（用于分红计算）。"""
        rows = self.conn.execute(
            f"SELECT action, quantity FROM {schema.TABLE_TXN} "
            f"WHERE account_id = ? AND instrument_id = ? AND trade_date <= ? "
            f"ORDER BY trade_date, id",
            (account_id, instrument_id, as_of),
        ).fetchall()
        total = 0.0
        for row in rows:
            action, quantity = row["action"], row["quantity"]
            if action in (schema.ACTION_BUY, schema.ACTION_ADJUST):
                total += quantity
            elif action == schema.ACTION_SELL:
                total -= quantity
        return _round(max(total, 0.0))

    def positions(self, *, owner_id: int | None = None, account_id: int | None = None,
                  prices: dict | None = None, as_of: str | None = None) -> pd.DataFrame:
        """持仓估值表。

        prices: 可选的 {(kind, market, symbol): (价格, 日期)} 覆盖表；
                未提供时用产品上保存的手动价/最近价。
        """
        rows = store.list_holdings(self.conn, account_id)
        if not rows:
            return pd.DataFrame(columns=[
                "account_id", "instrument_id", "account", "owner", "kind", "market",
                "symbol", "name", "currency", "risk", "quantity", "cost_price",
                "price", "price_date", "market_value", "cost_value", "pnl", "pnl_pct",
            ])

        accounts = {a["id"]: a for a in store.list_accounts(self.conn)}
        owners = {o["id"]: o for o in store.list_owners(self.conn)}
        prices = prices or {}

        records = []
        for row in rows:
            account = accounts.get(row["account_id"], {})
            if owner_id is not None and account.get("owner_id") != owner_id:
                continue
            owner = owners.get(account.get("owner_id"), {})

            price, price_date = self._resolve_price(row, prices, as_of)
            quantity = float(row["quantity"])
            cost_price = float(row["cost_price"])
            market_value = _round(quantity * price) if price is not None else None
            cost_value = _round(quantity * cost_price)
            pnl = _round(market_value - cost_value) if market_value is not None else None
            pnl_pct = (round((price / cost_price - 1) * 100, 2)
                       if price is not None and cost_price else None)

            records.append({
                "account_id": row["account_id"],
                "instrument_id": row["instrument_id"],
                "account": account.get("name", ""),
                "owner": owner.get("name", ""),
                "kind": row["kind"],
                "market": row["market"],
                "symbol": row["symbol"],
                "name": row["name"],
                "currency": row["currency"],
                "risk": row["risk"],
                "quantity": quantity,
                "cost_price": cost_price,
                "price": price,
                "price_date": price_date,
                "market_value": market_value,
                "cost_value": cost_value,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
            })
        return pd.DataFrame(records)

    def _resolve_price(self, row: dict, prices: dict, as_of: str | None):
        """按优先级取价：注入的价格 > 手动价 > 产品上保存的最新价 > 成本价兜底。"""
        key = (row["kind"], row["market"], row["symbol"])
        if key in prices:
            value = prices[key]
            if isinstance(value, (tuple, list)):
                return float(value[0]), value[1]
            return float(value), as_of

        if row["kind"] == schema.KIND_CASH:
            return 1.0, as_of

        if row["manual_price"] is not None:
            return float(row["manual_price"]), row["price_date"]

        # 拿不到价格时返回 None：宁可显示「缺价格」，也不要用成本价冒充现价
        return None, None

    # ------------------------------------------------------------------
    # 汇率折算
    # ------------------------------------------------------------------
    def to_base(self, value: float, currency: str, as_of: str | None = None) -> float:
        """折算成基准币种（人民币）。缺汇率时按 1:1 兜底并告警。"""
        if value is None or currency == schema.BASE_CURRENCY:
            return float(value or 0.0)
        try:
            rate = store.get_fx(self.conn, currency, as_of)
        except KeyError:
            logger.warning("缺少 %s 汇率，按 1:1 折算（结果会偏大/偏小）", currency)
            return float(value or 0.0)
        return float(value) * rate

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------
    def risk_breakdown(self, frame: pd.DataFrame | None = None, *,
                       owner_id: int | None = None, account_id: int | None = None,
                       as_of: str | None = None) -> pd.DataFrame:
        """按风险等级汇总市值与占比（折算成人民币）。

        缺价格的持仓不计入市值，单独在 missing 列里计数。
        """
        if frame is None:
            frame = self.positions(owner_id=owner_id, account_id=account_id, as_of=as_of)
        columns = ["risk", "risk_name", "value", "weight", "count", "missing"]
        if frame.empty:
            return pd.DataFrame(columns=columns)

        work = self._with_base_value(frame, as_of)
        valid = work[work["market_value"].notna()]
        total = float(valid["base_value"].sum())

        records = []
        for risk in schema.RISKS:
            subset = work[work["risk"] == risk]
            value = float(subset["base_value"].sum())
            priced = subset[subset["market_value"].notna()]
            records.append({
                "risk": risk,
                "risk_name": schema.RISK_NAMES[risk],
                "value": _round(value),
                "weight": round(value / total * 100, 2) if total > 0 else 0.0,
                "count": int(len(subset)),
                "missing": int(len(subset) - len(priced)),
            })
        return pd.DataFrame(records, columns=columns)

    def _with_base_value(self, frame: pd.DataFrame, as_of: str | None) -> pd.DataFrame:
        """给持仓表补上折算成人民币的市值/成本列。"""
        work = frame.copy()
        rates = {currency: self.to_base(1.0, currency, as_of)
                 for currency in work["currency"].unique()}
        work["fx"] = work["currency"].map(rates)
        work["base_value"] = work["market_value"] * work["fx"]
        work["base_cost"] = work["cost_value"] * work["fx"]
        return work

    def summary(self, *, owner_id: int | None = None, account_id: int | None = None,
                as_of: str | None = None, frame: pd.DataFrame | None = None) -> dict:
        """总资产 / 成本 / 浮盈 / 现金 / 分币种小计（全部折算成人民币）。"""
        if frame is None:
            frame = self.positions(owner_id=owner_id, account_id=account_id, as_of=as_of)

        result = {
            "total_value": 0.0, "total_cost": 0.0, "pnl": 0.0, "pnl_pct": 0.0,
            "cash_by_currency": {}, "by_currency": {}, "missing_price": 0,
            "negative_cash": [], "as_of": as_of or date.today().isoformat(),
        }
        if frame.empty:
            return result

        work = self._with_base_value(frame, as_of)
        priced = work[work["market_value"].notna()]

        total_value = float(priced["base_value"].sum())
        total_cost = float(priced["base_cost"].sum())
        pnl = round(total_value - total_cost, 2)

        by_currency: dict[str, dict] = {}
        for row in priced.itertuples():
            bucket = by_currency.setdefault(row.currency, {"value": 0.0, "cost": 0.0})
            bucket["value"] += float(row.base_value)
            bucket["cost"] += float(row.base_cost)

        cash_by_currency: dict[str, float] = {}
        negative_cash: list[str] = []
        for row in work.itertuples():
            if row.kind != schema.KIND_CASH:
                continue
            amount = round(float(row.quantity), 2)
            cash_by_currency[row.currency] = amount
            if amount < 0:
                negative_cash.append(f"{row.currency} 现金为负：{amount:,.2f}")

        result.update({
            "total_value": round(total_value, 2),
            "total_cost": round(total_cost, 2),
            "pnl": pnl,
            "pnl_pct": round(pnl / total_cost * 100, 2) if total_cost else 0.0,
            "cash_by_currency": cash_by_currency,
            "by_currency": {k: {"value": round(v["value"], 2), "cost": round(v["cost"], 2)}
                            for k, v in by_currency.items()},
            "missing_price": int(len(work) - len(priced)),
            "negative_cash": negative_cash,
        })
        return result
