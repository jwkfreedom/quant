# quant

A 股 / 美股**选股研究工具**，同时提供 **backtrader 策略回测**能力。

> 重构状态：**阶段 2.1 完成**（依赖清单 + 包结构 + 统一入口）。
> 详见 [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md)。

## 快速开始

**环境已经建好**，直接自检即可（不需要 pwsh）：

```bat
scripts\verify.bat                         :: 一键自检（info + check + pytest）
```

或在任意命令行窗口（cmd / Windows PowerShell / PowerShell 7）里逐步执行：

```bat
.venv\Scripts\python.exe -m quant info     :: 配置 + 依赖自检
.venv\Scripts\python.exe -m quant check    :: 数据目录体检
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

安装完成后（`pip install -e .`）也可以直接用 `quant` 命令：
```bat
.venv\Scripts\quant.exe check
```

## 常用命令

| 命令 | 作用 |
|---|---|
| `quant info` | 打印配置与依赖自检 |
| `quant check` | 数据目录体检（季度覆盖、缺失的价格文件） |
| `quant download-jibenmian --start-year 2023 --end-year 2024` | 下载全市场季度基本面（业绩快报） |
| `quant calc-growth --from-year 2021` | 合并三表并计算单季增长，导出 CSV |
| `quant download-price --mode cur` | 追加今年日线 |
| `quant download-price --mode yearly` | 重下全部历史日线（较慢） |
| `quant download-price --stock 000001 600519` | 指定股票 |
| `quant download-etf --start 20180101 --end 20230201` | 下载 ETF 日线 |
| `quant download-us` | 下载知名美股清单 |

## 目录结构

```
quant/                  主包（唯一可导入代码）
├── config.py           配置：环境变量 > .env > 默认值
├── cli.py              统一命令行入口
├── data/               数据采集与落盘
│   ├── download_a.py   A股：季度三表 / 日线 / ETF
│   ├── download_us.py  美股
│   ├── stockapi.py     雪球、东财 HTTP 接口
│   ├── fsutil.py       数据目录维护工具
│   └── universe.py     标的池常量（ETF 列表等）
├── foundation/         基本面
│   ├── season.py       季报日期工具
│   ├── growth.py       三表合并、单季增长
│   └── financial.py    TTM、财务指标修补、PE/PB
├── price/loader.py     日线读取 + 估值
├── strategy/           backtrader 策略（ma_obv / volume_breakout）
├── filter/             可插拔选股过滤器（2.3 实装）
├── trade/              选股/交易记录（records.csv + records.py）
└── ui/                 桌面界面（2.4 实装）

data/                   数据仓库（git 忽略）
├── a/jibenmian/        季度三表 zcfz_/lrb_/xjll_YYYYMMDD.csv
├── a/stock/
│   ├── price/          日线 price_XXXXXX_pre.csv / _cur.csv
│   ├── financial/      主要财务指标 financial_report_XXXXXX.csv
│   └── lrb|xjll|zcfz/  单股三表明细
├── a/etf/              ETF 清单与日线
├── own/                个人持仓
└── us/                 美股

research/               研究草稿（非库代码，见其 README）
notebooks/legacy/       重构前的 notebook 归档
study/                  学习笔记（保留）
docs/                   文档
tests/                  pytest 单测
scripts/bootstrap.ps1   环境重建脚本
tools/sandbox/          DSH 沙箱兼容补丁（自动复制进 venv）
```

## 数据流

```
quant download-jibenmian            quant download-price
        |                                   |
        v                                   v
data/a/jibenmian/*.csv            data/a/stock/price/*.csv
        |                                   |
        v                                   v
foundation.load_jibenmian         price.loader.get_stock_price
foundation.rm_broken_stocks                   |
foundation.growth_score                       v
        |                          price.loader.get_full_price
        v                          (+ financial_report -> PE/PB)
quant calc-growth                             |
        |                                     v
        v                            strategy / trade / notebooks
<DATA_DIR>/<year>01-lastseason.csv
```

## 开发

```powershell
.venv/Scripts/python.exe -m pytest          # 运行单测
.venv/Scripts/python.exe -m quant --help    # 查看命令
```

- 内部数据列名统一使用**英文**，中文只出现在展示层（`quant/ui`）。
- 所有入口必须走 `quant/cli.py`，禁止模块级副作用（import 即执行）。
- 路径统一取自 `quant.config`，不要写相对路径。

## 路线图

| 阶段 | 内容 | 状态 |
|---|---|---|
| 2.1 | 依赖清单 + 包结构 + 统一入口 | 完成 |
| 2.2 | 数据稳定化：英文 schema、SQLite 主库、original 归档、增量更新 | 待开始 |
| 2.3 | 主要功能接口：选股过滤链、基本面/行情查询、回测入口 | 待开始 |
| 2.4 | 桌面 UI（显示层中文映射） | 待开始 |
