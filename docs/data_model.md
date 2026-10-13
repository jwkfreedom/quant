# 数据模型（阶段 2.2）

## 总览

阶段 2.2 起，**SQLite 是唯一查询入口**，原始 CSV 只作为归档保留在 `data/original/`。

```
data/
├── quant.db                     SQLite 主库（WAL 模式）
├── original/                    原始件归档（只读，不再被查询）
│   ├── jibenmian/               季度三表 zcfz_/lrb_/xjll_YYYYMMDD.csv
│   ├── financial/               单股财务指标 financial_report_XXXXXX.csv（87 列全量）
│   ├── stock_statements/        单股三表明细 lrb/ xjll/ zcfz/
│   └── etf/                     ETF 清单（a_etf_list.csv、hangye_etf.csv 等）
├── own/                         个人持仓
└── us/                          美股
```

> 已删除：`data/a/stock/price/`、`data/a/stock/temp/`（890 MB 重复副本）、
> `data/a/stock/price.zip`（316 MB）、`data/a/etf/price/` —— 内容全部已入 `daily_price` / `etf_daily`。

## 表结构

| 表 | 主键 | 说明 |
|---|---|---|
| `meta` | key | schema 版本、迁移时间等 |
| `stock_list` | symbol | 股票代码 + 简称 + 来源 |
| `daily_price` | (symbol, date) | A 股日线，不复权与复权并存 |
| `etf_daily` | (symbol, date) | ETF 日线（只有前复权） |
| `fundamental` | (symbol, season) | 季度基本面（三表合并） |
| `fundamental_growth` | (symbol, season) | 单季收入/利润及其同比 |
| `financial_indicator` | (symbol, report_date) | 财务指标（精选 29 列 + TTM） |
| `trade_record` | id | 选股/交易记录 |

所有表都是 `WITHOUT ROWID`（避免额外的 rowid 与主键索引开销）。

### daily_price

| 列 | 含义 |
|---|---|
| symbol / date / idate | 代码 / `YYYY-MM-DD` / `YYYYMMDD` 整数 |
| open/high/low/close | **不复权**价格 |
| open_qfq/high_qfq/low_qfq/close_qfq | **前复权**价格 |
| volume / turnover | 成交量 / 成交额 |
| amplitude / pct_change / price_change / turnover_rate | 振幅 / 涨跌幅 / 涨跌额 / 换手率 |

> ⚠️ 方向容易记反：库里不带后缀的是**不复权**。
> 对外函数 `get_stock_price()` 为了兼容旧语义做了反转：
> 返回的 `open/high/low/close` 是**前复权**，`*_org` 是**不复权**，并额外给出显式的 `*_qfq`。

### fundamental

按「资产负债表 / 利润表 / 现金流量表」顺序排列的英文列（见 `quant/data/schema.py`）：

- 资产负债：`cash`、`accounts_receivable`、`inventory`、`total_assets`、`total_assets_yoy`、
  `accounts_payable`、`advance_receipts`、`total_liabilities`、`total_liabilities_yoy`、`debt_ratio`、`total_equity`
- 利润：`net_profit`、`net_profit_yoy`、`total_revenue`、`total_revenue_yoy`、
  `operating_cost`、`selling_expense`、`admin_expense`、`finance_expense`、`total_operating_expense`、`operating_profit`、`total_profit`
- 现金流：`net_cash_flow`、`net_cash_flow_yoy`、`operating_cash_flow`(`_ratio`)、`investing_cash_flow`(`_ratio`)、`financing_cash_flow`(`_ratio`)
- 文本：`name`、`ann_date_bs`、`ann_date_is`、`ann_date_cf`

合并口径与原实现一致：**三张表都要出现的股票才保留**（inner join）。

### fundamental_growth

| 列 | 含义 |
|---|---|
| pre_year_income / season_income / season_income_growth | 去年同季收入 / 当季收入 / 当季收入同比(%) |
| pre_year_profit / season_profit / season_profit_growth | 去年同季利润 / 当季利润 / 当季利润同比(%) |

计算规则：
- 当季收入 = 本期累计 − 上季累计；一季报直接取累计值
- 去年同季值 = 本期累计 ÷ (1 + 报表同比/100)
- 当季同比 = (当季值 ÷ 去年同季值 − 1) × 100；一季报直接取报表同比
- 缺上一季度数据时结果为 NaN（旧实现会抛异常）

### financial_indicator

从 87 列的 `financial_report` 中精选 29 列入库（`eps_diluted`、`bvps_after`、`roe`、`gross_margin`、
`debt_ratio`、`total_assets` 等），并新增两列 TTM：

- `eps_ttm`  = TTM(摊薄每股收益)
- `bvps_ttm` = TTM(每股净资产_调整后)

完整 87 列数据仍保留在 `data/original/financial/`。

## 常用查询

```python
from quant.data import store
from quant.price.loader import get_stock_price, get_full_price, get_etf_price
from quant.foundation.growth import compute_growth

with store.open_db() as conn:
    # 单只股票日线（前复权在 close，不复权在 close_org）
    df = get_stock_price("000001", conn=conn)

    # 带 PE / PB
    df = get_full_price("000001", conn=conn)

    # 某季度全市场基本面
    fund = store.read_fundamental(conn, 20231231, 20231231)

    # 单季增长
    growth = store.read_growth(conn, 20230101)

    # 各表行数
    print(store.stats(conn))
```

## 更新策略

| 命令 | 行为 |
|---|---|
| `quant update-jibenmian` | 只下载归档区缺失的季度文件，然后**增量**摄入（已入库的季度自动跳过） |
| `quant update-price` | 逐只股票从「库中最后一个交易日 + 1 天」接着拉；`--mode full` 整段重拉 |
| `quant update-etf` | 同上，标的为内置 ETF 池 |
| `quant rebuild-growth` | 从 `fundamental` 全量重算 `fundamental_growth` |
| `quant update-all` | 以上按顺序执行 |

所有更新都是幂等的（`INSERT OR REPLACE`），中断后重跑即可续上。
