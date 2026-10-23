"""资产管理的数据契约：表名、常量、展示名与建表语句。

设计原则（与 quant.data.schema 一致）
------------------------------------
1. 内部一律英文，中文只在展示层出现。
2. 资产数据库与行情库分开（quant.config.PORTFOLIO_DB_PATH）：
   行情库可以随时重建，手工录入的账户与流水不能丢。
3. 市值口径统一为「数量 × 价格」；现金的数量就是金额，价格恒为 1。
"""

from __future__ import annotations

#: 资产库结构版本
SCHEMA_VERSION = 1

# --------------------------------------------------------------------------
# 表名
# --------------------------------------------------------------------------
TABLE_META = "portfolio_meta"
TABLE_OWNER = "portfolio_owner"
TABLE_ACCOUNT = "portfolio_account"
TABLE_INSTRUMENT = "portfolio_instrument"
TABLE_HOLDING = "portfolio_holding"
TABLE_TXN = "portfolio_txn"
TABLE_FX = "portfolio_fx_rate"
TABLE_DIVIDEND = "portfolio_dividend"

ALL_TABLES = (
    TABLE_META, TABLE_OWNER, TABLE_ACCOUNT, TABLE_INSTRUMENT,
    TABLE_HOLDING, TABLE_TXN, TABLE_FX, TABLE_DIVIDEND,
)

# --------------------------------------------------------------------------
# 产品类型
# --------------------------------------------------------------------------
KIND_STOCK = "stock"
KIND_ETF = "etf"
KIND_FUND = "fund"
KIND_CASH = "cash"

KINDS: tuple[str, ...] = (KIND_STOCK, KIND_ETF, KIND_FUND, KIND_CASH)

KIND_NAMES: dict[str, str] = {
    KIND_STOCK: "股票",
    KIND_ETF: "场内基金",
    KIND_FUND: "场外基金",
    KIND_CASH: "现金",
}

#: 现金产品的代码（每个市场一条）
CASH_SYMBOL = "CASH"

# --------------------------------------------------------------------------
# 市场与币种
# --------------------------------------------------------------------------
MARKET_CN = "CN"
MARKET_HK = "HK"
MARKET_US = "US"

MARKETS: tuple[str, ...] = (MARKET_CN, MARKET_HK, MARKET_US)

MARKET_NAMES: dict[str, str] = {
    MARKET_CN: "A股/中国",
    MARKET_HK: "港股",
    MARKET_US: "美股",
}

#: 市场 -> 结算币种
MARKET_CURRENCY: dict[str, str] = {
    MARKET_CN: "CNY",
    MARKET_HK: "HKD",
    MARKET_US: "USD",
}

#: 币种 -> 市场（现金产品按币种归市场）
CURRENCY_MARKET: dict[str, str] = {v: k for k, v in MARKET_CURRENCY.items()}

CURRENCIES: tuple[str, ...] = ("CNY", "HKD", "USD")

CURRENCY_NAMES: dict[str, str] = {"CNY": "人民币", "HKD": "港币", "USD": "美元"}

CURRENCY_SYMBOL: dict[str, str] = {"CNY": "¥", "HKD": "HK$", "USD": "$"}

#: 统计基准币种
BASE_CURRENCY = "CNY"

# --------------------------------------------------------------------------
# 风险等级
# --------------------------------------------------------------------------
RISK_HIGH = "high"
RISK_MID = "mid"
RISK_LOW = "low"

RISKS: tuple[str, ...] = (RISK_HIGH, RISK_MID, RISK_LOW)

RISK_NAMES: dict[str, str] = {RISK_HIGH: "高风险", RISK_MID: "中风险", RISK_LOW: "低风险"}

#: 展示顺序（高 -> 中 -> 低）
RISK_ORDER: dict[str, int] = {RISK_HIGH: 0, RISK_MID: 1, RISK_LOW: 2}

#: 新建产品时的默认风险等级（用户可按产品手动改）
DEFAULT_RISK: dict[str, str] = {
    KIND_STOCK: RISK_HIGH,
    KIND_ETF: RISK_MID,
    KIND_FUND: RISK_MID,
    KIND_CASH: RISK_LOW,
}

#: 风险配色（与 quant.ui.theme.C 同源）
RISK_COLOURS: dict[str, str] = {RISK_HIGH: "#D93F3F", RISK_MID: "#B45309", RISK_LOW: "#2E9E5B"}

# --------------------------------------------------------------------------
# 交易动作
# --------------------------------------------------------------------------
ACTION_BUY = "buy"
ACTION_SELL = "sell"
ACTION_ADJUST = "adjust"
ACTION_DEPOSIT = "deposit"
ACTION_WITHDRAW = "withdraw"
ACTION_DIVIDEND = "dividend"

ACTIONS: tuple[str, ...] = (
    ACTION_BUY, ACTION_SELL, ACTION_ADJUST,
    ACTION_DEPOSIT, ACTION_WITHDRAW, ACTION_DIVIDEND,
)

ACTION_NAMES: dict[str, str] = {
    ACTION_BUY: "买入",
    ACTION_SELL: "卖出",
    ACTION_ADJUST: "数量调整",
    ACTION_DEPOSIT: "存入现金",
    ACTION_WITHDRAW: "取出资金",
    ACTION_DIVIDEND: "分红入账",
}

#: 会让持仓数量增加的动作
INCREASE_ACTIONS = (ACTION_BUY, ACTION_ADJUST)
#: 会让持仓数量减少的动作
DECREASE_ACTIONS = (ACTION_SELL,)

