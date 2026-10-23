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

## 11. 阶段 2.3 完成记录（主要功能接口）

### 11.1 新增模块

| 文件 | 职责 |
|---|---|
| `quant/query.py` | 统一查询 API：`snapshot()` 横截面快照、`prices()` / `price_wide()` / `price_history()`、`fundamentals()` / `growth()` / `financial()`、`universe()`、`summary()` |
| `quant/filter/base.py` | Filter 协议、FilterContext（快照与历史的查询缓存）、注册表 |
| `quant/filter/builtin.py` | 14 个内置过滤器（见 11.3） |
| `quant/filter/chain.py` | FilterChain（记录每一步剩余数量）、ScreenResult、`name:k=v` 描述解析 |
| `quant/strategy/runner.py` | cerebro 统一装配（资金/手续费/**仓位 sizer**/分析器）、BacktestResult、指标提取 |
| `quant/data/frames.py:prepare_financial_frame` | 财务数据入库唯一入口（含 TTM 计算） |

### 11.2 新增命令

```
quant screen [--filter SPEC ...] [--as-of] [--sort] [--limit] [--columns] [--display-columns] [--out] [--list]
quant backtest --strategy NAME [--symbol] [--cash] [--commission] [--plot] [--list]
quant update-financial [--stock ...] [--limit] [--workers] [--delay] [--force]
```

### 11.3 内置过滤器

`exclude_st`、`min_listing`、`market_cap`、`pe`、`pb`、`roe`、`debt_ratio`、
`growth`、`turnover_rate`、`price_change`、`price_range`、`ma_trend`、`ma_cross`、`volume_ratio`。

写自定义过滤器只需实现 `apply(df, ctx)` 并 `@register`，即可在命令行用 `--filter 名字:参数` 引用。
详见 [filter_guide.md](filter_guide.md)。

### 11.4 修复的问题

| 位置 | 问题 | 处理 |
|---|---|---|
| `query._read_sql` | dict 参数被 `list()` 转成键名列表，命名占位符全部绑错（`snapshot(as_of=...)` 实际没生效） | 单测发现；dict 原样传给 pandas |
| `FilterContext.history` | 全表窗口函数排序 1000 万行（20~28 秒/次） | 改为「按每只股票自己的最后交易日回推区间 + 临时表 join」，21 根约 0.5~12 秒且只查一次 |
| `FilterContext.history` | 列名与 `daily_price` 不一致（`close_org`） | 统一成 loader 口径：`close` 前复权、`close_org` 不复权 |
| `MyOBV` | 指标从未初始化（首值 NaN），策略一笔都不买 | 加 `nextstart()`，OBV 从 0 起算 |
| `build_cerebro` | 没设 sizer，backtrader 默认每次买 1 股，回测结果恒等于初始资金 | 统一 `PercentSizer(95)` |
| `VolumeBreakoutStrategy` | 买入前不判断是否已持仓，配合百分比仓位会把现金打成深负数 | 加持仓判断 |
| `extract_result` | 回撤取自不存在的字段，恒为 0 | 改用 `drawdown.get_analysis()["max"]` |

### 11.5 示例 notebook

`notebooks/` 下三个可直接运行的示例（**已用脚本逐个执行验证通过**）：

| 文件 | 内容 |
|---|---|
| `01_数据总览.ipynb` | 数据概况、全市场快照、市值分布、单股日线与 PE、基本面时序 |
| `02_选股示例.ipynb` | 过滤链（字符串/对象两种写法）、自定义过滤器、导出 |
| `03_回测示例.ipynb` | 策略列表、两个策略回测、批量对比 |

### 11.6 验证

| 项目 | 结果 |
|---|---|
| 单测 | **109 passed**（新增 query / filter / strategy / 回测冒烟 共 40+ 条） |
| notebook | 3 个 notebook 的全部代码单元执行成功 |
| `quant screen` | 实跑：4925 → 4660 → 4578 → 324 → 185 只，各步剔除数与结果表正常 |
| `quant backtest` | 实跑：ma_obv(512480/159611/510880)、volume_breakout(000001/600519) 均输出收益/回撤/交易次数/胜率 |
| `quant update-financial` | 逐股增量更新，并发抓取 + 单线程写库（后台运行中） |

