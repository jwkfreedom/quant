"""CLI 冒烟测试。"""

from __future__ import annotations

from quant.cli import build_parser, main


def test_parser_has_all_subcommands():
    parser = build_parser()
    for command in (
        "info", "check", "download-jibenmian", "calc-growth",
        "download-price", "download-etf", "download-us",
    ):
        args = parser.parse_args([command])
        assert callable(args.func)


def test_calc_growth_defaults():
    args = build_parser().parse_args(["calc-growth"])
    assert args.from_year == 2021
    assert args.out is None


def test_download_price_mode():
    args = build_parser().parse_args(["download-price", "--mode", "yearly", "--limit", "5"])
    assert args.mode == "yearly"
    assert args.limit == 5


def test_info_command_runs(capsys):
    assert main(["info"]) == 0
    out = capsys.readouterr().out
    assert "DATA_DIR" in out
