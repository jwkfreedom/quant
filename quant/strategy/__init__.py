"""backtrader 策略集合。

阶段 2.1 只迁移了原有两个可运行策略；
原 strategy/bt_etf.py 因存在 NameError 且数据源与标的不匹配，
已移入 research/ 作为草稿保留，ETF 轮动策略将在阶段 2.3 重写。
"""

from quant.strategy.ma_obv import MAOBVStrategy, MyOBV, run_backtest as run_ma_obv
from quant.strategy.volume_breakout import VolumeBreakoutStrategy, run_backtest as run_volume_breakout

__all__ = [
    "MyOBV",
    "MAOBVStrategy",
    "run_ma_obv",
    "VolumeBreakoutStrategy",
    "run_volume_breakout",
]