### 11.7 已知限制

1. `financial_indicator` 的更新是逐股请求（约 5000 只，单只约 2.6 秒；
   `--workers 6` 约 1.3 秒/只），完整跑一轮 **约 2 小时**。已在后台执行：

   ```bat
   .venv\Scripts\python.exe -m quant update-financial --workers 6 --delay 0
   ```

   实测：`--workers 6` 时 100 只 / 135 秒（约 1.35 秒/只）。
   每 100 只提交一次，可以随时中断、重跑（`skip_unchanged` 会跳过已是最新报告期的股票）。
   未更新到的股票 PE/PB 为 NaN（选股时会被 `pe`/`pb` 过滤器剔除）。

   注意进度不能看「有 TTM 的股票数」——已经是最新报告期的股票会被跳过、不产生变化；
   要看日志里的 `财务指标进度 N/总数`。

   首次全量跑完后发现一个坑：akshare 的 `stock_financial_analysis_indicator` 会按年份
   逐年请求，**起始年份给太早（2000）时部分股票会整体返回空表**
   （实测 002415、300750 返回 0 行，000001 正常）。已在 `fetch_financial` 里加了
   起始年份回退阶梯（2010 -> 2015 -> 2020），并对空结果告警。

   日常增量用 **`--stale-days`** 只更新过期标的，不必每次遍历全市场：

   ```bat
   .venv\Scripts\python.exe -m quant update-financial --stale-days 180 --workers 4 --delay 0.2
   ```

   **最终结果**（`--stale-days 180 --workers 4 --delay 0.2`，4249 只，用时 59 分钟）：

   | 项 | 结果 |
   |---|---|
   | 处理 / 更新 / 跳过 | 4249 / **4150** / 99（无数据的退市股） |
   | 写入行数 | 154,820 |
   | `financial_indicator` 总量 | **299,428 行 / 5,317 只股票** |
   | 最新报告期 | 2026-09-30 |
   | 快照 PE / PB 覆盖率 | **4921 / 4925 (99.9%)**（此前只有 105 只） |

### 11.8 全链路实测（数据补全后）

```bat
quant screen --filter exclude_st --filter min_listing:bars=250 ^
             --filter market_cap:max=300 --filter pe:min=0,max=20 --filter roe:min=10
```

```
初始股票池  4925 -> exclude_st 4660 -> min_listing 4578 -> market_cap 4055 -> pe 727 -> roe 118
```
2. `snapshot(as_of)` 的季度上限沿用项目既有口径 `get_season_iDATE`（报告期 ≤ 快照日），
   对年初的日期存在「年报尚未披露但已被使用」的前视偏差，与重构前行为一致。
3. `FilterContext.history()` 首次查询约 10 秒（1000 万行上做区间扫描），同一次选股内走缓存。

---

## 12. 阶段 2.4 记录（桌面界面 + 估值历史分位）

### 12.1 需求确认（用户答复「按默认」）

| 项 | 决定 |
|---|---|
| UI 技术栈 | **wxPython 4.2.3** + matplotlib（已安装，无需新依赖） |
| 分位口径 | 剔除 PE ≤ 0 的交易日；**按每个交易日**计算；窗口 3/5/10 年 + 全历史，默认 10 年 |
| 数据准备 | 开发前先补基本面到最新季度 |
| PS 口径 | 总市值 ÷ 营业总收入(TTM) |
| 回测范围 | 第一版只支持单标的 |
| 方案保存 | 项目内 `config/screens/*.json` |
| 导出 | CSV 为主，同时支持 Excel（openpyxl） |
| 一键更新 | 做，带确认对话框并在后台线程执行 |

> 约束：本环境无显示，**看不到窗口**。因此 UI 拆成「视图模型层（纯 pandas，可无头单测）+
> wx 视图层（薄）」，功能正确性由 pytest 保证，外观需用户本地验证。

### 12.2 底层能力（2.4.0）

