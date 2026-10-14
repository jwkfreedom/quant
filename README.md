# quant

A 股 / 美股**选股研究工具**，同时提供 **backtrader 策略回测**能力。

> 重构状态：**阶段 2.4 进行中**（桌面界面 + 估值历史分位）。
> 详见 [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md) 与 [docs/data_model.md](docs/data_model.md)。

## 快速开始

**环境已经建好**，直接自检即可（不需要 pwsh）：

```bat
scripts\verify.bat                         :: 一键自检（info + check + pytest）
```

或在任意命令行窗口（cmd / Windows PowerShell / PowerShell 7）里逐步执行：

```bat
.venv\Scripts\python.exe -m quant info     :: 配置 + 依赖自检
.venv\Scripts\python.exe -m quant check    :: 数据体检（数据库 + 归档区）
.venv\Scripts\python.exe -m pytest         :: 单测
```

**需要在别的机器/重建环境时**：

```bat
scripts\bootstrap.bat                       :: 双击或命令行运行均可
:: 等价于： powershell -NoProfile -ExecutionPolicy Bypass -File scripts\bootstrap.ps1
```

> 需要 **Python 3.11**：脚本会优先用项目内的 `.python/python/python.exe`，
> 其次找 PATH 上的 `python`；也可以用 `-PythonExe <路径>` 指定。

配置数据目录（可选，默认 `<项目根>/data`）：

```bat
copy .env.example .env
```

## 常用命令

### 查看与自检

| 命令 | 作用 |
|---|---|
| `quant info` | 配置与依赖自检 |
| `quant check` | 数据体检：各表行数、覆盖区间、归档区大小、schema 版本 |
| `quant db-stats` | 只看各表行数 |

### 数据库维护

| 命令 | 作用 |
|---|---|
| `quant db-init` | 建库建表（幂等） |
| `quant db-migrate` | 历史 CSV → SQLite（可重复执行，自动跳过已迁移部分） |
| `quant db-migrate --archive` | 迁移后把原始 CSV 归档到 `data/original/` |
| `quant db-migrate --cleanup --yes` | 归档后删除已入库的行情 CSV（不可逆，会先打印将释放的空间） |

### 追加最新数据

| 命令 | 作用 |
|---|---|
| `quant update-jibenmian` | 补齐缺失季度并增量摄入（默认从库中最新季度往后） |
| `quant update-jibenmian --from-year 2024 --to-year 2024` | 指定年份区间 |
| `quant update-price` | 全市场日线增量更新（从库中最后交易日往后） |
| `quant update-price --stock 000001 600519` | 指定股票 |
| `quant update-price --mode full` | 整段重拉（前复权因子变化后需要） |
| `quant update-etf` | ETF 日线增量更新 |
| `quant update-financial` | 财务指标增量更新（逐股，较慢，建议后台跑） |
| `quant update-all` | 按顺序执行以上全部 |
| `quant rebuild-growth` | 从 `fundamental` 全量重算单季增长表 |

### 选股与回测

| 命令 | 作用 |
|---|---|
| `quant screen --list` | 列出所有可用过滤器 |
| `quant screen --filter exclude_st --filter market_cap:max=80` | 按过滤链选股，打印每一步剩余数量 |
| `quant screen --filter growth:min=30 --sort market_cap --out picks.csv` | 排序并导出 CSV |
| `quant screen --display-columns` | 输出列名用中文展示名 |
| `quant backtest --list` | 列出所有可用策略 |
| `quant backtest --strategy ma_obv --symbol 512480` | 运行回测（收益率/回撤/夏普/胜率） |
| `quant backtest --strategy ma_obv --ma-period 10` | 带参数回测 |

### 桌面界面

```bat
scripts\run_ui.bat          :: 双击启动
.venv\Scripts\python.exe -m quant ui          :: 或命令行启动
.venv\Scripts\python.exe -m quant ui 000001   :: 启动后直接打开某只股票
```

六个页面：**数据总览**（新鲜度 + 一键更新）、**选股筛选**（条件编辑 + 结果 + 方案保存）、
**个股分析**（K线 / 估值带 / 财务 / 估值历史 / 原始数据）、**策略回测**（参数表单 + 净值曲线 + 成交明细）、
**数据浏览器**（任意表分页 + 导出）、**设置/关于**。设计稿见 [docs/ui_design.md](docs/ui_design.md)。

### 估值历史分位

```bat
quant rebuild-valuation --windows 3 5 10 0 --workers 4   :: 重建 PE/PB/PS 历史分位
quant rebuild-ttm                                        :: 回填 fundamental 的 TTM 列
```

分位含义：窗口内「估值低于当前」的交易日占比。分位 ≤ 10 表示当前处于窗口内最低的 10%。

### 导出

| 命令 | 作用 |
|---|---|
| `quant calc-growth --from-year 2021` | 导出单季增长 CSV（与旧 `calc_a_growth` 同口径） |
| `quant calc-growth --legacy-columns` | 导出旧版中文列名 |

