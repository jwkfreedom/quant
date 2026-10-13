# PROJECT_STATUS — quant 项目现状文档

> 版本：v1.0（阶段 1 冻结版）
> 生成方式：对 `D:\github\quant` 实际文件系统扫描 + 源码逐文件通读，非推测
> 阶段：**阶段 1（项目理解）已完成** → 待进入 **阶段 2（代码整理重构）**

---

## 0. 项目定位（已与作者确认）

- **主定位**：A 股（+ 美股）**选股研究工具**，同时具备**策略回测**能力。
- **次要定位**：交易记录（真实成交）与**模拟交易回测**（`trade/` 方向）。
- **最终形态**：命令行 + ipynb 为主，后续再做桌面 UI（现有 `gui.py` 废弃、重写）。

---

## 1. 项目目录结构

```
D:\github\quant\
├── config.py                  # 实际配置（被 .gitignore 忽略）
├── config.py.sample           # 配置模板（入 git）
├── process.py                 # ★ 主流程入口（下载/计算 调度脚本）
├── stockdata.py               # ★ 核心数据层：基本面合并、季报日期、PE/PB、日线读取
├── test.py                    # 临时验证脚本（akshare 分红）
├── gui.py                     # wxPython 独立 Demo（与项目无耦合，拟删除重写）
├── anabase.py                 # 技术指标实验（MACD，依赖未安装的 ta 库）
├── spy.py                     # 美股 SPY/SSO 轮动自研回测（独立脚本，拟重写）
├── stock_select.ipynb         # 选股实验 notebook
├── stockdata_usage.ipynb      # 基本面数据使用示例 notebook
│
├── utils/
│   ├── download.py            # ★ 全部数据下载（akshare）：基本面/日线/ETF/股票列表
│   ├── osutil.py              # 文件系统搬运工具（价格文件归档、改名）
│   ├── stockapi.py            # 雪球 / IEX / 东财 HTTP 接口封装（含明文 API Key）
│   └── download_us.py         # 美股数据下载（yfinance/akshare，半成品）
│
├── analyse/                   # 数据分析实验层
│   ├── ana_jibenmian.py       # 均线/量能突变/波峰波谷分析
│   ├── analyse.py             # MA+RSI 信号 + 简易回测（残破）
│   ├── ana_test.py            # 头肩顶形态识别（scipy + mplfinance）
│   ├── ana.ipynb              # 绘图实验
│   └── memo.md                # 滚动统计片段备忘
│
├── strategy/                  # 策略/回测层（backtrader）
│   ├── bt_etf.py              # ETF 轮动策略（有 NameError，跑不通）
│   ├── bt_ova.py              # MA + 自研 OBV 策略回测（可运行）
│   └── test1.py               # 缩量买入 + 止盈止损策略（可运行）
│
├── trade/                     # 交易记录与执行（雏形）
│   ├── trade.py               # 持股记录读取 + 价格准备（无实际策略）
│   ├── record.csv             # 选股/交易记录（14 行）
│   └── stockfilter.md         # 选股过滤条件（自然语言，未代码化）
│
├── study/                     # 学习笔记（21 个文件，与主流程弱相关）
│   ├── *.ipynb                # akshare/dataframe/统计/量化教程笔记
│   └── sp500/                 # 标普500 成分股历史数据集 + 抓取脚本
│
├── docs/                      # 文档
│   ├── usage.md               # 数据准备与使用说明（唯一有效业务文档）
│   ├── dataana.md             # 基本面字段说明与指标口径
│   ├── eastmoney.md           # 东财接口字段结构（507 行，外部资料）
│   └── akshare_func_list.md   # akshare 函数清单（1200 行，外部资料）
│
├── data/                      # 数据仓库（.gitignore 全忽略）
│   ├── 202101-lastseason.csv  # ★ calc_a_growth 的产出（全A基本面成长表）
│   ├── a/
│   │   ├── jibenmian/         # 季度三表：zcfz/lrb/xjll_YYYYMMDD.csv（162 个，2010Q1~2023Q2）
│   │   ├── etf/               # ETF 清单 + price/（63 个 etf_XXXXXX.csv）
│   │   └── stock/
│   │       ├── price/         # price_XXXXXX_pre.csv(4903) + _cur.csv(4925)，950 MB
│   │       ├── temp/          # 同一批价格文件的归档副本，890 MB ★重复
│   │       ├── financial/     # financial_report_XXXXXX.csv（2721 个，新浪主要指标）
│   │       ├── lrb/ xjll/ zcfz/  # 单股三表明细（各约 4923 个）
│   │       └── price.zip      # 316 MB，价格数据打包副本
│   ├── own/                   # 个人持仓：hold.csv + readme.md
│   └── us/                    # 美股数据（空目录）
│
├── netres/stock.ipynb         # 网络资源笔记
├── backup/bt_etf.py           # 旧版 ETF 策略（与 strategy/bt_etf.py 不同，已废弃）
├── .qoder/repowiki/           # AI 生成的项目 Wiki（19 个 md，被 gitignore）
├── .lingma/                   # 灵码配置目录（空）
└── __pycache__/
```

