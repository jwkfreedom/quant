"""quant —— A股/美股选股研究与策略回测工具。

包结构（阶段 2.1 建立）::

    quant.config              配置（环境变量优先）
    quant.cli                 统一命令行入口
    quant.data                数据采集与落盘
    quant.foundation          基本面（三表合并、单季增长、TTM 估值）
    quant.price               行情读取与估值
    quant.strategy            backtrader 策略
    quant.filter              可插拔选股过滤器（阶段 2.3 实装）
    quant.trade               交易记录与模拟盘
    quant.ui                  桌面界面（阶段 2.4 实装）
"""

from quant.config import DATA_DIR, PROJECT_ROOT, __version__

__all__ = ["DATA_DIR", "PROJECT_ROOT", "__version__"]
