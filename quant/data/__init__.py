"""数据采集与存储层。

包含：
    schema    数据契约（英文列名 + 中文展示名）
    store     SQLite 建表/读写
    frames    原始 DataFrame -> 可写库结构的规范化
    migrate   一次性 CSV -> SQLite 迁移与归档
    update    增量更新
    download_a / download_us   取数（akshare / yfinance）
    stockapi  雪球、东财 HTTP 接口
    fsutil    数据目录维护工具
    universe  标的池常量

注意：本模块**不**在包导入时加载子模块（避免 import quant.data 时拉起 akshare）。
请按需显式导入，例如 from quant.data import store。
"""

from __future__ import annotations

__all__: list[str] = []