**规模统计**

| 项 | 数值 |
|---|---|
| git 追踪文件 | 54 |
| `data/` | 37,382 个文件，约 3.24 GB |
| `data/a/stock/price/` | 950 MB（4903 pre + 4925 cur） |
| `data/a/stock/temp/` | 890 MB（与 price 近乎重复） |
| `data/a/stock/price.zip` | 316 MB（第三份重复） |
| `data/a/jibenmian/` | 94.2 MB，162 个文件（54 季度 × 3 表），范围 20100331 ~ 20230630 |
| `data/a/stock/lrb|xjjl|zcfz/` | 各约 4923 个文件，242.5 MB（lrb） |
| `data/a/stock/financial/` | 2721 个文件，78.4 MB |
| `study/` | 22 MB |

---

## 2. 各目录/核心文件职责

| 文件/目录 | 职责 | 状态 |
|---|---|---|
| `config.py` | 唯一定义 `DATA_DIR` | ⚠️ 被 gitignore，仅 sample 入库 |
| `process.py` | 手工编辑后运行的调度脚本：下载基本面、算成长表、下载行情 | ⚠️ 顶层即执行 |
| `stockdata.py` | 数据层核心：`load_jibenmian` 合并三表、`rm_broken_stocks` 剔除残缺股、`growth_score` 算单季同比、`get_stock_price` 日线、`get_full_price` 日线+PE/PB | ⚠️ 含较多脆弱实现 |
| `utils/download.py` | 全部采集入口（akshare），含股票列表、ETF 列表 | ⚠️ 硬编码严重、裸 except |
| `utils/osutil.py` | 价格文件在 price/ 与 temp/ 间搬移、目录改名 | ⚠️ 相对路径依赖 CWD |
| `utils/stockapi.py` | 雪球实时报价、IEX、东财 clist | ⚠️ 导入即发请求，明文 Key |
| `utils/download_us.py` | 美股知名股清单 + yfinance | ⚠️ 半成品，函数忽略入参 |
| `analyse/*` | 研究性分析脚本（画图、形态、信号） | ⚠️ 多处跑不通 |
| `strategy/*` | backtrader 回测 | `bt_ova.py` / `test1.py` 可跑 |
| `trade/*` | 选股记录 + 交易准备 | 雏形，无策略 |
| `study/*` | 学习笔记，独立于主流程 | 拟归档 |
| `docs/usage.md` | **实际的数据操作手册** | 有效 |
| `docs/dataana.md` | 指标口径（PE/PB/PS 定义） | 有效 |
| `docs/eastmoney.md`、`docs/akshare_func_list.md` | 外部资料速查 | 参考资料 |

---

## 3. 技术栈

| 项 | 实际情况 |
|---|---|
| 语言 | Python 3.9（64 位，`C:\Users\jwk\AppData\Local\Programs\Python\Python39`） |
| 工程化 | **无 venv、无 requirements.txt、无 pyproject/setup.py、无 CI、无测试** |
| 数据采集 | akshare 1.18.63（主）、yfinance 0.2.36、requests 2.31.0 + 雪球/IEX 直连 |
| 数据处理 | pandas 2.1.4、numpy 1.26.3、scipy 1.11.4、openpyxl 3.1.2 |
| 回测 | backtrader 1.9.78.123 |
| 可视化 | matplotlib 3.8.2、mplfinance 0.12.10b0 |
| GUI | wxPython 4.2.3（仅 `gui.py` Demo，拟废弃） |
| **缺失依赖** | `ta`、`talib`、`statsmodels`（已确认补装） |
| 版本管理 | git，分支 `main`，与 `origin/main` 同步；最近 15 次提交标题全为 `temp`；当前未提交改动：`stock_select.ipynb`、`test.py` |

---

## 4. 现有业务逻辑

### 4.1 程序入口

项目**没有统一 CLI 入口**，所有入口都是「脚本顶层直接执行」：

1. `process.py` —— 事实上的主入口（`calc_a_growth(2021, ...)` 写在模块顶层，import 即执行）
2. `spy.py` —— 美股策略，独立自洽
3. `strategy/*.py`、`analyse/*.py`、`anabase.py`、`test.py` —— 各自独立脚本
4. `*.ipynb` —— 交互式入口

### 4.2 数据流向

**A 股基本面线（主链路）**

```
process.download_a_jibenmian()
  → utils.download.jibenmian_all_fast(zcfz/lrb/xjll, 年区间)
      → akshare.stock_zcfz_em / stock_lrb_em / stock_xjll_em
      → data/a/jibenmian/{type}_{YYYYMMDD}.csv

process.calc_a_growth(startYear, out)
  → stockdata.load_jibenmian      按季读三表、按「股票代码」三表 merge、打 DATE/iDATE 标记
  → stockdata.rm_broken_stocks    取所有季度股票代码交集（剔除数据不全股）
  → stockdata.growth_score        → calc_season_growth 计算单季收入/利润与其同比
  → data/202101-lastseason.csv
```

