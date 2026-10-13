# notebooks/legacy —— 归档 notebook

这些 notebook 是重构前的工作副本，**原样保存、未做修改**。
它们 `import stockdata as sd`，而旧的 `stockdata.py` 已经拆分进 `quant` 包，
因此目前**不能直接运行**。

| notebook | 内容 |
|---|---|
| `stock_select.ipynb` | 选股实验：营收/净利润/资产负债率散点筛选 |
| `stockdata_usage.ipynb` | 基本面成长表（202101-lastseason.csv）的使用示例 |
| `ana.ipynb` | matplotlib 日期轴实验 |

阶段 2.3 会基于新的包 API 重写，并放到 `notebooks/` 根目录。
