"""选股过滤器注册表单测。"""

from __future__ import annotations

import pandas as pd
import pytest

from quant import filter as filter_module
from quant.filter import Filter, available_filters, clear_registry, get_filters, register


class SmallCap:
    name = "small_cap"
    description = "市值小于 80 亿"

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        return df[df["market_cap"] < 8e9]


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_registry()
    yield
    clear_registry()


def test_register_and_get():
    register(SmallCap())
    assert available_filters() == ["small_cap"]

    df = pd.DataFrame({"market_cap": [1e9, 1e10]})
    result = get_filters(["small_cap"])[0].apply(df)
    assert len(result) == 1


def test_get_unknown_filter():
    with pytest.raises(KeyError):
        get_filters(["nope"])


def test_protocol_conformance():
    assert isinstance(SmallCap(), Filter)