| 新增 | 说明 |
|---|---|
| `valuation_percentile` 表 | 一行一只股票 × 一个窗口，约 1.5 万行（不是 1000 万行的逐日大表） |
| `quant/foundation/valuation.py` | 逐日估值序列（`compute_symbol_valuation`）与分位计算（`compute_percentiles`） |
| `quant rebuild-valuation` | 批量重建分位表（多线程读、单线程写，可中断续跑） |
| `quant rebuild-ttm` | 回填 `fundamental.revenue_ttm / net_profit_ttm`（PS 依赖） |
| schema v2 | `ensure_schema()` 自动 `ALTER TABLE` 补列，老库无缝升级 |
| 新过滤器 | `pe_percentile` / `pb_percentile` / `ps_percentile` / `ps` / `break_ma` / `ma_align` / `gross_margin` |
| 快照新列 | `ps`、`pe_pct_3y/5y/10y/all`、`pb_pct_10y`、`ps_pct_10y`、`revenue_ttm`、`net_profit_ttm` |
| 回测增强 | 净值曲线、买入持有基准、年化收益、夏普、成交明细、策略参数化（`PARAMS_SPEC` / `StrategyInfo`） |
| 数据源回退 | 东财被限流时自动改用新浪（`fetch_price_sina`），并可 `--source` 指定 |

**分位口径**（用户确认）：
`PE_t = 不复权收盘价 ÷ 当期已披露的 EPS_TTM`，
分位 = 窗口内 `PE < PE_t` 的交易日占比；剔除 `PE ≤ 0`（亏损期）与指标缺失的交易日。

### 12.3 界面（2.4.1）

`quant/ui/`：

| 文件 | 职责 |
|---|---|
| `viewmodels.py` | 数据总览状态、表浏览器分页查询、导出、选股、方案存取、个股数据包、回测转发 |
| `charts.py` | K线、估值带、财务、估值历史、净值曲线、市值/PE 分布（纯 Figure，无 GUI 依赖） |
| `widgets.py` | DataFrameGrid、FigurePanel、MetricCards、BusyRunner（后台任务）、导出对话框 |
| `screens/` | dashboard / screener / stock_detail / backtest / explorer / settings |
| `app.py` | 主窗口（左侧导航）+ 菜单 + 状态栏 |

启动：`scripts\run_ui.bat` 或 `python -m quant ui [symbol]`。

### 12.4 数据现状（2.4 完成后）

| 表 | 行数 | 覆盖 |
|---|---|---|
| `daily_price` | 13,814,214 | 5,322 只，2010-01-04 ~ **2026-10-14** |
| `fundamental` | 251,837 | 5,384 只 × 66 个季度，20100331 ~ **20260630** |
| `fundamental_growth` | 251,837 | 同步重建到 2026Q2 |
| `financial_indicator` | 299,428 | 5,317 只，最新报告期 2026-09-30 |
| `valuation_percentile` | 21,128 | **5,322 只 × 4 个窗口** |
| `etf_daily` | 45,074 | 62 只 ETF |

快照覆盖率（`quant check` / `query.snapshot()`）：

| 字段 | 非空 |
|---|---|
| `market_cap` / `pe` / `pb` | 5,276 / 5,278 / 5,278 |
| `ps` | 5,260 |
| `pe_pct_10y`（3y/5y/all 同） | 3,614（其余为历史不足或长期亏损被剔除） |
| `pb_pct_10y` / `ps_pct_10y` | 5,127 / 5,133 |
| `roe` / `debt_ratio` | 5,175 / 5,322 |

PE 十年分位分布：≤10% 有 **605 只**，≤20% 有 924 只，中位数 53.1。

### 12.5 验证

| 项目 | 结果 |
|---|---|
| 单测 | **199 passed**（含 valuation / runner / viewmodels / ui 冒烟 / 无头构造 / wx API 静态检查） |
| notebook | 3 个示例 notebook 全部代码单元执行通过（已适配新 API） |
| 编译检查 | `python -m compileall quant/ui` 通过 |
| 模块导入 | `quant.ui.app` 导入成功，6 个页面类均可解析 |
| **无头构造** | 真实创建 `MainFrame`：6 个页面、21 个条件行、个股渲染、参数表单、页面切换全通过（`tests/test_ui_frame.py`，9 条） |
| **wx API 静态检查** | AST 扫描源码里所有 `wx.<Name>`，逐个核对是否存在（`tests/test_wx_api.py`，14 条） |
| 图表 | 7 类图形对真实数据与空数据都能正常构建 |
| 实跑 | `quant rebuild-valuation`、`quant screen`（含 PE 分位）、`quant backtest`（含参数）均验证通过 |

