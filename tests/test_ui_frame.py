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
    from quant.ui import viewmodels as vm

    panel = frame.panels["数据浏览器"]
    assert panel.table == vm.EXPLORER_TABLES[0]
    panel.table_choice.SetSelection(4)
    assert panel.table == vm.EXPLORER_TABLES[4]


def test_settings_labels(frame):
    panel = frame.panels["设置/关于"]
    assert panel.screens_label.GetLabel()
