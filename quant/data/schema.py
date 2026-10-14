"""数据契约：英文列名定义、中文列名映射与展示名。

设计原则
--------
1. **内部一律英文列名**；中文只出现在两个地方：
   - 迁移时读取原始 CSV 的列名映射（本文件）
   - 展示层（`DISPLAY_NAMES`，规划由 quant/ui 使用）
2. 原始 CSV 保持不动，归档到 `data/original/`；SQLite 是唯一查询入口。
3. 列名带 `_qfq` 后缀表示**前复权**；不带后缀的 OHLC 表示**不复权（原始价）**。

注意价格列的方向
----------------
数据库 daily_price 表：`open/high/low/close` 是**不复权**，`*_qfq` 是前复权。
而 `get_stock_price()` 返回的 DataFrame 里：
    `open/high/low/close` → 前复权（沿用重构前的语义，便于回测）
    `*_org`               → 不复权（沿用重构前的语义）
    `*_qfq`               → 前复权（显式名，与上面等价）
"""

from __future__ import annotations

SCHEMA_VERSION = 2

# --------------------------------------------------------------------------
# 表名
# --------------------------------------------------------------------------
TABLE_META = "meta"
TABLE_STOCK_LIST = "stock_list"
TABLE_DAILY_PRICE = "daily_price"
TABLE_ETF_DAILY = "etf_daily"
TABLE_FUNDAMENTAL = "fundamental"
TABLE_FUNDAMENTAL_GROWTH = "fundamental_growth"
TABLE_FINANCIAL = "financial_indicator"
TABLE_TRADE_RECORD = "trade_record"
TABLE_VALUATION_PERCENTILE = "valuation_percentile"

ALL_TABLES = (
    TABLE_META,
    TABLE_STOCK_LIST,
    TABLE_DAILY_PRICE,
    TABLE_ETF_DAILY,
    TABLE_FUNDAMENTAL,
    TABLE_FUNDAMENTAL_GROWTH,
    TABLE_FINANCIAL,
    TABLE_TRADE_RECORD,
    TABLE_VALUATION_PERCENTILE,
)

# --------------------------------------------------------------------------
# 估值历史分位
# --------------------------------------------------------------------------
#: 计算分位的窗口（年）；0 表示「全部可得历史」
VALUATION_WINDOWS: tuple[int, ...] = (3, 5, 10, 0)

#: 默认展示/筛选用的窗口
DEFAULT_VALUATION_WINDOW = 10

#: valuation_percentile 表列（除主键 symbol/window_years）
VALUATION_PERCENTILE_COLUMNS: tuple[str, ...] = (
    "as_of", "current_pe", "current_pb", "current_ps",
    "pe_pct", "pb_pct", "ps_pct",
    "sample_days", "window_start", "window_years_actual", "computed_at",
)

#: 快照里附带的分位列：窗口 -> 列名
VALUATION_PERCENTILE_FIELDS: dict[int, str] = {
    3: "pe_pct_3y",
    5: "pe_pct_5y",
    10: "pe_pct_10y",
    0: "pe_pct_all",
}

# --------------------------------------------------------------------------
# 价格
# --------------------------------------------------------------------------
#: 日线原始 CSV 列名 -> 数据库列名（不复权 OHLC 直接用 open/high/low/close）
PRICE_COLUMN_MAP: dict[str, str] = {
    "开盘": "open",
    "收盘": "close",
    "最高": "high",
    "最低": "low",
    "开盘_qfq": "open_qfq",
    "收盘_qfq": "close_qfq",
    "最高_qfq": "high_qfq",
    "最低_qfq": "low_qfq",
    "成交量": "volume",
    "成交额": "turnover",
    "振幅": "amplitude",
    "涨跌幅": "pct_change",
    "涨跌额": "price_change",
    "换手率": "turnover_rate",
    "日期": "date",
}

#: daily_price 表的业务列（不含 symbol/date/idate 主键列）
PRICE_VALUE_COLUMNS: tuple[str, ...] = (
    "open", "high", "low", "close",
    "open_qfq", "high_qfq", "low_qfq", "close_qfq",
    "volume", "turnover", "amplitude", "pct_change", "price_change", "turnover_rate",
)

