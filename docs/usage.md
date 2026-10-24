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

### 4. 财务指标（逐股）

```bat
:: 只更新「最新报告期早于 180 天前或没有数据」的股票（推荐）
.venv\Scripts\python.exe -m quant update-financial --stale-days 180 --workers 4 --delay 0.2

:: 指定股票
.venv\Scripts\python.exe -m quant update-financial --stock 000001 600519

:: 全市场（较慢，约 1~2 小时）
.venv\Scripts\python.exe -m quant update-financial --workers 4
```

- 单只请求约 2~2.5 秒（新浪接口按年份逐年取数），`--workers` 控制并发抓取线程
  （写库仍是单线程）；并发过高会被限流、接口返回空表，建议不超过 4。
- 每 100 只提交一次，随时可中断重跑；库中已是最新报告期的股票会自动跳过。
- 进度看日志里的 `财务指标进度 N/总数`，不要看「有 TTM 的股票数」（跳过的不会变化）。

### 5. 一键

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

## 五、选股

```bat
:: 查看所有过滤器
.venv\Scripts\python.exe -m quant screen --list

:: 选股（过滤器可重复，格式 name 或 name:k=v,k=v）
.venv\Scripts\python.exe -m quant screen ^
    --filter exclude_st ^
    --filter min_listing:bars=250 ^
    --filter market_cap:max=200 ^
    --filter growth:field=season_income_growth,min=20 ^
    --filter price_change:bars=20,min=0 ^
    --limit 20 --sort market_cap --out picks.csv

:: 指定快照日期 / 中文列名导出
.venv\Scripts\python.exe -m quant screen --filter pe:max=15 --as-of 20231229 --display-columns
```

输出会先打印每一步过滤掉了多少只，再打印结果表。完整说明见
[filter_guide.md](filter_guide.md)。

Python 里等价写法：

```python
from quant.filter import FilterChain, FilterContext

with FilterContext(as_of=20231229) as ctx:
    result = FilterChain.from_specs([
        "exclude_st",
        "market_cap:max=200",
        "growth:field=season_income_growth,min=20",
    ]).run(ctx)

print(result.report())
df = result.frame
```

## 六、回测

```bat
.venv\Scripts\python.exe -m quant backtest --list
.venv\Scripts\python.exe -m quant backtest --strategy ma_obv --symbol 512480 --cash 100000
.venv\Scripts\python.exe -m quant backtest --strategy volume_breakout --symbol 000001 --plot
```

输出统一为：区间、初始资金、最终市值、总收益率、最大回撤、交易次数、胜率。

Python 里：

```python
from quant.strategy import run_backtest

result = run_backtest("ma_obv", symbol="512480", cash=100000, commission=0.001)
print(result.report())
```

注册自己的策略（runner 需返回 `BacktestResult`）：

```python
from quant.strategy import register_strategy

def my_runner(symbol, cash=100000.0, commission=0.001, plot=False):
    ...
    return result

register_strategy("my_strategy", my_runner, default_symbol="000001", description="我的策略")
```

## 七、估值历史分位（PE/PB/PS）

```bat
:: 先补齐 TTM 列（PS 依赖），再重建分位表
.venv\Scripts\python.exe -m quant rebuild-valuation --windows 3 5 10 0 --workers 4
```

**口径**：

- `PE_t = 不复权收盘价_t ÷ eps_ttm(t)`，`eps_ttm(t)` 取 t 时点已披露的最近报告期
- **分位 = 窗口内「估值低于当前」的交易日占比**；分位 ≤ 10 表示当前处于窗口内最低的 10%
- 剔除 `PE ≤ 0`（亏损期）与指标缺失的交易日
- 窗口 3 / 5 / 10 年与全历史（`0`），默认用 10 年

跑完后快照里会多出 `pe_pct_3y / pe_pct_5y / pe_pct_10y / pe_pct_all / pb_pct_10y / ps_pct_10y`，
可以直接用于筛选：

```bat
.venv\Scripts\python.exe -m quant screen ^
    --filter exclude_st ^
    --filter pe_percentile:window_years=10,max=10 ^
    --filter pb_percentile:window_years=10,max=20 ^
    --filter roe:min=8
```

> 建议在每次更新完行情与财务指标之后重建一次；`--stock` 可以只算指定股票，方便增量。

## 八、桌面界面

```bat
scripts\run_ui.bat                              :: 双击启动
.venv\Scripts\python.exe -m quant ui            :: 命令行启动
.venv\Scripts\python.exe -m quant ui 000001     :: 启动后直接打开某只股票
```

| 页面 | 用途 |
|---|---|
| 数据总览 | 数据新鲜度、数据量、一键更新（后台执行） |
| 选股筛选 | 勾选条件 → 运行 → 看每步剩余数量 → 保存方案 / 导出 / 复制等价命令 |
| 个股分析 | K线、估值带（PE 分位通道）、财务、估值历史、原始数据（可导出） |
| 策略回测 | 策略与参数表单 → 收益/回撤/夏普 + 净值曲线 + 成交明细 |
| 数据浏览器 | 浏览行情库/资产库的全部用户表、按代码/日期/单列条件过滤、CSV / Excel 导出 |
| 设置/关于 | 路径、依赖版本、筛选方案目录 |

筛选方案保存在 `config/screens/*.json`（可用环境变量 `QUANT_SCREENS_DIR` 改路径）。

## 九、数据体检

```bat
.venv\Scripts\python.exe -m quant check
```

输出：各表行数、日线覆盖（股票数 + 日期区间）、基本面覆盖（股票数 + 季度区间）、
`schema_version`、归档区各目录的文件数与大小。

## 十、配置

优先级：**真实环境变量 > `.env` 文件 > 代码默认值**。见 `.env.example`。

| 变量 | 默认值 | 说明 |
|---|---|---|
| `QUANT_DATA_DIR` | `<项目根>/data` | 数据根目录 |
| `QUANT_DB_PATH` | `<DATA_DIR>/quant.db` | SQLite 主库 |
| `QUANT_ORIGINAL_DIR` | `<DATA_DIR>/original` | 原始 CSV 归档 |
| `QUANT_LOG_LEVEL` | `INFO` | 日志级别 |
