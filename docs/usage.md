# 数据使用说明（阶段 2.2）

> 数据已经从「每只股票两个 CSV」迁移到 **SQLite**（`data/quant.db`）。
> 表结构与字段含义见 [data_model.md](data_model.md)。

## 一、首次迁移（已完成，保留备查）

如果你从旧版本升级，或换机器后拿到的是旧的 CSV 目录树：

```bat
.venv\Scripts\python.exe -m quant db-init                  :: 建库
.venv\Scripts\python.exe -m quant db-migrate               :: CSV -> SQLite（可重复执行）
.venv\Scripts\python.exe -m quant db-migrate --archive     :: 原始 CSV 归档到 data/original/
.venv\Scripts\python.exe -m quant db-migrate --cleanup     :: 先看会删什么（dry-run）
.venv\Scripts\python.exe -m quant db-migrate --cleanup --yes   :: 确认后真正删除
```

- `db-migrate` 是**幂等**的：已经进库的股票/季度会自动跳过，中断后重跑即可续上。
- `--cleanup` 删除的是已入库的行情 CSV、`data/a/stock/temp/` 重复副本与 `price.zip`，
  默认只做演练，必须显式加 `--yes` 才真正删除。

## 二、追加最新数据

### 1. 季度基本面

```bat
.venv\Scripts\python.exe -m quant update-jibenmian
.venv\Scripts\python.exe -m quant update-jibenmian --from-year 2024 --to-year 2024
.venv\Scripts\python.exe -m quant update-jibenmian --tables zcfz --force
```

流程：**只下载归档区里缺失的季度文件** → 落盘到 `data/original/jibenmian/` →
按季度增量摄入 `fundamental` 表（已入库的季度自动跳过）。

> 之后记得重算派生表：`quant rebuild-growth`

### 2. 日线

```bat
.venv\Scripts\python.exe -m quant update-price                       :: 全市场增量
.venv\Scripts\python.exe -m quant update-price --stock 000001 600519
.venv\Scripts\python.exe -m quant update-price --limit 20            :: 试跑
.venv\Scripts\python.exe -m quant update-price --mode full           :: 整段重拉
```

- **增量**：对每只股票查库中最后一个交易日，从**次日**开始拉，只写新增区间。
- **full**：从 `--start`（默认 20100101）整段重拉。当前复权因子发生变化后需要执行。
- 每只股票之间默认间隔 0.3 秒（`--delay`），全市场约 5000 只，增量通常几分钟到十几分钟。

### 3. ETF

```bat
.venv\Scripts\python.exe -m quant update-etf
.venv\Scripts\python.exe -m quant update-etf --symbol 512480
```

### 4. 一键

```bat
.venv\Scripts\python.exe -m quant update-all
```

顺序：季度基本面 → 增长表 → 日线 → ETF。

## 三、读取数据

```python
from quant.data import store
from quant.price.loader import get_stock_price, get_full_price, get_etf_price
from quant.foundation.growth import compute_growth, rm_broken_stocks

# 单只股票日线：close 是前复权，close_org 是不复权（沿用重构前语义）
df = get_stock_price("000001")

# 带 PE / PB（date 作为索引）
df = get_full_price("000001")

# 指定区间（YYYYMMDD 整数边界）
df = get_stock_price("000001", start=20230101, end=20231231)

with store.open_db() as conn:
    fund = store.read_fundamental(conn, 20230101, 20231231)      # 季度基本面
    fund = store.read_fundamental(conn, symbols=["000001"])       # 指定股票
    growth = store.read_growth(conn, 20230101)                    # 单季增长
    etf = store.read_etf_price(conn, "512480")                     # ETF
    fin = store.read_financial(conn, "000001")                     # 财务指标
```

### 字段方向提醒

| 场景 | 用哪一列 |
|---|---|
| 回测 / 技术指标 | `open/high/low/close`（**前复权**） |
| 计算真实市值、估值 | `close_org`（**不复权**） |
| 与旧代码兼容 | `*_org` = 旧实现的原始价，`open/close/...` = 旧实现的前复权价 |

## 四、导出单季增长

```bat
.venv\Scripts\python.exe -m quant calc-growth --from-year 2021
.venv\Scripts\python.exe -m quant calc-growth --from-year 2021 --legacy-columns
```

口径与重构前的 `calc_a_growth` 一致：读取指定起始年之后的季度 → 剔除季度不全的股票 →
计算单季增长 → 导出 CSV（utf_8_sig）。

| 列 | 含义 |
|---|---|
| `pre_year_income` / `season_income` / `season_income_growth` | 去年同季收入 / 当季收入 / 当季收入同比(%) |
| `pre_year_profit` / `season_profit` / `season_profit_growth` | 去年同季利润 / 当季利润 / 当季利润同比(%) |

## 五、数据体检

```bat
.venv\Scripts\python.exe -m quant check
```

输出：各表行数、日线覆盖（股票数 + 日期区间）、基本面覆盖（股票数 + 季度区间）、
`schema_version`、归档区各目录的文件数与大小。

## 六、配置

优先级：**真实环境变量 > `.env` 文件 > 代码默认值**。见 `.env.example`。

| 变量 | 默认值 | 说明 |
|---|---|---|
| `QUANT_DATA_DIR` | `<项目根>/data` | 数据根目录 |
| `QUANT_DB_PATH` | `<DATA_DIR>/quant.db` | SQLite 主库 |
| `QUANT_ORIGINAL_DIR` | `<DATA_DIR>/original` | 原始 CSV 归档 |
| `QUANT_LOG_LEVEL` | `INFO` | 日志级别 |