# --------------------------------------------------------------------------
# 其它
# --------------------------------------------------------------------------
#: 资金账户类型
ACCOUNT_TYPES: tuple[str, ...] = ("securities", "fund", "bank", "other")
ACCOUNT_TYPE_NAMES: dict[str, str] = {
    "securities": "证券账户",
    "fund": "基金账户",
    "bank": "银行账户",
    "other": "其它",
}

#: 价格来源
PRICE_SOURCE_AUTO = "auto"
PRICE_SOURCE_MANUAL = "manual"

#: 分红来源
DIVIDEND_SOURCE_AUTO = "auto"
DIVIDEND_SOURCE_MANUAL = "manual"

#: 建表语句（幂等）
DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_META} (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- 资产账户（一个人）
CREATE TABLE IF NOT EXISTS {TABLE_OWNER} (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    note       TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

-- 资金账户（某人的一个券商/基金账户）
CREATE TABLE IF NOT EXISTS {TABLE_ACCOUNT} (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id    INTEGER NOT NULL REFERENCES {TABLE_OWNER}(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    account_type TEXT NOT NULL DEFAULT 'securities',
    currency    TEXT NOT NULL DEFAULT 'CNY',
    note        TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    UNIQUE(owner_id, name)
);

-- 产品：股票 / 场内基金 / 场外基金 / 现金
CREATE TABLE IF NOT EXISTS {TABLE_INSTRUMENT} (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    kind         TEXT NOT NULL,
    market       TEXT NOT NULL DEFAULT 'CN',
    symbol       TEXT NOT NULL,
    name         TEXT NOT NULL DEFAULT '',
    currency     TEXT NOT NULL DEFAULT 'CNY',
    risk         TEXT NOT NULL DEFAULT 'mid',
    price_source TEXT NOT NULL DEFAULT 'auto',
    manual_price REAL,
    price_date   TEXT,
    note         TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL,
    UNIQUE(kind, market, symbol)
);

-- 持仓：一个资金账户里的一个产品
CREATE TABLE IF NOT EXISTS {TABLE_HOLDING} (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id    INTEGER NOT NULL REFERENCES {TABLE_ACCOUNT}(id) ON DELETE CASCADE,
    instrument_id INTEGER NOT NULL REFERENCES {TABLE_INSTRUMENT}(id),
    quantity      REAL NOT NULL DEFAULT 0,
    cost_price    REAL NOT NULL DEFAULT 0,
    opened_at     TEXT,
    updated_at    TEXT NOT NULL,
    UNIQUE(account_id, instrument_id)
);

-- 交易流水
CREATE TABLE IF NOT EXISTS {TABLE_TXN} (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id    INTEGER NOT NULL REFERENCES {TABLE_ACCOUNT}(id) ON DELETE CASCADE,
    instrument_id INTEGER NOT NULL REFERENCES {TABLE_INSTRUMENT}(id),
    trade_date    TEXT NOT NULL,
    action        TEXT NOT NULL,
    quantity      REAL NOT NULL,
    price         REAL NOT NULL DEFAULT 0,
    fee           REAL NOT NULL DEFAULT 0,
    realized_pnl  REAL,
    note          TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL
);

-- 汇率：1 外币 = rate 人民币
CREATE TABLE IF NOT EXISTS {TABLE_FX} (
    date     TEXT NOT NULL,
    currency TEXT NOT NULL,
    rate     REAL NOT NULL,
    source   TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (date, currency)
) WITHOUT ROWID;

-- 分红：自动拉取或手动登记
CREATE TABLE IF NOT EXISTS {TABLE_DIVIDEND} (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument_id   INTEGER NOT NULL REFERENCES {TABLE_INSTRUMENT}(id),
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
);
"""

#: 索引
INDEXES = f"""
CREATE INDEX IF NOT EXISTS idx_txn_account_date ON {TABLE_TXN}(account_id, trade_date);
CREATE INDEX IF NOT EXISTS idx_txn_instrument   ON {TABLE_TXN}(instrument_id, trade_date);
CREATE INDEX IF NOT EXISTS idx_holding_account  ON {TABLE_HOLDING}(account_id);
CREATE INDEX IF NOT EXISTS idx_dividend_exdate  ON {TABLE_DIVIDEND}(ex_date);
CREATE INDEX IF NOT EXISTS idx_account_owner    ON {TABLE_ACCOUNT}(owner_id);
"""

#: 展示名（供 UI / 报表使用）
DISPLAY_NAMES: dict[str, str] = {
    "id": "序号",
    "owner": "资产账户",
    "owner_id": "资产账户",
    "account": "资金账户",
    "account_id": "资金账户",
    "name": "名称",
    "kind": "类型",
    "market": "市场",
    "symbol": "代码",
    "currency": "币种",
    "risk": "风险",
    "quantity": "数量",
    "cost_price": "成本价",
    "price": "现价",
    "market_value": "市值",
    "cost_value": "成本",
    "pnl": "浮动盈亏",
    "pnl_pct": "盈亏比例",
    "weight": "占比",
    "trade_date": "日期",
    "action": "操作",
    "fee": "手续费",
    "realized_pnl": "已实现盈亏",
    "note": "备注",
    "ex_date": "除息日",
    "pay_date": "派息日",
    "cash_per_share": "每股分红",
    "stock_per_share": "每股送转",
    "cash_amount": "分红金额",
    "forecast_amount": "预期分红",
    "forecast_base": "折合人民币",
    "yield_pct": "股息率",
    "last_ex_date": "最近除息日",
    "scope": "口径",
    "recorded": "已入账",
    "price_source": "价格来源",
    "manual_price": "手动价",
    "account_type": "账户类型",
    "opened_at": "建仓日",
    "updated_at": "更新时间",
    "created_at": "创建时间",
    "base_value": "折合人民币",
}
