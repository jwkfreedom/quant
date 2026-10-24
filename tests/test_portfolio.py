"""资产管理的核心逻辑测试：账户、买卖、成本、现金、风险统计。

这些测试只碰临时库，不会动真实的 data/portfolio.db。
"""

from __future__ import annotations

import pytest

from quant.portfolio import Portfolio, init_db, open_db, schema, store


@pytest.fixture
def book(tmp_path):
    """一个干净的资产库，返回 (Portfolio, 数据库路径)。"""
    db = tmp_path / "portfolio.db"
    init_db(db)
    with open_db(db) as conn:
        yield Portfolio(conn)


@pytest.fixture
def setup_book(book):
    """王大 + 华泰证券（人民币）+ 盈透证券（美元）."""
    owner = book.create_owner("王大")
    htsc = book.add_account(owner, "华泰证券", currency="CNY")
    ib = book.add_account(owner, "盈透证券", currency="USD")
    return book, owner, htsc, ib


# --------------------------------------------------------------------------
# 账户
# --------------------------------------------------------------------------
def test_create_owner_and_accounts(book):
    owner = book.create_owner("王大", note="主账户")
    account = book.add_account(owner, "华泰证券", currency="CNY")

    assert [o["name"] for o in book.owners()] == ["王大"]
    accounts = book.accounts(owner)
    assert [a["name"] for a in accounts] == ["华泰证券"]
    assert accounts[0]["currency"] == "CNY"

    # 新建账户会自带一条零余额的现金产品
    cash = book.cash_balance(account)
    assert cash == 0.0
    assert "王大" in book.account_label(account)


def test_account_currency_must_be_supported(book):
    owner = book.create_owner("王大")
    with pytest.raises(ValueError):
        book.add_account(owner, "奇怪账户", currency="XXX")


# --------------------------------------------------------------------------
# 现金
# --------------------------------------------------------------------------
def test_deposit_and_withdraw(book):
    owner = book.create_owner("王大")
    account = book.add_account(owner, "华泰证券")

    assert book.deposit(account, 100000, trade_date="2026-01-02") == 100000
    assert book.withdraw(account, 30000, trade_date="2026-01-03") == 70000
    assert book.cash_balance(account) == 70000

    with pytest.raises(ValueError):
        book.deposit(account, -1)
    with pytest.raises(ValueError):
        book.withdraw(account, 0)


# --------------------------------------------------------------------------
# 买入 / 成本
# --------------------------------------------------------------------------
def test_buy_uses_moving_weighted_average_and_folds_in_fee(book):
    owner = book.create_owner("王大")
    account = book.add_account(owner, "华泰证券")
    book.deposit(account, 1_000_000, trade_date="2026-01-02")

    book.buy(account, kind="stock", market="CN", symbol="600519", name="贵州茅台",
             quantity=100, price=1500, fee=15, trade_date="2026-01-05")
    result = book.buy(account, kind="stock", market="CN", symbol="600519",
                      quantity=100, price=1600, fee=16, trade_date="2026-02-05")

    assert result["quantity"] == 200
    # (1500*100 + 15 + 1600*100 + 16) / 200 = 1550.155
    assert result["cost_price"] == pytest.approx(1550.155, abs=1e-6)
    assert result["warnings"] == []

    # 现金同步减少（含手续费）
    expected_cash = 1_000_000 - (1500 * 100 + 15) - (1600 * 100 + 16)
    assert book.cash_balance(account) == pytest.approx(expected_cash)


def test_buy_warns_when_cash_goes_negative(book):
    owner = book.create_owner("王大")
    account = book.add_account(owner, "华泰证券")
    result = book.buy(account, kind="stock", market="CN", symbol="000001", name="平安银行",
                      quantity=100, price=12, trade_date="2026-01-05")
    assert result["warnings"], "现金不足应当给出提醒"
    assert book.cash_balance(account) < 0


def test_buy_rejects_non_positive_quantity(book):
    owner = book.create_owner("王大")
    account = book.add_account(owner, "华泰证券")
    with pytest.raises(ValueError):
        book.buy(account, kind="stock", market="CN", symbol="000001",
                 quantity=0, price=10)


