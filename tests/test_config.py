"""配置模块单测。"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

from quant import config


@pytest.fixture
def temp_dir():
    """自建临时目录（不使用 pytest 的 tmp_path，避免依赖系统临时目录）。"""
    path = Path(tempfile.mkdtemp(prefix="quant-test-"))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_project_root_contains_package():
    assert (config.PROJECT_ROOT / "quant" / "config.py").is_file()


def test_data_dir_default_is_under_project_root(monkeypatch):
    monkeypatch.delenv("QUANT_DATA_DIR", raising=False)
    assert config._path_env("QUANT_DATA_DIR", config.PROJECT_ROOT / "data") == config.PROJECT_ROOT / "data"


def test_path_env_override(monkeypatch, temp_dir):
    monkeypatch.setenv("QUANT_TEST_PATH", str(temp_dir))
    assert config._path_env("QUANT_TEST_PATH", Path("unused")) == temp_dir.resolve()

    monkeypatch.setenv("QUANT_TEST_PATH", "   ")
    assert config._path_env("QUANT_TEST_PATH", Path("fallback")) == Path("fallback")


def test_load_env_file_does_not_override_real_env(monkeypatch, temp_dir):
    env_file = temp_dir / ".env"
    env_file.write_text("# comment\nQUANT_UT_KEY=from_file\nQUANT_UT_EXIST=from_file\n", encoding="utf-8")

    monkeypatch.setenv("QUANT_UT_EXIST", "from_env")
    monkeypatch.delenv("QUANT_UT_KEY", raising=False)

    config.load_env_file(env_file)

    assert os.environ["QUANT_UT_KEY"] == "from_file"
    assert os.environ["QUANT_UT_EXIST"] == "from_env"


def test_load_env_file_missing_is_noop(temp_dir):
    config.load_env_file(temp_dir / "not-exists.env")  # 不应抛异常


def test_get_log_level_fallback(monkeypatch):
    monkeypatch.setenv("QUANT_LOG_LEVEL", "not-a-level")
    assert config.get_log_level() == 20  # logging.INFO
