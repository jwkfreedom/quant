"""资产管理：账户 / 持仓 / 买卖 / 分红 / 风险统计。

使用示例
--------
>>> from quant.portfolio import init_db, open_db, Portfolio
>>> init_db()
>>> with open_db() as conn:
...     book = Portfolio(conn)
...     owner = book.create_owner("王大")
...     account = book.add_account(owner, "华泰证券", currency="CNY")
...     book.deposit(account, 100000)
...     book.buy(account, kind="stock", market="CN", symbol="600519",
...              quantity=100, price=1500, name="贵州茅台", fee=15)
"""

from quant.portfolio.schema import (  # noqa: F401
    ACTION_NAMES,
    ACTIONS,
    BASE_CURRENCY,
    CURRENCIES,
    DEFAULT_RISK,
    KIND_NAMES,
    KINDS,
    MARKET_CURRENCY,
    MARKET_NAMES,
    MARKETS,
    RISK_COLOURS,
    RISK_NAMES,
    RISKS,
    SCHEMA_VERSION,
)
from quant.portfolio.service import Portfolio  # noqa: F401
from quant.portfolio.store import (  # noqa: F401
    connect,
    ensure_schema,
    init_db,
    open_db,
)

__all__ = [
    "Portfolio", "connect", "open_db", "init_db", "ensure_schema",
    "ACTIONS", "ACTION_NAMES", "KINDS", "KIND_NAMES", "MARKETS", "MARKET_NAMES",
    "MARKET_CURRENCY", "CURRENCIES", "RISKS", "RISK_NAMES", "RISK_COLOURS",
    "DEFAULT_RISK", "BASE_CURRENCY", "SCHEMA_VERSION",
]
