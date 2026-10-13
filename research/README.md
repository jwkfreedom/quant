# research —— 研究草稿（非库代码）

这里存放从旧结构中归档出来的**实验脚本**。它们不在 `quant` 包内、不参与导入、
也不保证能直接运行（部分依赖的数据路径与列名已随重构变化）。

保留原因：其中的思路（形态识别、量能分析、ETF 打分轮动）在阶段 2.3 重写功能时会用到。

| 文件 | 原位置 | 说明 | 现状 |
|---|---|---|---|
| `ana_jibenmian.py` | analyse/ana_jibenmian.py | 均线金叉死叉、量能突变、波峰波谷 | 需把 `sd.*` 换成 `quant.*`；原代码调用不存在的 `sd.stock_price` |
| `ana_test.py` | analyse/ana_test.py | 头肩顶形态识别（scipy + mplfinance） | 可用，需改导入 |
| `analysis_ma_rsi.py` | analyse/analyse.py | MA + RSI 信号与简易回测 | 原代码缺 numpy 导入、用了未安装的 talib，**需重写** |
| `etf_rotation_draft_a.py` | strategy/bt_etf.py | ETF 轮动（选涨幅最高者满仓） | 有 NameError（未导入 datetime），数据源与标的不匹配 |
| `etf_rotation_draft_b.py` | backup/bt_etf.py | ETF 轮动（分位打分 + 仓位管理） | 更完整的草稿，被 a 版取代 |
| `memo_rolling_stats.md` | analyse/memo.md | 滚动窗口统计代码片段备忘 | 文档 |

阶段 2.3 计划：
- 形态/量能分析 → `quant/analysis/`
- ETF 轮动 → `quant/strategy/etf_rotation.py`（统一 backtrader，含手续费与基准对比）