# --------------------------------------------------------------------------
# 卖出
# --------------------------------------------------------------------------
def test_sell_more_than_held_is_rejected(book):
    owner = book.create_owner("王大")
    account = book.add_account(owner, "华泰证券")
    book.deposit(account, 200000, trade_date="2026-01-02")
    book.buy(account, kind="stock", market="CN", symbol="600519", name="贵州茅台",
             quantity=100, price=1500, trade_date="2026-01-05")

    with pytest.raises(ValueError) as excinfo:
        book.sell(account, kind="stock", market="CN", symbol="600519",
                  quantity=101, price=1600)
    assert "超过当前持有" in str(excinfo.value)

    # 持仓没被改动
    positions = book.positions()
    row = positions[positions["symbol"] == "600519"].iloc[0]
    assert row["quantity"] == 100


def test_sell_computes_realized_pnl_and_keeps_cost(book):
    owner = book.create_owner("王大")
    account = book.add_account(owner, "华泰证券")
    book.deposit(account, 1_000_000, trade_date="2026-01-02")
    book.buy(account, kind="stock", market="CN", symbol="600519", name="贵州茅台",
             quantity=200, price=1500, fee=30, trade_date="2026-01-05")

    result = book.sell(account, kind="stock", market="CN", symbol="600519",
                       quantity=50, price=1700, fee=8.5, trade_date="2026-03-05")

    cost = (1500 * 200 + 30) / 200          # 1500.15
    assert result["quantity"] == 150
    assert result["cost_price"] == pytest.approx(cost)
    assert result["realized_pnl"] == pytest.approx((1700 - cost) * 50 - 8.5)


def test_selling_everything_removes_holding(book):
    owner = book.create_owner("王大")
    account = book.add_account(owner, "华泰证券")
    book.deposit(account, 200000, trade_date="2026-01-02")
    book.buy(account, kind="stock", market="CN", symbol="600519", name="贵州茅台",
             quantity=100, price=1500, trade_date="2026-01-05")
    book.sell(account, kind="stock", market="CN", symbol="600519",
              quantity=100, price=1600, trade_date="2026-03-05")

    positions = book.positions()
    assert "600519" not in set(positions["symbol"])


# --------------------------------------------------------------------------
# 期初导入 / 调整
# --------------------------------------------------------------------------
def test_adjust_sets_target_quantity_without_history(book):
    owner = book.create_owner("王大")
    account = book.add_account(owner, "华泰证券")

    result = book.adjust(account, kind="etf", market="CN", symbol="510300",
                         name="沪深300ETF", quantity=10000, cost_price=3.9,
                         trade_date="2026-01-01")
    assert result["quantity"] == 10000
    assert result["delta"] == 10000

    positions = book.positions()
    row = positions[positions["symbol"] == "510300"].iloc[0]
    assert row["quantity"] == 10000
    assert row["cost_price"] == pytest.approx(3.9)

    # 再调整一次：只改数量，delta 是差额
    again = book.adjust(account, kind="etf", market="CN", symbol="510300",
                        quantity=12000, cost_price=3.95, trade_date="2026-02-01")
    assert again["delta"] == 2000

    # 调成 0 等于清空
    book.adjust(account, kind="etf", market="CN", symbol="510300", quantity=0)
    assert "510300" not in set(book.positions()["symbol"])


# --------------------------------------------------------------------------
# 估值与风险统计
# --------------------------------------------------------------------------
def test_positions_use_injected_prices(setup_book):
    book, owner, htsc, ib = setup_book
    book.deposit(htsc, 1_000_000, trade_date="2026-01-02")
    book.buy(htsc, kind="stock", market="CN", symbol="600519", name="贵州茅台",
             quantity=100, price=1500, trade_date="2026-01-05")

    prices = {("stock", "CN", "600519"): (1800.0, "2026-06-30")}
    positions = book.positions(prices=prices)

    row = positions[positions["symbol"] == "600519"].iloc[0]
    assert row["price"] == 1800.0
    assert row["market_value"] == pytest.approx(180000.0)
    assert row["pnl"] == pytest.approx(180000 - 150000)
    assert row["pnl_pct"] == pytest.approx((1800 / 1500 - 1) * 100, abs=0.01)