### 12.6 界面打磨（A 阶段，用户确认后追加）

| 位置 | 新增能力 |
|---|---|
| DataFrameGrid | 点击列头排序（升序/降序/取消，取消时恢复原始顺序）、右键菜单框架（ContextMenu）、Ctrl+C 复制选区、selected_rows() |
| 选股筛选 | 双击结果行跳到个股分析；右键「查看个股分析 / 复制代码 / 导出选中」 |
| 个股分析 | K 线日/周/月周期切换（charts.resample_ohlc）、前复权/不复权切换、叠加 MACD / RSI（纯 pandas 实现，不依赖 talib） |
| 策略回测 | 新增「参数扫描」页签：参数区间 + 步长 → 逐值回测 → 结果表 + 各指标随参数变化曲线（标出最优值） |
| viewmodels | sweep_values()、sweep_backtest()（单值失败不中断整轮） |
| 筛选说明 | 选股页新增「说明」按钮 → 弹出完整说明书（`quant/filter/guide.py`）：快照日期规则、过滤链机制、14 个条件的逐参数说明与例子；右键条件名可单独查看该条件；命令行 `quant filter-guide` 输出同样内容 |
| 策略说明 | 回测设置左侧新增「策略说明」区（只读、等宽字体），内容由 `StrategyInfo.explain()` 从**策略自身声明**生成：描述 + 参数表（名称/含义/默认值/范围）+ 编号算法步骤 + 默认标的与分类；切换策略自动刷新 |

**顺带修掉的口径问题**：query.prices() 返回的列沿用数据库约定
（open/high/low/close 是**不复权**、*_qfq 是前复权），
而 loader 的 get_stock_price() 是 close 前复权 + *_org 不复权 —— 两套命名不一致，
导致 K 线图最初把「前复权」画成了不复权。现在由 charts.price_columns(df, adjust) 统一识别两套命名。

**说明书与代码的一致性**：`quant/filter/guide.py` 只放给人看的散文，
过滤器行为仍在 `builtin.py`。`tests/test_filter_guide.py`（49 条）用反射核对：
每个已注册过滤器都必须有说明、**说明里写的参数必须与 `__init__` 的真实参数完全一致**、
分组必须覆盖全部过滤器、快照日期与过滤链机制的关键内容必须在位。
改代码却忘了改文档，测试直接失败。

**策略说明的设计**：说明文本不写在界面代码里，而是由每个策略模块声明
`PARAMS_SPEC`（参数）与 `RULES`（算法步骤），`StrategyInfo.explain()` 渲染成文本。
这样新增策略只要写这两份声明，界面上的参数表单与算法说明就自动同步，
不会出现「文档写了、代码改了」的脱节。

### 12.7 界面无响应的排查与加固

用户反馈「运行回测后命令行有输出、界面没内容」。在无头环境复现时发现
**数据其实已经写进控件**（卡片、表格、图表都拿到了值），因此问题定位在
「渲染回调失败被静默吞掉」与「wx 不重绘」两类原因上。已做三处加固：

1. `BusyRunner._finish` 现在会捕获渲染回调里的异常并弹窗提示
   （以前异常只进 stderr，界面上什么都看不到）；
2. 新增 `widgets.relayout()`，在控件重建后显式 `Layout() + Refresh()`；
   `MetricCards.set_metrics`、`FigurePanel.set_figure` 也会主动让父面板重排；
3. 回测结果页新增**文字摘要行**（把 `result.report()` 压成一行），
   即使卡片或图表出问题也能看到结果。

新增回归测试 `test_backtest_render_fills_widgets`：真实跑一次回测并调用渲染，
断言卡片有值、净值图已创建 —— 防止「命令行有、界面空」再次发生。

### 12.8 遗留与注意

1. **行情数据源**：东财（`stock_zh_a_hist`）在一次高并发全量更新后被限流，已改用新浪接口补齐
   （`fetch_price_sina`）。2023-12 以前的数据来自东财、之后来自新浪，**不复权价完全一致**
   （估值不受影响），**前复权序列在衔接处可能有极小台阶**（技术指标/回测跨该日时留意）。
