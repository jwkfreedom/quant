"""CLI 冒烟测试。"""

from __future__ import annotations

import pytest

from quant.cli import build_parser, main

SUBCOMMANDS = (
    "info", "check", "db-init", "db-stats", "db-migrate",
    "update-jibenmian", "update-price", "update-etf", "update-financial", "update-all",
    "rebuild-growth", "calc-growth",
)


@pytest.mark.parametrize("command", SUBCOMMANDS)
def test_parser_has_subcommand(command):
    args = build_parser().parse_args([command])
    assert callable(args.func)


def test_update_price_defaults():
    args = build_parser().parse_args(["update-price"])
    assert args.mode == "incremental"
    assert args.limit is None
    assert args.stock is None


def test_update_price_full_alias():
    args = build_parser().parse_args(["update-price", "--full", "--limit", "5"])
    assert args.full is True
    assert args.limit == 5


def test_db_migrate_flags():
    args = build_parser().parse_args(["db-migrate", "--archive", "--cleanup", "--yes"])
    assert args.archive and args.cleanup and args.yes


def test_rebuild_growth_defaults():
    args = build_parser().parse_args(["rebuild-growth"])
    assert args.season_start is None
    assert args.only_complete is False


def test_calc_growth_complete_only_default():
    assert build_parser().parse_args(["calc-growth"]).complete_only is True
    assert build_parser().parse_args(["calc-growth", "--all-stocks"]).complete_only is False


def test_info_command_runs(capsys):
    assert main(["info"]) == 0
    out = capsys.readouterr().out
    assert "DATA_DIR" in out


def test_portfolio_txn_delete_flag():
    args = build_parser().parse_args(["portfolio-txn", "--delete", "12"])
    assert args.delete == 12
    assert build_parser().parse_args(["portfolio-txn"]).delete is None


def test_portfolio_dividend_report_period_flag():
    args = build_parser().parse_args([
        "portfolio-dividend", "--add", "600519", "--report-period", "2025-12-31",
    ])
    assert args.report_period == "2025-12-31"
