"""回测入口与结果对象单测。"""

from __future__ import annotations

import pytest

from quant.strategy import (
    REGISTRY,
    BacktestResult,
    default_params,
    get_strategy,
    list_strategies,
    register_strategy,
)


def test_registry_has_builtin_strategies():
    names = [info.name for info in list_strategies()]
    assert "ma_obv" in names
    assert "volume_breakout" in names


def test_every_strategy_declares_params():
    for info in list_strategies():
        assert info.default_symbol, f"{info.name} 缺少默认标的"
        assert info.description, f"{info.name} 缺少说明"
        assert info.runner is not None
        for param in info.params:
            for key in ("name", "label", "type", "default"):
                assert key in param, f"{info.name}.{param} 缺少 {key}"


def test_default_params():
    params = default_params("ma_obv")
    assert params == {"ma_period": 20, "obv_period": 14}


def test_every_strategy_has_rules():
    for info in list_strategies():
        assert info.rules, f"{info.name} 缺少算法说明（RULES）"
        assert len(info.rules) >= 3


def test_explain_contains_params_and_rules():
    text = get_strategy("ma_obv").explain()
    assert "【ma_obv】" in text
    assert "【参数】" in text
    assert "【算法】" in text
    assert "【默认标的】512480" in text
    for param in ("ma_period", "obv_period"):
        assert param in text
    # 算法步骤要编号，子项不参与编号
    assert "  1. " in text and "  2. " in text


def test_explain_handles_strategy_without_params():
    def fake_runner(symbol, **kwargs):
        return BacktestResult("fake", symbol, 1.0, 1.0)

    register_strategy("fake_no_params", fake_runner, default_symbol="000001",
                      description="无参数策略")
    try:
        text = get_strategy("fake_no_params").explain()
        assert "该策略没有可调参数" in text
        assert "尚未填写算法说明" in text
    finally:
        REGISTRY.pop("fake_no_params", None)


def test_get_strategy_unknown():
    with pytest.raises(KeyError):
        get_strategy("nope")


def test_register_custom_strategy():
    def fake_runner(symbol, **kwargs):
        return BacktestResult("fake", symbol, 1.0, 1.0)

    register_strategy("fake", fake_runner, default_symbol="000001",
                      description="测试用", params=[{"name": "p", "label": "P", "type": "int", "default": 1}])
    try:
        info = get_strategy("fake")
        assert info.default_symbol == "000001"
        assert info.params[0]["name"] == "p"
        assert info.runner("000002").symbol == "000002"
    finally:
        REGISTRY.pop("fake", None)


def test_result_metrics():
    result = BacktestResult("s", "000001", initial_cash=100000.0, final_value=120000.0,
                            trades=10, win_trades=6)
    assert result.return_pct == pytest.approx(20.0)
    assert result.win_rate == pytest.approx(60.0)


def test_result_metrics_without_trades():
    result = BacktestResult("s", "000001", initial_cash=100000.0, final_value=90000.0)
    assert result.return_pct == pytest.approx(-10.0)
    assert result.win_rate == 0.0


def test_result_report_contains_new_fields():
    result = BacktestResult("s", "000001", 100000.0, 110000.0, start="2023-01-01",
                            end="2023-12-31", bars=240, annual_return=10.0, sharpe=1.5)
    report = result.report()
    for text in ("策略", "总收益率", "年化收益", "夏普比率", "最大回撤", "10.00%"):
        assert text in report


def test_result_summary_dict():
    result = BacktestResult("s", "000001", 100000.0, 110000.0, trades=4, win_trades=2,
                            annual_return=9.5, sharpe=0.8)
    summary = result.metrics()
    assert summary["return_pct"] == pytest.approx(10.0)
    assert summary["trades"] == 4
    assert summary["win_rate"] == pytest.approx(50.0)