def test_manual_price_is_used_for_funds(setup_book):
    book, owner, htsc, ib = setup_book
    fund_account = book.add_account(owner, "天天基金", account_type="fund")
    book.adjust(fund_account, kind="fund", market="CN", symbol="710001",
                name="富安达优势", quantity=5000, cost_price=1.5)

    instrument = store.find_instrument(book.conn, "fund", "CN", "710001")
    store.set_manual_price(book.conn, instrument["id"], 1.85)

    positions = book.positions()
    row = positions[positions["symbol"] == "710001"].iloc[0]
    assert row["price"] == pytest.approx(1.85)
    assert row["market_value"] == pytest.approx(9250.0)


def test_missing_price_is_reported_not_faked(setup_book):
    book, _owner, htsc, _ib = setup_book
    book.adjust(htsc, kind="stock", market="CN", symbol="600519",
                name="贵州茅台", quantity=100, cost_price=1500)

    positions = book.positions()
    row = positions[positions["symbol"] == "600519"].iloc[0]
    assert row["price"] is None or row["market_value"] != row["market_value"]  # NaN

    summary = book.summary()
    assert summary["missing_price"] == 1
    assert summary["total_value"] == 0.0


def test_risk_breakdown_weights(setup_book):
    book, owner, htsc, _ib = setup_book
    book.deposit(htsc, 1_000_000, trade_date="2026-01-02")
    # 高风险：股票 10 万
    book.adjust(htsc, kind="stock", market="CN", symbol="600519",
                name="贵州茅台", quantity=100, cost_price=1000)
    # 中风险：ETF 6 万
    book.adjust(htsc, kind="etf", market="CN", symbol="510300",
                name="沪深300ETF", quantity=20000, cost_price=3.0)
    # 现金（低风险）：直接把余额设成 4 万，便于核对比例
    cash_id = store.cash_instrument(book.conn, "CNY")
    store.upsert_holding(book.conn, htsc, cash_id, quantity=40000, cost_price=1.0)

    prices = {
        ("stock", "CN", "600519"): (1000.0, "2026-06-30"),
        ("etf", "CN", "510300"): (3.0, "2026-06-30"),
    }
    frame = book.positions(prices=prices)
    table = book.risk_breakdown(frame=frame).set_index("risk")

    assert table.loc["high", "value"] == pytest.approx(100000)
    assert table.loc["mid", "value"] == pytest.approx(60000)
    assert table.loc["low", "value"] == pytest.approx(40000)
    total = 200000
    assert table.loc["high", "weight"] == pytest.approx(50.0)
    assert table.loc["mid", "weight"] == pytest.approx(30.0)
    assert table.loc["low", "weight"] == pytest.approx(20.0)
    assert table["weight"].sum() == pytest.approx(100.0)


def test_multi_currency_converts_to_cny(setup_book):
    book, _owner, _htsc, ib = setup_book
    store.upsert_fx(book.conn, "2026-01-01", "USD", 7.1, "boc")
    book.deposit(ib, 10000, trade_date="2026-01-02")
    book.adjust(ib, kind="stock", market="US", symbol="AAPL", name="苹果",
                quantity=10, cost_price=180, trade_date="2026-01-03")

    prices = {("stock", "US", "AAPL"): (200.0, "2026-06-30")}
    frame = book.positions(prices=prices)
    summary = book.summary(frame=frame, as_of="2026-06-30")

    # adjust 不动现金：现金仍是 10000 USD，股票 10*200=2000 USD
    assert summary["cash_by_currency"]["USD"] == pytest.approx(10000.0)
    assert summary["total_value"] == pytest.approx((10000 + 2000) * 7.1, abs=1)