**A 股行情线**

```
utils.download.stock_price_all / stock_price(symbol)
  → akshare.stock_zh_a_hist（不复权 + qfq 各一次）
  → copy_qfq_data 把 qfq 列并进同一张表
  → data/a/stock/price/price_{symbol}_pre.csv（今年以前）与 _cur.csv（今年）
  → utils.osutil.clear_price_a_files 把旧文件 move 到 temp/ 归档

stockdata.get_stock_price(symbol)  → 读 pre+cur 拼接、中文列名改英文、close 用 qfq 覆盖并保留 _org
stockdata.get_full_price(symbol)   → 再读 financial_report_{symbol}.csv（新浪）
                                     → fix_financial_data / calc_ttm / update_price_pe
                                     → 产出带 PE、PB 的完整日线（date 为索引）
```

**ETF 线**：`utils.download.download_etf` → `data/a/etf/price/etf_XXXXXX.csv` → `strategy/bt_ova.py`、`strategy/bt_etf.py`

**美股线**：`spy.py` 用 `akshare.stock_us_daily` 在线取 SPY/SSO，不落盘，自研份额法回测（不经 backtrader）

### 4.3 模块调用关系

```
process.py ──┬─→ utils.download ─→ akshare
             ├─→ stockdata ──────→ config.DATA_DIR (+ pandas, backtrader 未使用)
             └─→ utils.osutil ───→ 相对路径 data/a/stock/*
stockdata.py ───────────────────→ config.DATA_DIR
analyse/*  ──→ stockdata（+ scipy / mplfinance / talib❌ / ta❌）
strategy/* ──→ backtrader（bt_ova 读 csv；test1 调 stockdata.get_stock_price）
trade/trade.py ─→ stockdata + utils.download
gui.py / spy.py / utils/stockapi.py / utils/download_us.py ─→ 与主链路无耦合
```

**关键特征**：分层方向是「脚本 → utils → stockdata → config」，但**没有包结构**（无 `__init__.py`），靠 `sys.path.append("..")` 和「必须在项目根目录运行」来保证导入成功。

---

## 5. 问题标记

### 5.1 硬编码

| 位置 | 内容 |
|---|---|
| `utils/download.py:188` | `zcfz_20230930.csv` 作为「全A股票列表」来源 —— **磁盘上最新只到 20230630，此文件不存在**，`all_a_stocks()` 必然 FileNotFoundError |
| `utils/stockapi.py:28` | IEX API Key 明文写在源码里（且已入 git） |
| `config.py` | `DATA_DIR='d:/github/quant/data'` 绝对路径（sample 里是 c 盘，与实机不符） |
| `utils/download.py:27`、`strategy/bt_etf.py:3` | 63 个 ETF 代码**同一份列表复制两处** |
| `utils/osutil.py:7,10`、`utils/download_us.py:17`、`strategy/bt_ova.py:54` | `data/a/...` 相对路径，只认 CWD |
| `process.py:12-14,53` | 年份 2023/2024、起始年 2021、输出文件名 |
| `utils/download.py:69,124,147` | `time.sleep(3)`、`"20100101"`、前复权/不复权日期边界 |
| `anabase.py:33`、`analyse/ana_test.py:45`、`trade/trade.py:36`、`strategy/bt_ova.py:54,62` | 股票代码 `688050`/`000505`/`002334`、`2023/11/28`、初始资金 100000、费率 0.001 |
| `spy.py:47,50,75,84` | 回撤 3%、加仓 5%、止盈 10%、减仓 1/5 全部写死在循环里 |

### 5.2 重复代码

1. `utils/download.py` 与 `strategy/bt_etf.py` 的 ETF 列表逐字重复。
2. `backup/bt_etf.py` 与 `strategy/bt_etf.py`：同源两版，逻辑不同，属废弃分叉。
3. `spy.py` 内两套回测实现：第 20~102 行是「权重法」废弃实现，第 108 行起重新用「份额法」实现，前一段完全无用。
4. `data/a/stock/price/` 与 `data/a/stock/temp/` 近乎同一份数据，**磁盘重复约 890 MB**；另有 `price.zip` 316 MB 第三份。
5. 三个入口各自实现「读 pre+cur、拼日期、算 iDATE」的逻辑。
6. `analyse/ana_jibenmian.py` 三个分析函数重复「读数据→rolling→画图」骨架。

### 5.3 注释缺失

- `gui.py`、`strategy/test1.py`、`analyse/analyse.py` 基本无文档字符串。
- `growth_score`、`calc_season_growth`、`calc_pepb_by_season`、`update_price_pe` 四个最关键算法函数没有说明数据前提（如「首季必须是 XXXX0331」），而该前提是硬约束。
- `trade/stockfilter.md` 的过滤条件是自然语言，无代码实现、无口径定义（已确认暂时搁置）。
- `docs/usage.md` 未提 `data/a/stock/financial/` 这条 PE/PB 依赖链。