2. **界面外观已由用户本机验证通过**（2026-10-14）：六个页面切换正常、选股能出结果、
   四张图表中文显示正常、无控件被窗口截断。
   已用「无头构造 + wx API 静态检查」把**代码级**问题提前拦住，
   首轮运行前就修掉了 6 个必然崩溃的问题：
   `wx.ListBook` 拼写（应为 `Listbook`）、页面早于状态栏创建、
   垂直 BoxSizer 使用 `ALIGN_CENTER_VERTICAL`、`StaticBoxSizer` 父窗口与面板不一致、
   `TextCtrl` 不支持 `hint` 参数、`Grid.SetAlternateRowColour` 不存在、
   绑定 `EVT_TEXT_ENTER` 缺少 `wx.TE_PROCESS_ENTER` 样式。
3. **PE/PB 分位需先跑 `rebuild-valuation`**，否则相关过滤器会提示缺列。
4. 未做：实盘对接、组合回测、定时任务。
5. 六个页面都已实现第一版（超出原计划的 2.4.1 范围），后续按用户反馈迭代外观与交互。
6. 全市场行情补齐时发现东财限流后，尾部约 88 只（退市/无数据）在反复重试中被手动中止；
   其余 5,146 只已更新到 2026-10-14。

---

## 13. 阶段 2.5 记录（UI 视觉改版 V2）

用户反馈「现在的 UI 太难看」，选定 **A 路线：wxPython 深度美化**（不换 GUI 框架、不加新依赖）。
效果稿 `docs/ui_mockup.html`，可运行样张 `scripts/ui_style_demo.py`，规范 `docs/ui_theme.md`。

### 13.1 三路线对比与选型

| 路线 | 外观上限 | 工作量 | 结论 |
| --- | --- | --- | --- |
| A. wx 深度美化 | 现代桌面工具（卡片化扁平风） | 2~3 轮 | **采用** |
| B. 换 PySide6 + QSS | 最高（暗色/动画/高分屏） | 重写整个视图层 | 本地单机工具用不上 |
| C. 改本地 Web UI | 最漂亮（ECharts） | 前后端都要重做 | 启动方式从双击 bat 变成起服务 |

### 13.2 新增模块

| 文件 | 内容 |
| --- | --- |
| `quant/ui/theme.py` | 色板 `C`、圆角/间距/字号常量、`sign_colour()`、`apply_matplotlib_theme()`。**不导入 wx**，绘图代码可安全引用 |
| `quant/ui/components.py` | `make_font` / `qpen` / `qbrush` / `measure_text` / `text_label` / `hint_label` / `style_input` 与自绘控件 `Card` / `FlatButton` / `Badge` / `SideNav` / `PageHeader`，以及 `make_notebook()`（agw.FlatNotebook，失败自动回退 `wx.Notebook`） |

自绘控件把绘制逻辑拆成 `_paint(gc, width, height)`，可以脱离真实窗口用 `wx.MemoryDC` 渲染，
因此**无头环境也能验证绘制路径不抛异常**（这是本机没有显示器时唯一可靠的验证手段）。

### 13.3 视觉规范

- 底色 `#F5F6F8`、白卡片 + `#E5E7EB` 描边、圆角 10px；主色 `#2563EB`
- 文字：主 `#111827` / 次 `#6B7280` / 弱 `#9CA3AF`；数字用 Consolas 等宽
- 字号：页面标题 16pt / 卡片标题 11pt / 正文 10pt / 表格 9pt
- 间距 8px 基准：卡片内边距 16、卡片间距 12、控件间距 8
- 涨 `#D93F3F`、跌 `#2E9E5B`（A 股习惯）
- 表格：行高 30、表头高 34、表头底 `#F9FAFB`、网格线 `#EEF0F3`、选中 `#EFF4FF`、数字列右对齐

### 13.4 六个页面改了什么