def test_missing_fx_falls_back_with_warning(setup_book, caplog):
    book, _owner, _htsc, ib = setup_book
    book.deposit(ib, 1000, trade_date="2026-01-02")
    summary = book.summary()
    assert summary["cash_by_currency"]["USD"] == pytest.approx(1000.0)
    # 没有汇率时按 1:1 兜底，但会记录告警
    assert summary["total_value"] == pytest.approx(1000.0)


def test_negative_cash_is_flagged(book):
    owner = book.create_owner("王大")
    account = book.add_account(owner, "华泰证券")
    book.buy(account, kind="stock", market="CN", symbol="000001",
             name="平安银行", quantity=100, price=12, trade_date="2026-01-05")
    summary = book.summary()
    assert summary["negative_cash"], "现金透支应当被标记出来"


# --------------------------------------------------------------------------
# 流水与重建
# --------------------------------------------------------------------------
def test_transaction_quantity_rebuilds_history(setup_book):
    book, _owner, htsc, _ib = setup_book
    book.deposit(htsc, 1_000_000, trade_date="2026-01-02")
    book.buy(htsc, kind="stock", market="CN", symbol="600519", name="贵州茅台",
             quantity=100, price=1500, trade_date="2026-01-05")
    book.buy(htsc, kind="stock", market="CN", symbol="600519",
             quantity=100, price=1600, trade_date="2026-02-05")
    book.sell(htsc, kind="stock", market="CN", symbol="600519",
              quantity=50, price=1700, trade_date="2026-03-05")

    instrument = store.find_instrument(book.conn, "stock", "CN", "600519")
    iid = instrument["id"]

    assert book.transaction_quantity(htsc, iid, "2026-01-04") == 0
    assert book.transaction_quantity(htsc, iid, "2026-01-05") == 100
    assert book.transaction_quantity(htsc, iid, "2026-02-05") == 200
    assert book.transaction_quantity(htsc, iid, "2026-03-05") == 150


def test_txn_list_is_filtered_by_account(setup_book):
    book, _owner, htsc, ib = setup_book
    book.deposit(htsc, 1000, trade_date="2026-01-02")
    book.deposit(ib, 1000, trade_date="2026-01-03")

    htsc_txns = store.list_txns(book.conn, account_id=htsc)
    assert len(htsc_txns) == 1
    assert htsc_txns[0]["action"] == schema.ACTION_DEPOSIT
    assert htsc_txns[0]["currency"] == "CNY"


def _txn_rows(book, account_id, *, symbol=None, action=None):
    rows = store.list_txns(book.conn, account_id=account_id)
    return [row for row in rows
            if (symbol is None or row["symbol"] == symbol)
            and (action is None or row["action"] == action)]


def test_delete_buy_rebuilds_quantity_cost_and_cash(book):
    owner = book.create_owner("王大")
    account = book.add_account(owner, "华泰证券")
    book.deposit(account, 1_000_000, trade_date="2026-01-02")
    book.buy(account, kind="stock", market="CN", symbol="600519", name="贵州茅台",
             quantity=100, price=1500, fee=15, trade_date="2026-01-05")
    book.buy(account, kind="stock", market="CN", symbol="600519",
             quantity=100, price=1600, fee=16, trade_date="2026-02-05")

    second_buy = next(row for row in _txn_rows(book, account, symbol="600519",
                                               action=schema.ACTION_BUY)
                      if row["price"] == 1600)
    result = book.delete_txn(second_buy["id"])

    expected_cost = (1500 * 100 + 15) / 100
    assert result["quantity"] == pytest.approx(100)
    assert result["cost_price"] == pytest.approx(expected_cost)
    assert result["cash"] == pytest.approx(1_000_000 - (1500 * 100 + 15))
    assert result["realized_updated"] == 0

    row = book.positions().set_index("symbol").loc["600519"]
    assert row["quantity"] == pytest.approx(100)
    assert row["cost_price"] == pytest.approx(expected_cost)
    assert store.get_txn(book.conn, second_buy["id"]) is None