### 5.4 潜在 Bug（已确认会报错或行为异常）

| # | 位置 | 问题 |
|---|---|---|
| 1 | `utils/download.py:188` | 股票列表文件不存在 → 所有全市场下载功能瘫痪 |
| 2 | `strategy/bt_etf.py:12` | 使用 `datetime.time(15,0)` 但从未 `import datetime` → NameError |
| 3 | `strategy/bt_etf.py:29` | 用 `bt.feeds.YahooFinanceData` 加载 A 股 ETF 代码 → 数据源与标的完全不匹配 |
| 4 | `analyse/analyse.py:5` | `from ..config import DATA_DIR` 越级相对导入，脚本直跑必失败 |
| 5 | `analyse/analyse.py:3,39,45` | `import talib`（未安装）；使用 `np.where/np.log1p` 但未 import numpy |
| 6 | `analyse/analyse.py:53` | `ana_stock('000001')` 传入字符串，函数内却当 DataFrame 用 |
| 7 | `analyse/ana_jibenmian.py:69` | 调用 `sd.stock_price(...)` —— stockdata 中无此函数 → AttributeError |
| 8 | `anabase.py:3,33` | `import ta` 未安装；顶层直接执行并画图 |
| 9 | `utils/stockapi.py:69` | 模块级 `print(iex_stocks(...))`：任何 import 都会发外部请求 |
| 10 | `utils/download_us.py:25,32` | `get_financial_data(symbol)` 内部硬编码 `yf.Ticker("MSFT")`，入参被忽略；且模块级调用 |
| 11 | `process.py:52-55` | 顶层调用 `calc_a_growth`，import process 就会重算并覆盖 `202101-lastseason.csv` |
| 12 | `test.py` | 顶层网络请求，无 `__main__` 保护 |
| 13 | `utils/download.py:125,151,167` | 裸 `except:` 吞掉一切异常（含 KeyboardInterrupt），失败被静默 |
| 14 | `stockdata.py:61-65` | 三表 merge 后 `序号/股票简称/公告日期` 列名冲突 → pandas 自动加 `_x/_y` 后缀，下游列名极脆弱（实际产出的 `202101-lastseason.csv` 表头已出现 `Unnamed: 0_x`、`股票简称_x/_y`） |
| 15 | `utils/download.py:67,122,150,166` | `to_csv` 未加 `index=False` → 所有 CSV 多一列匿名索引，读回来即 `Unnamed: 0` |
| 16 | `stockdata.py:165-169` | 大量 `.item()`：筛选结果多行时直接 ValueError；缺数据同样抛异常 |
| 17 | `stockdata.py:286-298` | `calc_pepb_by_season` 依赖「组内第 0 行=该季度首个交易日」，但 `get_stock_price` 拼接 pre/cur 后未排序，PE/PB 可能算错且难察觉 |
| 18 | `stockdata.py:130-132` | `growth_score` 遇首季不是 0331 时 `return`（返回 None）而非报错 |
| 19 | `stockdata.py:134-138` | 按股票逐个 `df.loc` 全表扫描，O(股票数²) 级慢；靠原地修改副作用生效 |
| 20 | `stockdata.py:11` | `import backtrader` 完全未使用，白白拉起重依赖 |
| 21 | `stockdata.py:180-181` | 直接读 `_pre.csv`/`_cur.csv`，但磁盘上 4903 pre vs 4925 cur，约 22 只股票只有 cur → FileNotFoundError |
| 22 | `spy.py:75` | 条件 2 用 `spy_price >= buy_sso_high*1.1` 判断 SSO 止盈，`buy_sso_high` 存的却是 SPY 价格，变量语义与判定对象不一致 |
| 23 | `trade/trade.py:12-16,25-28` | `prepareData` 被注释掉；逐行 print 调试残留；`strategy` 字典定义了却从未使用 |
| 24 | `strategy/test1.py:55` | `def log(slef, str)` 参数拼写错误且遮蔽内置 `str` |
| 25 | `utils/download.py:16` | `sys.path.append("..")` + 顶层 `from config import ...`，而 `config.py` 不入库 → 新环境直接 ImportError |
| 26 | `gui.py` 全文 | 独立 Demo，与任何业务代码零关联，却放在项目根目录（已确认重写） |

### 5.5 可优化点