| 页面 | 改造 |
| --- | --- |
| 主窗口 | `wx.Listbook`（左侧丑页签）→ `SideNav` + `wx.Simplebook`；顶部加品牌区；状态栏换色 |
| 数据总览 | 三组 `StaticBoxSizer` → 「数据新鲜度 / 数据量」双卡片 + 「快捷操作」卡片；刷新移到标题条 |
| 选股筛选 | 条件区进卡片 + 滚动区；「说明 / 运行选股」升到标题条；结果区卡片化 |
| 个股分析 | 查询条拆两行放进卡片；标题显示在右侧；五个页签换 FlatNotebook |
| 策略回测 | 左列「回测设置 + 策略说明」两张卡片；右侧结果换 FlatNotebook |
| 数据浏览器 | 「查询条件」「结果」两张卡片；分页/导出行卡片内 |
| 设置/关于 | 路径、依赖、筛选方案三张卡片 |

### 13.5 验证

- `pytest tests` **257 passed**（新增 `theme.py` / `components.py` 后 `test_wx_api` 参数化多 2 项）
- 无头构造主窗口 + 逐个 `switch_page()` 正常
- 六个页面各自构造 + 真实渲染（选股出 5,057 只、回测卡片/净值图/成交明细都有值）
- 自绘控件逐个 `_paint()` 渲染无异常
- `python -m quant ui` 实际启动 9 秒无任何异常输出

### 13.6 已知取舍

1. **表格没有斑马纹**：`wx.grid` 的行属性会完全覆盖列属性，加了隔行底色就没法再做数字列右对齐。
   最终选择「极浅网格线 + 30px 行高 + 右对齐等宽数字」，观感更接近现代表格。
2. `FlatNotebook` 在部分 wxPython 版本没有 `SetTabFont`，已用 `SetFont` 兜底，
   并把整段样式设置包在 `try/except` 里，失败自动回退 `wx.Notebook`。
3. 外观仍需用户在本机确认（本机无显示）。若配色/密度要调，改 `theme.py` 的 `C` 类即可全局生效。

---

## 14. 阶段 3.1 记录（资产管理）

用户需求：一个资产账户下有多个资金账户；资金账户下有多个股票/基金；股票有持有量并可买进卖出；
每个产品（含现金）都有高/中/低风险属性；能按资金账户统计各风险类别占比。

### 14.1 需求确认（用户逐条答复）

| # | 决定 |
| --- | --- |
| 1 | 新建独立库 `data/portfolio.db`，不并进行情库 |
| 2 | 价格全部自动获取，新增基金净值数据源 |
| 3 | 现金作为产品参与统计，风险固定低风险 |
| 4 | 风险默认值：股票高 / 基金中 / 现金低，可手动改 |
| 5 | 买卖记全：日期、价格、数量、手续费、备注 |
| 6 | 有期初导入 |
| 7 | 卖出超过持有：拒绝并警告 |
| 8 | 按市值占比统计 |
| 9 | 新增第七个页面「资产管理」 |
| 10 | 多币种多市场（美元/港币/美股/港股），**先做 A 股、保留结构** |
| 11 | 分红自动统计、能算资金账户一年分红量；美股分红手动登记 |

补充确认：汇率用中行折算价；分红按除息日持股数、期初导入为起点；税前不计税；
分红不自动入账要手动「记入现金」；送转只提示不改数量；现金支持存入/取出。

### 14.2 新增模块

| 文件 | 内容 |
| --- | --- |
| `quant/portfolio/schema.py` | 表名/类型/市场/币种/风险/动作常量，建表 DDL，展示名 |
| `quant/portfolio/store.py` | SQLite 存取：owner / account / instrument / holding / txn / fx / dividend |
| `quant/portfolio/service.py` | 业务逻辑 `Portfolio`：买卖、调整、现金、估值、风险统计 |
| `quant/portfolio/prices.py` | 取价：本地行情库、ETF/个股联网兜底、基金净值、中行汇率 |
| `quant/portfolio/dividends.py` | 分红拉取、手动登记、按除息日持股数的明细与汇总、记入现金 |
| `quant/ui/screens/portfolio.py` | 第七页：总览 / 持仓 / 流水 / 分红，含 `TradeDialog` |
| `quant/ui/charts.py` | 新增 `risk_pie_figure` / `account_bar_figure` |
| `quant/ui/viewmodels.py` | 新增 `portfolio_*` 系列（纯 pandas，可无头测试） |
| `docs/portfolio_guide.md` | 使用说明 |

