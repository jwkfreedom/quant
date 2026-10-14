# 选股过滤器指南

## 一分钟上手

```python
from quant.filter import FilterChain, FilterContext

with FilterContext(as_of=20231229) as ctx:          # as_of 不传 = 库中最新交易日
    result = FilterChain.from_specs([
        "exclude_st",                                # 剔除 ST / 退市
        "min_listing:bars=250",                      # 上市满一年
        "market_cap:max=200",                        # 市值 < 200 亿
        "growth:field=season_income_growth,min=20",  # 单季营收同比 > 20%
        "price_change:bars=20,min=0",                # 近 20 个交易日上涨
    ]).run(ctx)

print(result.report())        # 每一步剩了多少只
print(result.frame.head())    # 结果表（一行一只股票）
```

命令行等价形式：

```bat
quant screen --filter exclude_st --filter market_cap:max=200 --filter growth:min=20 --out picks.csv
quant screen --list            :: 查看所有可用过滤器
```

描述语法：`name` 或 `name:k=v,k=v`，参数值会自动转成 int / float / bool / str / None。

## 数据从哪来

`FilterContext.snapshot()` 给出一张**横截面表**（一行一只股票）：

| 分组 | 列 |
|---|---|
| 标识 | `symbol`、`name` |
| 行情 | `date`、`close`(前复权)、`close_org`(不复权)、`close_qfq`、`volume`、`turnover`、`pct_change`、`turnover_rate` |
| 基本面 | `season`、`total_revenue`、`total_revenue_yoy`、`net_profit`、`net_profit_yoy`、`total_assets`、`total_liabilities`、`debt_ratio`、`total_equity` |
| 单季增长 | `season_income`、`season_income_growth`、`season_profit`、`season_profit_growth` |
| 财务指标 | `report_date`、`eps_ttm`、`bvps_ttm`、`roe`、`gross_margin` |
| 派生 | `shares`、`market_cap`（不复权价 × 股本）、`pe`、`pb` |

需要历史序列时用 `ctx.history(bars)`：返回每只股票最近 bars 根 K 线（长表，
`close` 前复权、`close_org` 不复权），同一个 bars 只查一次。

> 性能：快照约 3~4 秒，首次 history 约 10 秒（之后走缓存）。
> 所以一次选股尽量把所有条件放进同一个 `FilterChain`，而不是分多次调用。

## 内置过滤器

| 名字 | 参数 | 说明 |
|---|---|---|
| `exclude_st` | `keywords=ST,退` | 名称包含关键词的剔除 |
| `min_listing` | `bars=250` | 上市满 N 根 K 线 |
| `market_cap` | `min` / `max`（**亿元**） | 总市值区间 |
| `pe` | `min` / `max` | 市盈率(TTM) 区间 |
| `pb` | `min` / `max` | 市净率(TTM) 区间 |
| `roe` | `min` | 净资产收益率下限(%) |
| `debt_ratio` | `max` | 资产负债率上限(%) |
| `growth` | `field` / `min` / `max` | 单季增长区间，`field` 取 `season_income_growth` 或 `season_profit_growth` |
| `turnover_rate` | `min` / `max` | 换手率区间(%) |
| `price_change` | `bars=20` / `min` / `max` | 最近 N 个交易日涨跌幅(%) |
| `price_range` | `bars=5` / `max` | 最近 N 个交易日 (最高-最低)/最低 的振幅上限(%) |
| `ma_trend` | `short=5` / `long=20` | 短均线在长均线之上 |
| `ma_cross` | `short` / `long` / `window=3` | 最近 window 日内发生金叉 |
| `volume_ratio` | `bars=20` / `min` / `max` | 当日量 / 近 N 日均量 |

`min` / `max` 只写一侧就是单边限制；判断前会剔除 NaN（数据缺失的股票会被过滤掉）。

## 写一个自己的过滤器

```python
from quant.filter import register

@register
class SmallCap:
    name = "small_cap"                 # 命令行里用这个名字
    description = "市值小于 80 亿"      # quant screen --list 会打印

    def __init__(self, max_yi=80):     # 参数必须是显式关键字参数
        self.max_yi = max_yi

    def apply(self, df, ctx):          # df 是当前快照，返回过滤后的 df
        return df[df["market_cap"] <= self.max_yi * 1e8]
```

放到 `quant/filter/builtin.py` 里（或在 notebook 里定义后立即注册）即可：

```bat
quant screen --filter small_cap:max_yi=50
```

### 需要历史序列的过滤器

```python
@register
class UpDays:
    name = "up_days"
    description = "最近 N 日中上涨天数不少于 K 天"

    def __init__(self, bars=20, min_up=15):
        self.bars = int(bars)
        self.min_up = int(min_up)

    def apply(self, df, ctx):
        hist = ctx.history(self.bars).sort_values(["symbol", "date"])
        up = hist.assign(up=hist["pct_change"] > 0).groupby("symbol")["up"].sum()
        keep = up[up >= self.min_up].index
        return df[df["symbol"].isin(keep)]
```

## 与旧需求文档的对应

`docs/stock_filter_ideas.md` 里那两条自然语言条件，现在可以这样落：

```python
FilterChain.from_specs([
    "price_range:bars=5,max=5",      # 最近 5 日最高最低价差 < 5%
    "market_cap:max=80",             # 市值 < 80 亿
    "price_range:bars=10,min=10",    # 最近 10 日振幅 > 10%（需要 range 的 min 侧）
    "price_change:bars=1,max=1",     # 今天涨幅 < 1%
])
```

> 注意：`price_range` 目前只有上限（`max`）。需要「振幅下限」时，
> 给 `PriceRange` 加一个 `min` 参数即可（`_between` 已经支持双边）。