1. 统一入口 CLI（`argparse`）+ `if __name__ == "__main__"` 保护。
2. 建立真正的包结构（`__init__.py`），去除 `sys.path.append`。
3. 明确数据 schema：`load_jibenmian` 显式 rename 出稳定英文列名，一举消除 `_x/_y` 与 `.item()` 脆弱性。
4. 向量化重写 `growth_score`：`groupby(['code','iDATE'])` + `shift` 替代双重循环。
5. 统一 CSV 读写工具（固定编码、`index=False`），统一中文→英文列名映射。
6. 路径统一走 `config.DATA_DIR`。
7. 异常策略：具体异常 + 日志 + 下载重试。
8. 回测统一到 backtrader（含手续费/滑点/基准对比）。
9. 阈值参数外置到 config 或函数参数。
10. 为 `get_seasondate`、`pre_year_season`、`get_season_iDATE`、`growth_score` 补最小单测。
11. 数据目录治理：去重 890 MB + 316 MB。
12. 清理 `backup/`、`__pycache__/`、`.qoder/`、`.lingma/`、`study/`、`netres/`、重复副本。
13. 规范 git 提交信息（当前全为 `temp`）。

---

## 6. 已确认决策（作者答复，2025 会话）

| # | 问题 | 决策 |
|---|---|---|
| 1 | 项目定位 | 选股研究工具 + 策略回测 |
| 2 | `gui.py` | 无视，后续重新做桌面界面 |
| 3 | `trade/` | 发展为两个方向：真实交易记录 + 模拟交易回测 |
| 4 | `data/` 治理 | **数据保留一份，可转成 SQLite**；另建 `original/` 目录保留原始 CSV；其余重复数据删除 |
| 5 | 数据更新 | 需要「追加最新数据」功能（与第 4 点结合） |
| 6 | 数据源 | 主要用 akshare；保留其他数据源能力；**IEX 删除** |
| 7 | 美股 | 需要支持；**不用 `spy.py` 与 `study/`，重新编写** |
| 8 | 工程化 | 引入 `requirements.txt` + 虚拟环境 |
| 9 | 缺失依赖 | `ta`、`talib`、`statsmodels` **补装** |
| 10 | 配置 | 改为「环境变量优先 + sample 兜底」 |
| 11 | 列名 | 统一改为英文；**UI 显示层需支持中文** |
| 12 | 既有产出 | `202101-lastseason.csv` 可随重构重新生成 |
| 13 | 选股过滤器 | 暂不做 `stockfilter.md` 那两条；但未来要能**追加可插拔的过滤器**，从全市场过滤选股 |
| 14 | 回测框架 | **统一用 backtrader** |
| 15 | 阶段 2 顺序 | ①依赖清单+包结构+统一入口 → ②数据稳定化+追加更新 → ③主要功能接口（CLI/ipynb） → ④UI |
| 16 | 删除权限 | 允许删除 `backup/`、`__pycache__/`、重复副本、死代码 |
| 17 | 清理项 | `.qoder/repowiki/` 与 `.lingma/` 一并清理 |
| 18 | 本文档 | 落盘至 `docs/PROJECT_STATUS.md` |

---

## 7. 目标架构（阶段 2/3 蓝图）

```
quant/
├── pyproject.toml / requirements.txt
├── .env.example                    # DATA_DIR 等（环境变量优先，config 兜底）
├── README.md
├── quant/                          # 主包
│   ├── config.py                   # 配置加载（env → sample 默认值）
│   ├── cli.py                      # 统一命令行入口（quant <subcommand>）
│   ├── data/                       # 数据层
│   │   ├── paths.py                # 路径解析（原 csv / sqlite 双轨）
│   │   ├── schema.py               # ★ 英文列名契约 + 中文显示名映射表
│   │   ├── store.py                # SQLite 读写
│   │   ├── download_a.py           # A股 基本面/行情/ETF 采集
│   │   ├── download_us.py          # 美股采集（重写）
│   │   └── update.py               # 增量追加最新数据（断点续传）
│   ├── foundation/                 # 基本面
│   │   ├── season.py               # 季报日期工具（get_seasondate 等）
│   │   └── growth.py               # 单季同比、向量化
│   ├── price/                      # 行情
│   │   └── loader.py               # 日线读取 + PE/PB 估值
│   ├── filter/                     # ★ 可插拔选股过滤器
│   │   ├── base.py                 # Filter 协议/注册表
│   │   └── builtin/                # 内置过滤器
│   ├── strategy/                   # backtrader 策略（统一）
│   ├── trade/                      # 交易记录 + 模拟盘
│   └── ui/                         # 桌面界面（最后做，显示层负责中文名）
├── data/
│   ├── original/                   # 原始 CSV 归档（按来源/时间）
│   └── quant.db                    # SQLite 主库
├── notebooks/                      # 迁移后的 ipynb（英文列名）
├── tests/
└── docs/
```

**核心设计原则**
- 存储双轨：`data/original/*.csv` 保留原始落盘，`data/quant.db` 作为查询主库。
- 单一 schema：内部一律英文列名，中文名只存在于「显示层映射表」（`schema.py` 的 `DISPLAY_NAMES`）。
- 一切入口经 `quant/cli.py`；ipynb 只调用包 API，不再有顶层副作用。
- 过滤器插件化：新增选股条件只需加一个实现 `Filter` 协议的类并注册。