#: ETF 原始 CSV 列名 -> 数据库列名（ETF 数据本身已是前复权）
ETF_COLUMN_MAP: dict[str, str] = {
    "date": "date",
    "open": "open_qfq",
    "close": "close_qfq",
    "high": "high_qfq",
    "low": "low_qfq",
    "volumn": "volume",
    "turnover": "turnover",
    "amp": "amplitude",
    "percent_change": "pct_change",
    "value_change": "price_change",
    "turnover_rate": "turnover_rate",
}

#: get_stock_price() 返回给上层的列顺序
PRICE_FRAME_COLUMNS: tuple[str, ...] = (
    "date", "idate",
    "open", "high", "low", "close",
    "open_qfq", "high_qfq", "low_qfq", "close_qfq",
    "open_org", "high_org", "low_org", "close_org",
    "volume", "turnover", "amplitude", "pct_change", "price_change", "turnover_rate",
)

# --------------------------------------------------------------------------
# 季度基本面（jibenmian 三表）
# --------------------------------------------------------------------------
#: 表 -> {原始中文列名: 英文列名}
FUNDAMENTAL_COLUMN_MAP: dict[str, dict[str, str]] = {
    "zcfz": {
        "股票代码": "symbol",
        "股票简称": "name",
        "资产-货币资金": "cash",
        "资产-应收账款": "accounts_receivable",
        "资产-存货": "inventory",
        "资产-总资产": "total_assets",
        "资产-总资产同比": "total_assets_yoy",
        "负债-应付账款": "accounts_payable",
        "负债-预收账款": "advance_receipts",
        "负债-总负债": "total_liabilities",
        "负债-总负债同比": "total_liabilities_yoy",
        "资产负债率": "debt_ratio",
        "股东权益合计": "total_equity",
        "公告日期": "ann_date_bs",
    },
    "lrb": {
        "股票代码": "symbol",
        "净利润": "net_profit",
        "净利润同比": "net_profit_yoy",
        "营业总收入": "total_revenue",
        "营业总收入同比": "total_revenue_yoy",
        "营业总支出-营业支出": "operating_cost",
        "营业总支出-销售费用": "selling_expense",
        "营业总支出-管理费用": "admin_expense",
        "营业总支出-财务费用": "finance_expense",
        "营业总支出-营业总支出": "total_operating_expense",
        "营业利润": "operating_profit",
        "利润总额": "total_profit",
        "公告日期": "ann_date_is",
    },
    "xjll": {
        "股票代码": "symbol",
        "净现金流-净现金流": "net_cash_flow",
        "净现金流-同比增长": "net_cash_flow_yoy",
        "经营性现金流-现金流量净额": "operating_cash_flow",
        "经营性现金流-净现金流占比": "operating_cash_flow_ratio",
        "投资性现金流-现金流量净额": "investing_cash_flow",
        "投资性现金流-净现金流占比": "investing_cash_flow_ratio",
        "融资性现金流-现金流量净额": "financing_cash_flow",
        "融资性现金流-净现金流占比": "financing_cash_flow_ratio",
        "公告日期": "ann_date_cf",
    },
}

#: fundamental 表中的文本列（股票简称 + 三个公告日期）
FUNDAMENTAL_TEXT_COLUMNS: tuple[str, ...] = (
    "name", "ann_date_bs", "ann_date_is", "ann_date_cf",
)

#: fundamental 表中的数值列
FUNDAMENTAL_NUMERIC_COLUMNS: tuple[str, ...] = (
    # 资产负债表
    "cash", "accounts_receivable", "inventory", "total_assets", "total_assets_yoy",
    "accounts_payable", "advance_receipts", "total_liabilities", "total_liabilities_yoy",
    "debt_ratio", "total_equity",
    # 利润表
    "net_profit", "net_profit_yoy", "total_revenue", "total_revenue_yoy",
    "operating_cost", "selling_expense", "admin_expense", "finance_expense",
    "total_operating_expense", "operating_profit", "total_profit",
    # 现金流量表
    "net_cash_flow", "net_cash_flow_yoy",
    "operating_cash_flow", "operating_cash_flow_ratio",
    "investing_cash_flow", "investing_cash_flow_ratio",
    "financing_cash_flow", "financing_cash_flow_ratio",
    # 滚动四季度（TTM，由 rebuild-fundamental-ttm 计算）
    "revenue_ttm", "net_profit_ttm",
)

