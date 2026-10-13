"""pytest 公共 fixture。"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """自建临时目录。

    不使用 pytest 的 tmp_path：在受限环境下 pytest 的临时根目录可能不可写，
    这里直接用 tempfile.mkdtemp（必要时由 sitecustomize 放宽权限）。
    """
    path = Path(tempfile.mkdtemp(prefix="quant-test-"))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