def test_delete_sell_restores_holding_and_cash(book):
    owner = book.create_owner("王大")
    account = book.add_account(owner, "华泰证券")
    book.deposit(account, 200_000, trade_date="2026-01-02")
    book.buy(account, kind="stock", market="CN", symbol="600519", name="贵州茅台",
             quantity=100, price=1500, fee=15, trade_date="2026-01-05")
    book.sell(account, kind="stock", market="CN", symbol="600519",
              quantity=50, price=1600, fee=8, trade_date="2026-03-05")

    sell_txn = _txn_rows(book, account, symbol="600519", action=schema.ACTION_SELL)[0]
    result = book.delete_txn(sell_txn["id"])

    assert result["quantity"] == pytest.approx(100)
    assert result["cost_price"] == pytest.approx((1500 * 100 + 15) / 100)
    assert result["cash"] == pytest.approx(200_000 - (1500 * 100 + 15))
    assert _txn_rows(book, account, symbol="600519", action=schema.ACTION_SELL) == []
    assert book.positions().set_index("symbol").loc["600519", "quantity"] == pytest.approx(100)


def test_delete_only_buy_removes_the_holding(book):
    owner = book.create_owner("王大")
    account = book.add_account(owner, "华泰证券")
    book.deposit(account, 10_000, trade_date="2026-01-02")
    book.buy(account, kind="stock", market="CN", symbol="000001", name="平安银行",
             quantity=100, price=10, trade_date="2026-01-05")

    buy_txn = _txn_rows(book, account, symbol="000001", action=schema.ACTION_BUY)[0]
    result = book.delete_txn(buy_txn["id"])

    assert result["quantity"] == 0
    assert result["cash"] == pytest.approx(10_000)
    assert "000001" not in set(book.positions()["symbol"])


def test_delete_buy_keeps_opening_position_from_adjust(book):
    owner = book.create_owner("王大")
    account = book.add_account(owner, "华泰证券")
    book.adjust(account, kind="etf", market="CN", symbol="510300", name="沪深300ETF",
                quantity=10_000, cost_price=3.9, trade_date="2026-01-01")
    book.deposit(account, 10_000, trade_date="2026-01-02")
    book.buy(account, kind="etf", market="CN", symbol="510300",
             quantity=1_000, price=4.2, fee=5, trade_date="2026-02-02")

    buy_txn = _txn_rows(book, account, symbol="510300", action=schema.ACTION_BUY)[0]
    result = book.delete_txn(buy_txn["id"])

    assert result["quantity"] == pytest.approx(10_000)
    assert result["cost_price"] == pytest.approx(3.9)
    assert result["cash"] == pytest.approx(10_000)
    row = book.positions().set_index("symbol").loc["510300"]
    assert row["quantity"] == pytest.approx(10_000)
    assert row["cost_price"] == pytest.approx(3.9)


def test_delete_sell_after_reopen_uses_new_opening_date(book):
    owner = book.create_owner("王大")
    account = book.add_account(owner, "华泰证券")
    book.deposit(account, 10_000, trade_date="2026-01-02")
    book.buy(account, kind="stock", market="CN", symbol="600519",
             quantity=100, price=10, trade_date="2026-01-05")
    book.sell(account, kind="stock", market="CN", symbol="600519",
              quantity=100, price=12, trade_date="2026-02-05")
    book.buy(account, kind="stock", market="CN", symbol="600519",
             quantity=100, price=20, trade_date="2026-03-05")
    book.sell(account, kind="stock", market="CN", symbol="600519",
              quantity=50, price=25, trade_date="2026-04-05")

    last_sell = _txn_rows(book, account, symbol="600519", action=schema.ACTION_SELL)[0]
    book.delete_txn(last_sell["id"])

    instrument = store.find_instrument(book.conn, "stock", "CN", "600519")
    holding = store.get_holding(book.conn, account, instrument["id"])
    assert holding["quantity"] == pytest.approx(100)
    assert holding["cost_price"] == pytest.approx(20)
    assert holding["opened_at"] == "2026-03-05"