#: fundamental 表全部业务列（除主键 symbol/season）
FUNDAMENTAL_VALUE_COLUMNS: tuple[str, ...] = FUNDAMENTAL_TEXT_COLUMNS + FUNDAMENTAL_NUMERIC_COLUMNS

#: 股票简称（来自 zcfz）
FUNDAMENTAL_NAME_COLUMN = "name"

# --------------------------------------------------------------------------
# 单季增长
# --------------------------------------------------------------------------
#: 单季增长列（除主键 symbol/season）
GROWTH_VALUE_COLUMNS: tuple[str, ...] = (
    "pre_year_income", "season_income", "season_income_growth",
    "pre_year_profit", "season_profit", "season_profit_growth",
)

#: 计算单季增长时使用的字段：类型 -> (累计值列, 同比列, 去年同季列, 单季列, 单季同比列)
GROWTH_FIELD_MAP: dict[str, tuple[str, str, str, str, str]] = {
    "收入": ("total_revenue", "total_revenue_yoy", "pre_year_income", "season_income", "season_income_growth"),
    "利润": ("net_profit", "net_profit_yoy", "pre_year_profit", "season_profit", "season_profit_growth"),
}

#: 旧版（中文）列名，仅用于输出兼容
LEGACY_GROWTH_COLUMN_MAP: dict[str, str] = {
    "symbol": "股票代码",
    "season": "iDATE",
    "pre_year_income": "preYearIncome",
    "season_income": "SeasonIncome",
    "season_income_growth": "SeasonIncomeGrowth",
    "pre_year_profit": "preYearProfit",
    "season_profit": "SeasonProfit",
    "season_profit_growth": "SeasonProfitGrowth",
}

# --------------------------------------------------------------------------
# 财务指标（financial_report）
# --------------------------------------------------------------------------
#: financial_report 原始中文列名 -> 英文列名（精选子集，完整数据保留在 original/financial）
FINANCIAL_COLUMN_MAP: dict[str, str] = {
    "日期": "report_date",
    "摊薄每股收益(元)": "eps_diluted",
    "加权每股收益(元)": "eps_weighted",
    "每股收益_调整后(元)": "eps_adjusted",
    "扣除非经常性损益后的每股收益(元)": "eps_deducted",
    "每股净资产_调整前(元)": "bvps_before",
    "每股净资产_调整后(元)": "bvps_after",
    "每股经营性现金流(元)": "ocf_per_share",
    "每股资本公积金(元)": "capital_reserve_per_share",
    "每股未分配利润(元)": "retained_earnings_per_share",
    "总资产利润率(%)": "roa",
    "主营业务利润率(%)": "main_business_margin",
    "营业利润率(%)": "operating_margin",
    "销售净利率(%)": "net_margin",
    "销售毛利率(%)": "gross_margin",
    "净资产收益率(%)": "roe",
    "加权净资产收益率(%)": "roe_weighted",
    "主营业务利润(元)": "main_business_profit",
    "扣除非经常性损益后的净利润(元)": "net_profit_deducted",
    "主营业务收入增长率(%)": "revenue_growth",
    "净利润增长率(%)": "profit_growth",
    "总资产(元)": "total_assets",
    "资产负债率(%)": "debt_ratio",
    "流动比率": "current_ratio",
    "速动比率": "quick_ratio",
    "应收账款周转率(次)": "receivable_turnover",
    "存货周转率(次)": "inventory_turnover",
    "总资产周转率(次)": "asset_turnover",
}

#: financial_indicator 表列（除主键 symbol/report_date 与 idate）
FINANCIAL_VALUE_COLUMNS: tuple[str, ...] = tuple(
    value for value in FINANCIAL_COLUMN_MAP.values() if value != "report_date"
) + ("eps_ttm", "bvps_ttm")

