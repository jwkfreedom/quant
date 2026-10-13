# 数据使用说明

> 本手册对应阶段 2.1 之后的代码结构。命令统一走 `quant` CLI。

## 一、数据准备

### 1. 下载季度基本面（业绩快报）

```powershell
quant download-jibenmian --start-year 2023 --end-year 2024           # 全年四个季度
quant download-jibenmian --start-year 2023 --end-year 2024 --season 0331 0630
quant download-jibenmian --tables zcfz --start-year 2023 --end-year 2024
```

- 落盘：`data/a/jibenmian/{zcfz|lrb|xjll}_YYYYMMDD.csv`
- `zcfz` 资产负债表 / `lrb` 利润表 / `xjll` 现金流量表
- 每下载一个季度会 sleep 3 秒，全年 3 张表大约 12 次请求

### 2. 计算基本面单季增长

```powershell
quant calc-growth --from-year 2021
quant calc-growth --from-year 2021 --out data/202101-lastseason.csv
```

流程：`load_jibenmian` 合并三表 → `rm_broken_stocks` 剔除数据不全的股票 →
`growth_score` 计算单季收入/利润与同比 → 导出 CSV（utf_8_sig，带 BOM）。

导出时间范围：从指定年的 1 月 1 日到**上个季度**（今天往前 90 天）。

新增字段：

| 字段 | 含义 |
|---|---|
| preYearIncome | 去年同季收入 |
| SeasonIncome | 当季收入 |
| SeasonIncomeGrowth | 当季收入同比（%） |
| preYearProfit | 去年同季利润 |
| SeasonProfit | 当季利润 |
| SeasonProfitGrowth | 当季利润同比（%） |

### 3. 下载日线数据

```powershell
quant download-price --mode yearly     # 一年执行一次：归档旧文件并下载全部历史
quant download-price --mode cur        # 年内日常更新：只下载今年
quant download-price --stock 000001   # 单只
```

- `price_XXXXXX_pre.csv`：今年（不含）以前的数据
- `price_XXXXXX_cur.csv`：今年的数据
- 每个文件都同时包含**不复权**列和 **qfq 前复权**列（`开盘_qfq` 等）
- 归档动作会把 `price/` 中同类文件移动到 `data/a/stock/temp/`

### 4. 全市场股票池的来源

`all_a_stocks()` 读取 `data/a/jibenmian/` 下**最新的 zcfz 季度文件**的「股票代码」列。

> 所以下载日线前请先确保季度基本面数据足够新（一般选半年内的季度）。

## 二、数据使用

| 模块 | 函数 | 内容 |
|---|---|---|
| `quant.price.loader` | `get_stock_price(symbol)` | 单只股票日线（pre + cur 拼接，前复权覆盖 + `*_org` 原始价） |
| `quant.price.loader` | `get_full_price(symbol)` | 日线 + PE/PB，date 作为索引 |
| `quant.foundation.growth` | `load_jibenmian(season_start)` | 合并多季度三表 |
| `quant.foundation.growth` | `growth_score(df)` | 单季增长 |
| `quant.foundation.season` | `get_seasondate` / `pre_year_season` / `get_season_iDATE` | 季报日期工具 |

```python
from quant.price.loader import get_stock_price, get_full_price

df = get_stock_price("000001")     # 日线
df = get_full_price("000001")      # 日线 + PE/PB
```

> **注意**：`get_stock_price` 要求 `price/{symbol}_pre.csv` 与 `_cur.csv` **同时存在**，
> 缺失会直接抛 FileNotFoundError。用 `quant check` 可以查看哪些股票缺文件。

## 三、数据体检

```powershell
quant check
```

输出：基本面各表的文件数与季度区间、日线 pre/cur 数量、只有 cur 的股票（这些股票读不了）、
financial 与 etf 文件数。

## 四、配置

优先级：**真实环境变量 > `.env` 文件 > 代码默认值**。见 `.env.example`。

| 变量 | 默认值 | 说明 |
|---|---|---|
| `QUANT_DATA_DIR` | `<项目根>/data` | 数据根目录 |
| `QUANT_DB_PATH` | `<DATA_DIR>/quant.db` | SQLite 主库（阶段 2.2） |
| `QUANT_ORIGINAL_DIR` | `<DATA_DIR>/original` | 原始 CSV 归档（阶段 2.2） |
| `QUANT_LOG_LEVEL` | `INFO` | 日志级别 |
