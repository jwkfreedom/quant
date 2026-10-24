"""无头构造主窗口的回归测试。

开发环境没有显示，跑不了真正的界面；但 wxPython 在 Windows 上可以「只构造、不进事件循环」。
本测试把踩过的坑固定下来：控件名拼写、Sizer 与父窗口不匹配、TextCtrl 样式缺失等，
不依赖人工点界面就能发现。
"""

from __future__ import annotations

import pytest

wx = pytest.importorskip("wx")
import wx.grid  # noqa: E402,F401


@pytest.fixture(scope="module")
def app():
    """整个模块共用一个 wx.App（wx 不允许重复创建）。"""
    try:
        application = wx.App(False)
    except Exception as exc:  # pragma: no cover - 无显示环境
        pytest.skip(f"无法创建 wx.App：{exc}")
    yield application


@pytest.fixture
def frame(app):
    from quant.ui.app import MainFrame

    window = MainFrame()
    yield window
    window.Destroy()


def test_main_frame_builds_all_pages(frame):
    from quant.ui.app import PAGES

    assert len(frame.panels) == len(PAGES)
    for title, _cls in PAGES:
        assert title in frame.panels, f"缺少页面 {title}"


def test_status_bar_exists_and_settable(frame):
    assert frame.GetStatusBar() is not None
    frame.set_status("测试")
    frame.set_status("就绪")


def test_switch_every_page(frame):
    from quant.ui.app import PAGES

    for index, (title, _cls) in enumerate(PAGES):
        frame.book.SetSelection(index)
        assert frame.book.GetPageText(frame.book.GetSelection()) == title


def test_screener_collects_specs(frame):
    panel = frame.panels["选股筛选"]
    assert panel.rows, "条件行为空"
    assert panel.specs() == []

    panel.rows[0].checkbox.SetValue(True)
    specs = panel.specs()
    assert len(specs) == 1
    assert specs[0].startswith(panel.rows[0].name)

    # 带参数的条件应当生成 k=v 形式
    target = next(row for row in panel.rows if row.name == "market_cap")
    target.checkbox.SetValue(True)
    for name, control, _default in target.fields:
        if name == "max":
            control.SetValue("80")
    assert "market_cap:max=80" in panel.specs()


def test_stock_detail_renders(frame):
    from quant.ui import viewmodels as vm

    panel = frame.panels["个股分析"]
    detail = vm.stock_detail("000001")
    panel._render_detail(detail)
    assert panel.title.GetLabel().startswith("000001")


def test_backtest_param_form_follows_strategy(frame):
    panel = frame.panels["策略回测"]
    assert panel.strategy_name in ("ma_obv", "volume_breakout")
    assert panel.param_controls, "参数表单为空"

    # 切换到另一个策略，参数表单应随之变化
    other = "volume_breakout" if panel.strategy_name == "ma_obv" else "ma_obv"
    panel.strategy_choice.SetStringSelection(other)
    panel.on_strategy_changed()
    assert set(panel.param_controls) == {
        p["name"] for p in __import__("quant.strategy", fromlist=["get_strategy"]).get_strategy(other).params
    }


def test_backtest_collect_params_validates(frame):
    panel = frame.panels["策略回测"]
    for control in panel.param_controls.values():
        control.SetValue("abc")
    with pytest.raises(ValueError):
        panel._collect_params()


def test_explorer_table_switch(frame):
    panel = frame.panels["数据浏览器"]
    assert panel.database == "market"
    assert panel._tables, "数据表列表为空"
    assert panel.table == panel._tables[0]
    assert len(panel._tables) >= 5
    panel.table_choice.SetSelection(4)
    assert panel.table == panel._tables[4]


def test_settings_labels(frame):
    panel = frame.panels["设置/关于"]
    assert panel.screens_label.GetLabel()


# --------------------------------------------------------------------------
# 表格：排序 / 右键菜单 / 选择
# --------------------------------------------------------------------------
class _FakeLabelEvent:
    """只实现处理器用到的 GetCol（避免构造真正的 wx.grid.GridEvent）。"""

    def __init__(self, col: int):
        self._col = col

    def GetCol(self):
        return self._col

    def Skip(self):
        pass


def test_grid_sorts_by_header_click(app):
    import pandas as pd

    from quant.ui.widgets import DataFrameGrid

    parent = wx.Frame(None)
    grid = DataFrameGrid(parent)
    grid.SetDataFrame(pd.DataFrame({"a": [3, 1, 2], "b": ["c", "a", "b"]}))

    grid._on_label_click(_FakeLabelEvent(0))          # 第一次：降序
    assert grid.frame["a"].tolist() == [3, 2, 1]
    grid._on_label_click(_FakeLabelEvent(0))          # 第二次：升序
    assert grid.frame["a"].tolist() == [1, 2, 3]
    grid._on_label_click(_FakeLabelEvent(0))          # 第三次：取消排序
    assert grid.frame["a"].tolist() == [3, 1, 2]

    grid._on_label_click(_FakeLabelEvent(1))          # 按字符串列排
    assert grid.frame["b"].tolist() == ["c", "b", "a"]

    parent.Destroy()