# --------------------------------------------------------------------------
# 展示名（供 UI / 报表使用；内部数据不使用中文列名）
# --------------------------------------------------------------------------
DISPLAY_NAMES: dict[str, str] = {
    # 通用
    "symbol": "股票代码", "name": "股票简称", "date": "日期", "season": "报告期",
    "idate": "报告期(整数)", "ann_date": "公告日期",
    # 价格
    "open": "开盘", "high": "最高", "low": "最低", "close": "收盘",
    "open_qfq": "开盘(前复权)", "high_qfq": "最高(前复权)",
    "low_qfq": "最低(前复权)", "close_qfq": "收盘(前复权)",
    "open_org": "开盘(不复权)", "high_org": "最高(不复权)",
    "low_org": "最低(不复权)", "close_org": "收盘(不复权)",
    "volume": "成交量", "turnover": "成交额", "amplitude": "振幅",
    "pct_change": "涨跌幅", "price_change": "涨跌额", "turnover_rate": "换手率",
    # 资产负债表
    "cash": "货币资金", "accounts_receivable": "应收账款", "inventory": "存货",
    "total_assets": "总资产", "total_assets_yoy": "总资产同比",
    "accounts_payable": "应付账款", "advance_receipts": "预收账款",
    "total_liabilities": "总负债", "total_liabilities_yoy": "总负债同比",
    "debt_ratio": "资产负债率", "total_equity": "股东权益合计",
    # 利润表
    "net_profit": "净利润", "net_profit_yoy": "净利润同比",
    "total_revenue": "营业总收入", "total_revenue_yoy": "营业总收入同比",
    "operating_cost": "营业支出", "selling_expense": "销售费用",
    "admin_expense": "管理费用", "finance_expense": "财务费用",
    "total_operating_expense": "营业总支出", "operating_profit": "营业利润",
    "total_profit": "利润总额",
    # 现金流量表
    "net_cash_flow": "净现金流", "net_cash_flow_yoy": "净现金流同比",
    "operating_cash_flow": "经营性现金流净额", "operating_cash_flow_ratio": "经营性现金流占比",
    "investing_cash_flow": "投资性现金流净额", "investing_cash_flow_ratio": "投资性现金流占比",
    "financing_cash_flow": "融资性现金流净额", "financing_cash_flow_ratio": "融资性现金流占比",
    # 单季增长
    "pre_year_income": "去年同季收入", "season_income": "当季收入",
    "season_income_growth": "当季收入同比", "pre_year_profit": "去年同季利润",
    "season_profit": "当季利润", "season_profit_growth": "当季利润同比",
    # 财务指标
    "report_date": "报告期", "eps_diluted": "摊薄每股收益", "eps_weighted": "加权每股收益",
    "eps_adjusted": "每股收益(调整后)", "eps_deducted": "每股收益(扣非)",
    "bvps_before": "每股净资产(调整前)", "bvps_after": "每股净资产(调整后)",
    "ocf_per_share": "每股经营性现金流", "capital_reserve_per_share": "每股资本公积金",
    "retained_earnings_per_share": "每股未分配利润", "roa": "总资产利润率",
    "main_business_margin": "主营业务利润率", "operating_margin": "营业利润率",
    "net_margin": "销售净利率", "gross_margin": "销售毛利率",
    "roe": "净资产收益率", "roe_weighted": "加权净资产收益率",
    "main_business_profit": "主营业务利润", "net_profit_deducted": "扣非净利润",
    "revenue_growth": "主营收入增长率", "profit_growth": "净利润增长率",
    "current_ratio": "流动比率", "quick_ratio": "速动比率",
    "receivable_turnover": "应收账款周转率", "inventory_turnover": "存货周转率",
    "asset_turnover": "总资产周转率",
    "eps_ttm": "每股收益(TTM)", "bvps_ttm": "每股净资产(TTM)",
    "revenue_ttm": "营业总收入(TTM)", "net_profit_ttm": "净利润(TTM)",
    "pe": "市盈率", "pb": "市净率", "ps": "市销率",
    # 估值历史分位
    "pe_pct_3y": "PE分位(3年)", "pe_pct_5y": "PE分位(5年)",
    "pe_pct_10y": "PE分位(10年)", "pe_pct_all": "PE分位(全历史)",
    "pb_pct_10y": "PB分位(10年)", "ps_pct_10y": "PS分位(10年)",
    "current_pe": "当前PE", "current_pb": "当前PB", "current_ps": "当前PS",
    "sample_days": "样本交易日数", "window_start": "窗口起点",
    "as_of": "基准日", "window_years": "窗口(年)",
}


def display_name(column: str) -> str:
    """英文列名 -> 中文展示名（未知列原样返回）。"""
    return DISPLAY_NAMES.get(column, column)


def rename_for_display(df):
    """把 DataFrame 的列名换成中文展示名（返回新对象，用于 UI/图表）。"""
    return df.rename(columns=DISPLAY_NAMES)