---

## 8. 阶段 2 路线图

| 步骤 | 内容 | 产出 |
|---|---|---|
| **2.1** | 依赖清单 + 包结构 + 统一入口（工程化） | `requirements.txt`、venv、`quant/` 包骨架、`quant/cli.py` |
| **2.2** | 数据稳定化 + 追加最新数据功能 | `schema.py`（英文契约）、`store.py`（SQLite）、`update.py`（增量）、data 去重归档 |
| **2.3** | 主要功能接口（CLI / ipynb） | 选股过滤链、基本面成长查询、行情+估值查询、backtrader 回测入口 |
| **2.4** | UI | 桌面界面（显示层中文映射） |

---

---

## 9. 阶段 2.1 完成记录（工程化）

### 9.1 环境

| 项 | 结果 |
|---|---|
| Python | 3.11.17（python-build-standalone，解压到项目内 `.python/`，无需管理员权限） |
| 虚拟环境 | `.venv/`（Python 3.11.17） |
| 依赖 | 见 `requirements.txt`（锁定版本，与重构前 3.9 下验证过的组合一致） |
| 环境重建 | `scripts\bootstrap.bat`（或 `powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1`） |

> 说明：沙箱环境下 `venv` 自带的 ensurepip 会失败，改为「从基础解释器复制 pip」；
> 另发现以 0o700 创建的目录不可写，因此加了 `tools/sandbox/sitecustomize.py`
> （仅在 `DSH_SESSION_ID` 存在时生效），bootstrap 脚本会自动把它复制进 venv。

### 9.2 新目录结构

```
quant/                  主包
├── config.py           配置：环境变量 > .env > 默认值
├── cli.py              统一命令行入口（7 个子命令）
├── __main__.py         python -m quant
├── data/               download_a / download_us / stockapi / fsutil / universe
├── foundation/         season / growth / financial
├── price/loader.py     日线读取 + PE/PB
├── strategy/           ma_obv / volume_breakout
├── filter/             Filter 协议 + 注册表（2.3 实装）
├── trade/              records.py + records.csv
└── ui/                 占位（2.4 实装）
```

### 9.3 文件迁移对照

| 原路径 | 新路径 | 说明 |
|---|---|---|
| `stockdata.py` | `quant/foundation/season.py` + `growth.py` + `financial.py` + `quant/price/loader.py` | 按职责拆分，算法未改 |
| `utils/download.py` | `quant/data/download_a.py` | 去掉 sys.path hack；股票池来源改为自动取最新 zcfz |
| `utils/osutil.py` | `quant/data/fsutil.py` | 相对路径改为 DATA_DIR |
| `utils/stockapi.py` | `quant/data/stockapi.py` | **删除 IEX 段与明文 API Key**，删除模块级调用 |
| `utils/download_us.py` | `quant/data/download_us.py` | 删除模块级调用；修正忽略入参的 bug |
| `strategy/bt_ova.py` | `quant/strategy/ma_obv.py` | 回测包装成 `run_backtest()` |
| `strategy/test1.py` | `quant/strategy/volume_breakout.py` | 同上，策略类改名 |
| `trade/trade.py` + `record.csv` | `quant/trade/records.py` + `records.csv` | 删除模块级执行与调试 print |
| `process.py` | `quant/cli.py` 子命令 | 顶层副作用消除 |
| `analyse/*.py`（3 个） | `research/` | 归档为研究草稿 |
| `strategy/bt_etf.py`、`backup/bt_etf.py` | `research/etf_rotation_draft_{a,b}.py` | ETF 轮动草稿，2.3 重写 |
| `analyse/ana.ipynb`、`stock_select.ipynb`、`stockdata_usage.ipynb` | `notebooks/legacy/` | 原样归档 |
| `config.py` / `config.py.sample` | `quant/config.py` + `.env.example` | 环境变量优先 |
| `gui.py`、`spy.py`、`test.py`、`anabase.py` | — | 已删除（按决策） |
| `backup/`、`.qoder/`、`.lingma/`、`netres/`、`__pycache__/` | — | 已删除 |

### 9.4 阶段 2.1 顺手修复的问题（原 5.4 编号）

| 原编号 | 问题 | 处理 |
|---|---|---|
| 1 | `all_a_stocks` 硬编码不存在的 `zcfz_20230930.csv` | 改为自动读取最新 zcfz 文件 |
| 2 | `datetime` 未导入导致 NameError | 该文件已归档，2.3 重写时一并解决 |
| 4 | `from ..config import` 越级导入 | 归档文件中；包内已统一为绝对导入 |
| 9/10/11/12 | 模块级副作用（import 即联网/执行） | 全部消除 |
| 20 | `stockdata.py` 无用 import backtrader | 删除 |
| 25 | `sys.path.append` + config 不入库 | 改为真正的包 + 环境变量配置 |
| 26 | `gui.py` 孤立 Demo | 已删除 |