### 14.3 数据模型

    portfolio_owner       资产账户（人）
    portfolio_account     资金账户（币种 / 类型）
    portfolio_instrument  产品（kind/market/symbol + 风险 + 手动价）
    portfolio_holding     持仓（数量 + 成本价，唯一键 account+instrument）
    portfolio_txn         交易流水（buy/sell/adjust/deposit/withdraw/dividend）
    portfolio_fx_rate     汇率（1 外币 = rate 人民币）
    portfolio_dividend    分红（除息日/每股金额/送转比例/是否已入账）

### 14.4 关键规则

1. 成本用**移动加权平均**，买入手续费计入成本，卖出手续费从卖出金额扣。
2. 卖出超过持仓直接抛 `ValueError`；清仓后删除持仓行。
3. 买卖自动增减同币种现金；现金为负允许但会给 warning。
4. 拿不到价格时 `price` 为 `None`，**不拿成本价冒充**，缺价格的产品不计入总资产并单独计数。
5. 分红金额 = 除息日每股分红 × 该日持股数（由流水重建），按除息日归年，税前，不自动入账。
6. 所有汇总折算人民币；缺汇率时 1:1 兜底并告警。

### 14.5 数据源实测结论（2026-10 实测）

| 数据 | 接口 | 结果 |
| --- | --- | --- |
| A股个股分红 | `stock_fhps_detail_em` | 可用，含除权除息日、每 10 股派现/送转、方案进度 |
| ETF / 场外基金分红 | `fund_fh_em` | 可用（一次拉全量 7500 条，含 ETF 代码） |
| 场外基金净值 | `fund_open_fund_info_em` | 可用 |
| 港股分红 | `stock_hk_dividend_payout_em` | 可用，但方案是中文文本需解析 |
| 港股行情 | `stock_hk_daily` | 可用 |
| 美股行情 | `stock_us_hist` / `stock_us_daily` | 双源可用 |
| 汇率 | `currency_boc_sina` | 可用（中行折算价，单位 100 外币） |
| **美股分红** | — | **无 akshare 接口，yfinance 网络不通 → 只能手动登记** |

另外实测发现：本地 `etf_daily` 只覆盖 62 只 ETF，绝大多数场内基金要联网取 `fund_etf_hist_em`。

### 14.6 新增命令

`portfolio-init / owner / account / cash / buy / sell / adjust / position / stats / txn / update / dividend`
（详见 `docs/portfolio_guide.md` 第 8 节）

### 14.7 验证

- 新增 `tests/test_portfolio.py`（23 条）+ `tests/test_dividends.py`（10 条），**全量 291 passed**
- CLI 端到端实测：建账户 → 建资金账户（含 USD）→ 存现金 → 买入 → 期初导入 ETF → 刷新价格 →
  风险占比 58.26% / 18.90% / 22.84%（合计 100%）→ 拉取分红 28 条 → 2025 年分红 6,043 元
- 分红口径实测：600519 每 10 股派 276.73 元 → 每股 27.673 → 持有 100 股 → 2,767.30 元，与手工计算一致
- 界面：四个页签可构造，五种交易对话框的字段显隐正确

### 14.8 一年分红预期（后续追加）

按「窗口内每单位分红合计 × 当前持仓」估算年度分红，并给出年化股息率。

- 模块：`dividends.dividend_forecast()`，返回 (明细 DataFrame, 汇总 dict)
- 窗口：最近 N 个月（默认 12）或指定自然年度
- 界面：「分红预期」页签（第 5 个）；命令行 `quant portfolio-dividend --forecast`
- 测试：`tests/test_dividend_forecast.py`（9 条），全量 300 passed

### 14.9 已知限制

1. **美股分红无法自动获取**，只能在界面/命令行手动登记。
2. 港股/美股的行情与分红接口已写好但未做端到端验证（当前以 A 股为主）。
3. **没有每日资产快照**，所以没有资产曲线。
4. 红利税按税前统计，不扣税。
5. 网络抖动时联网取价会失败（akshare 的东财接口偶发断连），失败不影响已有价格。

---

*本文档随重构进展更新。阶段 1 分析结论已冻结；2.1 见第 9 节，2.2 见第 10 节，2.3 见第 11 节，2.4 见第 12 节，2.5 见第 13 节，3.1 见第 14 节。*