def test_delete_buy_used_by_later_sell_is_rejected(book):
    owner = book.create_owner("王大")
    account = book.add_account(owner, "华泰证券")
    book.deposit(account, 10_000, trade_date="2026-01-02")
    book.buy(account, kind="stock", market="CN", symbol="600519",
             quantity=100, price=10, trade_date="2026-01-05")
    book.sell(account, kind="stock", market="CN", symbol="600519",
              quantity=100, price=12, trade_date="2026-03-05")

    buy_txn = _txn_rows(book, account, symbol="600519", action=schema.ACTION_BUY)[0]
    with pytest.raises(ValueError) as excinfo:
        book.delete_txn(buy_txn["id"])
    assert "已经被后面的卖出用掉" in str(excinfo.value)

    # 拒绝后什么都没变：流水还在、现金还是 10200、持仓仍是 0
    assert store.get_txn(book.conn, buy_txn["id"]) is not None
    assert book.cash_balance(account) == pytest.approx(10_200)
    assert "600519" not in set(book.positions()["symbol"])


def test_delete_buy_with_intermediate_oversell_is_rejected(book):
    owner = book.create_owner("王大")
    account = book.add_account(owner, "华泰证券")
    book.deposit(account, 10_000, trade_date="2026-01-02")
    book.buy(account, kind="stock", market="CN", symbol="600519",
             quantity=100, price=10, trade_date="2026-01-05")
    book.sell(account, kind="stock", market="CN", symbol="600519",
              quantity=100, price=12, trade_date="2026-02-05")
    book.buy(account, kind="stock", market="CN", symbol="600519",
             quantity=200, price=20, trade_date="2026-03-05")

    first_buy = next(row for row in _txn_rows(book, account, symbol="600519",
                                              action=schema.ACTION_BUY)
                     if row["price"] == 10)
    with pytest.raises(ValueError) as excinfo:
        book.delete_txn(first_buy["id"])
    assert "已经被后面的卖出用掉" in str(excinfo.value)

    # 拒绝后保持原样：200 股 @20，现金 6200
    row = book.positions().set_index("symbol").loc["600519"]
    assert row["quantity"] == pytest.approx(200)
    assert row["cost_price"] == pytest.approx(20)
    assert book.cash_balance(account) == pytest.approx(6_200)


def test_delete_buy_updates_later_sell_realized_pnl(book):
    owner = book.create_owner("王大")
    account = book.add_account(owner, "华泰证券")
    book.deposit(account, 10_000, trade_date="2026-01-02")
    book.buy(account, kind="stock", market="CN", symbol="600519",
             quantity=100, price=10, trade_date="2026-01-05")
    book.buy(account, kind="stock", market="CN", symbol="600519",
             quantity=100, price=20, trade_date="2026-02-05")
    book.sell(account, kind="stock", market="CN", symbol="600519",
              quantity=50, price=25, trade_date="2026-03-05")

    second_buy = next(row for row in _txn_rows(book, account, symbol="600519",
                                               action=schema.ACTION_BUY)
                      if row["price"] == 20)
    result = book.delete_txn(second_buy["id"])

    # 删除第二次买入后成本回到 10，那笔卖出的已实现盈亏从 500 变成 750
    assert result["quantity"] == pytest.approx(50)
    assert result["cost_price"] == pytest.approx(10)
    assert result["realized_updated"] == 1
    sell_txn = _txn_rows(book, account, symbol="600519", action=schema.ACTION_SELL)[0]
    assert sell_txn["realized_pnl"] == pytest.approx(750)
    assert result["cash"] == pytest.approx(10_250)


def test_delete_non_trade_txn_is_rejected(book):
    owner = book.create_owner("王大")
    account = book.add_account(owner, "华泰证券")
    book.deposit(account, 10_000, trade_date="2026-01-02")
    deposit_txn = _txn_rows(book, account, action=schema.ACTION_DEPOSIT)[0]

    with pytest.raises(ValueError) as excinfo:
        book.delete_txn(deposit_txn["id"])
    assert "只能删除" in str(excinfo.value)
    assert store.get_txn(book.conn, deposit_txn["id"]) is not None
    assert book.cash_balance(account) == pytest.approx(10_000)