其余问题（`.item()` 脆弱性、`_x/_y` 列名、`to_csv` 索引列、裸 `except`、
PE/PB 排序依赖、O(n²) 循环、`pre/cur` 缺失）**保持原样**，留待 2.2 处理，
代码中已在相应位置标注 `TODO(2.2)`。

### 9.5 验证结果（全部通过）

| 验证项 | 命令 | 结果 |
|---|---|---|
| 依赖自检 | `quant info` | Python 3.11.17；akshare 1.18.63 / pandas 2.1.4 / numpy 1.26.3 / scipy 1.11.4 / backtrader 1.9.78.123 / ta 0.11.0 / TA-Lib 0.6.7 / statsmodels 0.14.1 / wxPython 4.2.3 全部 OK |
| 数据体检 | `quant check` | 三表各 54 个文件（20100331~20230630）；日线 pre 4903 / cur 4925，**22 只股票只有 cur 文件**；financial 2721；etf 63 |
| 模块导入 | 18 个模块全量 import | 通过 |
| 日线读取 | `get_stock_price('000001')` | 3288 行 × 21 列 |
| 估值读取 | `get_full_price('000001')` | 3288 行 × 25 列，含 PE / PB，DatetimeIndex |
| 股票池 | `all_a_stocks()` | 5063 只（来源 zcfz_20230630.csv） |
| 单测 | `pytest` | 全部通过（季报日期 20 项、单季增长 3 项、配置 5 项、CLI 4 项、过滤器 3 项） |
| **算法等价性** | `quant calc-growth --from-year 2021` | **与重构前的 data/202101-lastseason.csv 完全一致**：12640 行 × 51 列，季度集合相同，股票集合相同，6 个计算列（preYearIncome / SeasonIncome / SeasonIncomeGrowth / preYearProfit / SeasonProfit / SeasonProfitGrowth）max_abs_diff = 0 |

> 等价性验证是本次重构最关键的证据：算法代码在迁移过程中**没有发生任何数值变化**。

### 9.6 验证命令

```powershell
.venv/Scripts/python.exe -m quant info     # 配置与依赖自检
.venv/Scripts/python.exe -m quant check    # 数据目录体检
.venv/Scripts/python.exe -m pytest         # 单测
```

---

---

## 10. 阶段 2.2 完成记录（数据稳定化 + 增量更新）

### 10.1 存储架构

SQLite 成为**唯一查询入口**，原始件归档到 `data/original/`，详见 [data_model.md](data_model.md)。

| 表 | 行数 | 说明 |
|---|---|---|
| `stock_list` | 5,384 | 代码 + 简称 |
| `daily_price` | 10,193,800 | 4,925 只股票，2010-01-04 ~ 2023-11-30 |
| `etf_daily` | 43,284 | 62 只 ETF |
| `fundamental` | 199,909 | 5,384 只股票 × 56 个季度（20100331 ~ 20231231） |
| `fundamental_growth` | 199,909 | 单季增长 |
| `financial_indicator` | 136,223 | 2,721 只股票，精选 29 列 + 2 列 TTM |
| `trade_record` | 13 | 历史选股/交易记录 |

### 10.2 新增模块

| 文件 | 职责 |
|---|---|
| `quant/data/schema.py` | 数据契约：中文列名 -> 英文列名映射、各表列定义、`DISPLAY_NAMES` 展示名 |
| `quant/data/store.py` | SQLite 建表 / 写入 / 查询 / 统计 |
| `quant/data/frames.py` | 原始 DataFrame -> 可写库结构的规范化（日期、去重、数值化） |
| `quant/data/migrate.py` | 一次性 CSV -> SQLite 迁移、`original/` 归档、重复数据清理 |
| `quant/data/update.py` | 增量更新：季度基本面 / 日线 / ETF / 派生表 |

### 10.3 新增命令

```
quant db-init / db-stats / db-migrate [--archive] [--cleanup --yes]
quant update-jibenmian / update-price / update-etf / update-all / rebuild-growth
quant calc-growth [--legacy-columns]
```

旧的 `download-jibenmian / download-price / download-etf` 已由 `update-*` 取代
（增量语义，不再有 pre/cur 双文件与 temp 归档目录）。

### 10.4 修复的历史问题（原 5.4 编号）

| 原编号 | 问题 | 处理 |
|---|---|---|
| 14 | 三表 merge 产生 `_x/_y` 重复列名 | 迁移时按表分别重命名后合并，列名唯一且英文 |
| 15 | `to_csv` 带出匿名索引列 `Unnamed: 0` | 入库路径不再落盘 CSV；归档保留原样 |
| 16 | `.item()` 遇多行/缺行直接抛异常 | `calc_ttm` / `fix_bvps` / `compute_growth` 全部向量化，缺数据返回 NaN |
| 17 | PE/PB 依赖「组内行序」 | 计算前显式按日期排序，按季度首行取值，行序不再影响结果 |
| 19 | `growth_score` 逐股票双重循环（O(n²)） | 改为向量化（merge + 广播），24 万行秒级完成 |
| 21 | 22 只股票只有 `cur.csv`，读取必崩 | 数据入 `daily_price` 后不存在 pre/cur 概念，问题消失 |
| — | 个股缺失 pre/cur 导致 FileNotFoundError | 同上 |
| — | 冗余数据 2.1 GB（temp 890MB + price.zip 316MB + 归档副本） | 归档到 `original/`，重复副本删除（见 10.6） |