## 目录结构

```
quant/                    主包（唯一可导入代码）
├── config.py             配置：环境变量 > .env > 默认值
├── cli.py                统一命令行入口
├── query.py              统一查询 API（快照 / 行情 / 基本面 / 增长）
├── data/                 数据层
│   ├── schema.py         数据契约：英文列名 + 中文展示名映射
│   ├── store.py          SQLite 建表 / 读写 / 查询
│   ├── frames.py         原始表 -> 可写库结构的规范化
│   ├── migrate.py        一次性 CSV -> SQLite 迁移 + 归档 + 清理
│   ├── update.py         增量更新（基本面 / 日线 / ETF / 派生表）
│   ├── download_a.py     A 股取数（akshare）
│   ├── download_us.py    美股取数
│   ├── stockapi.py       雪球、东财 HTTP 接口
│   └── universe.py       标的池常量（ETF 列表等）
├── foundation/           基本面
│   ├── season.py         季报日期工具
│   ├── growth.py         季度读取、单季增长（向量化）
│   └── financial.py      TTM、每股净资产修补、PE/PB
├── price/loader.py       日线读取 + 估值
├── filter/               可插拔选股过滤器
│   ├── base.py           Filter 协议 + FilterContext（快照/历史缓存）
│   ├── builtin.py        14 个内置过滤器
│   └── chain.py          过滤链 + 结果报告
├── strategy/             backtrader 策略 + 统一回测入口
│   ├── runner.py         cerebro 装配、BacktestResult、指标提取
│   ├── ma_obv.py         均线 + OBV
│   └── volume_breakout.py 缩量买入
├── trade/                选股/交易记录（records.py + records.csv）
└── ui/                   桌面界面（wxPython）
    ├── viewmodels.py     取数/过滤/导出（纯 pandas，可无头单测）
    ├── charts.py         数据 -> matplotlib Figure
    ├── widgets.py        表格/图表面板/指标卡/后台任务
    ├── screens/          六个页面
    └── app.py            主窗口与导航

data/                     数据仓库（git 忽略）
├── quant.db              SQLite 主库（唯一查询入口）
├── original/             原始件归档（jibenmian / financial / stock_statements / etf）
├── own/                  个人持仓
└── us/                   美股

research/                 研究草稿（非库代码，见其 README）
notebooks/legacy/         重构前的 notebook 归档
study/                    学习笔记（保留）
docs/                     文档（PROJECT_STATUS / data_model / usage / ...）
tests/                    pytest 单测
scripts/bootstrap.bat     环境重建（一键）
tools/sandbox/            沙箱兼容补丁（自动复制进 venv）
```

## 数据流

```
                        ┌──────────────── akshare ────────────────┐
                        │                                          │
             quant update-jibenmian                     quant update-price / update-etf
                        │                                          │
                        v                                          v
        data/original/jibenmian/*.csv                    （直接入 daily_price / etf_daily）
                        │                                          │
                        └──────────> SQLite (data/quant.db) <──────┘
                                          │
        ┌─────────────────────────────────┼──────────────────────────────────┐
        v                                 v                                  v
store.read_fundamental          price.loader.get_stock_price      store.read_etf_price
foundation.compute_growth       price.loader.get_full_price               │
        │                        （+ financial_indicator -> PE/PB）       v
        v                                 │                         strategy/ma_obv
fundamental_growth                        v
        │                        strategy / trade / notebooks / filter
        v
quant calc-growth -> CSV
```

> 详细表结构与字段说明见 [docs/data_model.md](docs/data_model.md)。

## 开发

```bat
.venv\Scripts\python.exe -m pytest          :: 运行单测
.venv\Scripts\python.exe -m quant --help    :: 查看命令
```

约定：

- 内部数据列名统一使用**英文**，中文只出现在展示层（`quant/data/schema.py` 的 `DISPLAY_NAMES` / `rename_for_display()`）。
- 所有入口必须走 `quant/cli.py`，禁止模块级副作用（import 即执行）。
- 路径统一取自 `quant.config`；SQLite 路径为 `QUANT_DB_PATH`，默认 `<DATA_DIR>/quant.db`。
- 原始 CSV 一律落到 `data/original/`，不要新建 `data/a/...` 目录树。

## 路线图

| 阶段 | 内容 | 状态 |
|---|---|---|
| 2.1 | 依赖清单 + 包结构 + 统一入口 | 完成 |
| 2.2 | 数据稳定化：英文 schema、SQLite 主库、original 归档、增量更新 | 完成 |
| 2.3 | 主要功能接口：选股过滤链、基本面/行情查询、回测入口 | 完成 |
| 2.4 | 桌面 UI（显示层中文映射） | 进行中：界面与底层已就绪 |

参考文档：[docs/filter_guide.md](docs/filter_guide.md)（过滤器指南）、
[docs/data_model.md](docs/data_model.md)（数据模型）、
[docs/usage.md](docs/usage.md)（使用说明）。