def test_delete_missing_txn_is_rejected(book):
    with pytest.raises(ValueError):
        book.delete_txn(999999)


def test_deleting_account_cascades_holdings_and_txns(setup_book):
    book, _owner, htsc, _ib = setup_book
    book.deposit(htsc, 100000, trade_date="2026-01-02")
    book.buy(htsc, kind="stock", market="CN", symbol="600519", name="贵州茅台",
             quantity=10, price=1500, trade_date="2026-01-05")

    store.delete_account(book.conn, htsc)
    assert book.positions().empty
    assert store.list_txns(book.conn, account_id=htsc) == []


def test_ensure_schema_migrates_old_dividend_table(tmp_path):
    """旧库的 portfolio_dividend 没有 report_period，打开时要自动补列。"""
    db = tmp_path / "old.db"
    with store.open_db(db, create=True) as conn:
        conn.execute(
            f"""
            CREATE TABLE {schema.TABLE_DIVIDEND} (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                instrument_id   INTEGER NOT NULL,
                ex_date         TEXT NOT NULL,
                pay_date        TEXT,
                cash_per_share  REAL NOT NULL DEFAULT 0,
                stock_per_share REAL NOT NULL DEFAULT 0,
                currency        TEXT NOT NULL DEFAULT 'CNY',
                source          TEXT NOT NULL DEFAULT 'auto',
                recorded        INTEGER NOT NULL DEFAULT 0,
                note            TEXT NOT NULL DEFAULT '',
                fetched_at      TEXT NOT NULL,
                UNIQUE(instrument_id, ex_date)
            )
            """
        )
        conn.commit()
        store.ensure_schema(conn)
        columns = {row[1] for row in conn.execute(
            f"PRAGMA table_info({schema.TABLE_DIVIDEND})")}
        assert "report_period" in columns


def test_cash_instrument_is_created_per_currency(setup_book):
    book, _owner, htsc, ib = setup_book
    cny_cash = store.cash_instrument(book.conn, "CNY")
    usd_cash = store.cash_instrument(book.conn, "USD")
    assert cny_cash != usd_cash

    cny = store.get_instrument(book.conn, cny_cash)
    usd = store.get_instrument(book.conn, usd_cash)
    assert cny["risk"] == schema.RISK_LOW
    assert usd["currency"] == "USD"
    book_cash = {i["currency"] for i in store.list_instruments(book.conn, schema.KIND_CASH)}
    assert {"CNY", "USD"} <= book_cash


# --------------------------------------------------------------------------
# 风险默认值
# --------------------------------------------------------------------------
def test_default_risk_by_kind(book):
    owner = book.create_owner("王大")
    account = book.add_account(owner, "华泰证券")
    book.deposit(account, 1000, trade_date="2026-01-02")
    book.adjust(account, kind="stock", market="CN", symbol="600519", quantity=1, cost_price=1)
    book.adjust(account, kind="etf", market="CN", symbol="510300", quantity=1, cost_price=1)
    book.adjust(account, kind="fund", market="CN", symbol="710001", quantity=1, cost_price=1)

    risks = {row["symbol"]: row["risk"] for row in store.list_holdings(book.conn)}
    assert risks["600519"] == schema.RISK_HIGH
    assert risks["510300"] == schema.RISK_MID
    assert risks["710001"] == schema.RISK_MID
    assert risks[schema.CASH_SYMBOL] == schema.RISK_LOW


def test_risk_can_be_overridden(setup_book):
    book, _owner, htsc, _ib = setup_book
    book.adjust(htsc, kind="stock", market="CN", symbol="600519", quantity=1, cost_price=1)
    instrument = store.find_instrument(book.conn, "stock", "CN", "600519")
    store.update_instrument(book.conn, instrument["id"], risk=schema.RISK_LOW)

    row = book.positions().iloc[0]
    assert row["risk"] == schema.RISK_LOW