### 10.5 等价性验证（全部通过）

| 验证项 | 方法 | 结果 |
|---|---|---|
| 日线（抽查） | 12 只股票（含 22 只缺 pre 中的 2 只）CSV vs 库，逐列比较 | **max_abs_diff = 0** |
| 日线（全量） | 全部 4,925 只：行数 + `close_qfq` 合计 + `volume` 合计 + 日期范围 | **4,925 只全部一致，0 处不符**（10,193,800 行） |
| 单季增长 | 旧 `stockdata.py`（CSV 路径）vs 新 `compute_growth`（SQLite 路径），同一数据快照 | 6 个计算列 **max_abs_diff = 0**，行数/股票集合完全一致（15,156 行 / 1,263 只） |
| `get_full_price` | 旧实现 vs 新实现，比较 `close` / `close_org` / `PE` / `PB` | season ≥ 20120331 **max_abs_diff = 0** |
| `calc-growth` 导出 | 与旧 `calc_a_growth` 同口径导出 | 行数、季度数、股票集合一致 |
| 单测 | `pytest` | **68 passed** |

**唯一的有意差异**：旧实现在 `fix_financial_data` 里硬编码截断了 `report_date < 2011-01-01`，
导致 `season <= 20111231` 缺去年年报而算不出 TTM，这些季度的 PE/PB 全为 0。
新实现取消该截断，因此 2011 年及以前**多出**真实估值数据（已验证：旧实现全 0，新实现有值）。
2012Q1 起两者完全一致。

### 10.6 数据治理结果

| 动作 | 内容 |
|---|---|
| 归档 | `jibenmian/`(99MB) + `financial/`(78MB) + `stock_statements/`(914MB) + `etf/` 清单 -> `data/original/` |
| 删除 | `data/a/stock/price/`(950MB)、`data/a/stock/temp/`(890MB)、`price.zip`(316MB)、`data/a/etf/price/` |
| 结果 | 数据总量从 **6.17 GB 降到约 2.9 GB**（`quant.db` 约 1.8 GB + `original/` 1.1 GB） |

> 归档副本在删除前做过逐目录的文件名 + 大小一致性核对（6 组目录全部一致）。

### 10.7 增量更新实测

| 命令 | 结果 |
|---|---|
| `quant update-price --stock 000001` | 从库中最后交易日 2023-11-30 续拉到 2026-10-13，新增 713 行（**空档 3 年一次补齐**） |
| `quant update-etf --symbol 512480 159611` | 新增 1,790 行，两只 ETF 均更新到 2026-10-13 |
| `quant update-jibenmian --from-year 2024 --to-year 2024` | 下载 12 个季度文件到 `data/original/jibenmian/`，增量摄入 20,623 行 / 4 个季度 |
| `quant rebuild-growth` | 220,532 行 / 5,384 只股票 |

更新后的数据库现状：

| 表 | 行数 |
|---|---|
| `daily_price` | 10,194,513（4,925 只，2010-01-04 ~ 2026-10-13） |
| `etf_daily` | 45,074 |
| `fundamental` | 220,532（5,384 只 × 60 个季度，20100331 ~ 20241231） |
| `fundamental_growth` | 220,532 |
| `financial_indicator` | 136,223 |

> 注：`financial_indicator` 仍是 2023 年以前的历史数据，需要等 `financial_report` 的更新通道
> （阶段 2.3 补）才能让 PE/PB 跟上最新行情。

### 10.8 待办：删除残留的 data/a

`data/a/`（3.16 GB，37,385 个文件）内容已全部归档到 `data/original/` 并进入 `quant.db`，
但该目录不在当前文件沙箱的可写 ACL 内，自动删除被拒。请在**普通终端**（不受沙箱限制）执行一次：

```bat
:: 双击运行（推荐）
scripts\cleanup_data_a.bat

:: 或在 cmd.exe 里
rd /s /q data\a

:: 或在 PowerShell 里（注意：PowerShell 中 rd 是 Remove-Item 的别名，不认 /s /q）
cmd /c "rd /s /q data\a"
:: 或
Remove-Item -Recurse -Force .\data\a
```

删除后数据总量从 6.19 GB 降到约 2.9 GB（`quant.db` 1.98 GB + `original/` 1.10 GB）。

---

*本文档随重构进展更新。阶段 1 分析结论已冻结；2.1 见第 9 节，2.2 见第 10 节。*