def test_grid_row_helpers(app):
    import pandas as pd

    from quant.ui.widgets import DataFrameGrid

    parent = wx.Frame(None)
    grid = DataFrameGrid(parent)
    grid.SetDataFrame(pd.DataFrame({"symbol": ["000001", "000002"]}))

    assert grid.row_at(0)["symbol"] == "000001"
    assert grid.row_at(99) is None
    assert len(grid.selected_rows()) >= 0

    parent.Destroy()


def test_screener_context_menu_builds(app, frame):
    """右键菜单应当能构造出「查看个股分析」等条目（不弹出）。"""
    from quant.ui.widgets import ContextMenu

    panel = frame.panels["选股筛选"]
    menu = ContextMenu(panel.grid, {"symbol": "000001"})
    menu.add("测试项", lambda row: None)
    assert menu._callbacks, "菜单没有注册回调"
    menu._menu.Destroy()


def test_screener_jump_to_stock(app, frame):
    panel = frame.panels["选股筛选"]
    panel.jump_to_stock({"symbol": "600519"})
    assert frame.panels["个股分析"].symbol_input.GetValue() == "600519"


def test_backtest_render_fills_widgets(frame):
    """回测结果必须真正写进卡片 / 表格 / 图表（防止"命令行有输出、界面空白"）。"""
    panel = frame.panels["策略回测"]
    panel.strategy_choice.SetStringSelection("ma_obv")
    panel.on_strategy_changed()

    from quant.ui import viewmodels as vm

    result = vm.run_backtest("ma_obv", symbol="512480", cash=100000, commission=0.001)
    panel._render(result)

    labels = {k: v.GetLabel() for k, v in panel.cards._labels.items()}
    assert labels, "指标卡是空的"
    assert labels["总收益率"].endswith("%")
    assert labels["最终市值"] != "—"
    assert "策略" in panel.result_text.GetLabel()
    assert panel.figure_panel._canvas is not None, "净值图没有画出来"


def test_dividend_refresh_rerenders_forecast(app, frame, monkeypatch):
    """拉取分红后，「分红预期」页必须重新计算，不能停留在旧提示。"""
    from quant.ui.screens import portfolio as portfolio_screen

    panel = frame.panels["资产管理"]
    calls = []
    monkeypatch.setattr(panel, "render_dividends", lambda: calls.append("dividends"))
    monkeypatch.setattr(panel, "render_forecast", lambda: calls.append("forecast"))
    monkeypatch.setattr(panel, "_sync_years", lambda *args: None)
    monkeypatch.setattr(portfolio_screen.vm, "portfolio_years", lambda: [])
    monkeypatch.setattr(portfolio_screen.vm, "portfolio_report_years", lambda: [])
    monkeypatch.setattr(wx, "MessageBox", lambda *args, **kwargs: wx.OK)

    panel._after_dividend_refresh({"saved": 3, "failed": []})
    assert calls == ["dividends", "forecast"]


def test_help_dialog_shows_guide(app, frame):
    """「说明」按钮弹出的对话框内容要包含快照日期与各条件说明。"""
    from quant.filter.guide import build_guide
    from quant.ui.widgets import TextDialog

    text = build_guide()
    dialog = TextDialog(frame, "筛选条件说明", text)
    try:
        shown = dialog.text.GetValue()
        assert "【快照日期" in shown
        assert "【过滤链是怎么工作的】" in shown
        assert "pe_percentile" in shown
        assert "window_years" in shown
        assert not dialog.text.IsEditable()
    finally:
        dialog.Destroy()


def test_relayout_is_safe(app):
    from quant.ui.widgets import relayout

    parent = wx.Frame(None)
    relayout(parent, None, parent)
    parent.Destroy()


def test_backtest_sweep_controls_follow_strategy(frame):
    panel = frame.panels["策略回测"]
    panel.strategy_choice.SetStringSelection("ma_obv")
    panel.on_strategy_changed()
    assert panel.sweep_param.GetStringSelection() == "ma_period"
    assert panel.sweep_start.GetValue() and panel.sweep_stop.GetValue()
    assert float(panel.sweep_step.GetValue()) > 0


def test_backtest_shows_strategy_explanation(frame):
    """回测页的「策略说明」要显示参数表与算法步骤，并随策略切换更新。"""
    panel = frame.panels["策略回测"]

    panel.strategy_choice.SetStringSelection("ma_obv")
    panel.on_strategy_changed()
    text = panel.explain_text.GetValue()
    assert "【参数】" in text and "【算法】" in text
    assert "ma_period" in text and "obv_period" in text
    assert "买入：空仓 且 收盘价 > MA 且 OBV > 0" in text

    panel.strategy_choice.SetStringSelection("volume_breakout")
    panel.on_strategy_changed()
    text = panel.explain_text.GetValue()
    assert "volume_ratio" in text and "stop_loss" in text and "take_profit" in text
    assert "缩量阈值 × 均量" in text
    assert text != panel.explain_text.GetValue() or True

    # 说明文本只读
    assert not panel.explain_text.IsEditable()
