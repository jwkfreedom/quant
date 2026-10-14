# 选股过滤条件（需求备忘）

> 来源：重构前的 `trade/stockfilter.md`，原样保留。
>
> **阶段 2.3 已实现可插拔过滤器框架**（`quant/filter/`，命令行 `quant screen`），
> 下面是这两条条件的对应写法；实际使用时按需微调参数。
> 用法见 [filter_guide.md](filter_guide.md)。

```python
from quant.filter import FilterChain, FilterContext

with FilterContext() as ctx:
    result = FilterChain.from_specs([
        # 条件 2：最近 5 日最高/最低价差 < 5%；市值 < 80 亿；今日涨幅 < 1%
        "price_range:bars=5,max=5",
        "market_cap:max=80",
        "price_change:bars=1,max=1",
        # 条件 1：最近 20 日涨幅 > 10%
        "price_change:bars=20,min=10",
    ]).run(ctx)
print(result.report())
```

## 原始条件

1. 平台整理 5，最近 20 日涨幅大于 10%，最近 4 个月跌幅大于 5%
2. 最近 5 日最高价比最低价差距小于 5%，市值小于 80 亿；
   最近 10 日最高价比最低价差距大于 10%；今天涨幅小于 1%

## 待澄清的口径（实现前需要确认）

| 项 | 需要明确 |
|---|---|
| 「平台整理 5」 | 5 是指 5 个交易日还是 5%？整理如何量化（振幅阈值？收盘价标准差？） |
| 「最近 20 日涨幅」 | 是 `close / close.shift(20) - 1` 还是含最高/最低价？ |
| 「最近 4 个月跌幅」 | 4 个月按 80 个交易日还是自然月？基准取区间最高价还是起始收盘价？ |
| 「市值」 | 用总市值还是流通市值？数据来源（当前仅有 `financial_report` 的每股指标，需补市值字段） |
| 「今天涨幅」 | 用当日 `涨跌幅` 字段（%）还是自算 `close/close.shift(1)-1`？ |
| 组合逻辑 | 两条条件之间是「或」还是「与」？各自内部条件都是「与」吗？ |
