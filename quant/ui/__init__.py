"""桌面界面（阶段 2.4）。

分层：
    viewmodels.py  取数 / 过滤 / 导出（纯 pandas，可无头单测）
    charts.py      数据 -> matplotlib Figure
    widgets.py     wx 控件（表格 / 图表面板 / 指标卡 / 后台任务）
    screens/       各页面
    app.py         主窗口与导航

入口：`python -m quant ui`
"""

from __future__ import annotations

__all__ = ["main"]


def main() -> int:
    """启动桌面界面（延迟导入 wx，避免非 GUI 场景下报错）。"""
    from quant.ui.app import run

    return run()
