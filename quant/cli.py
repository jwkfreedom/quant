"""quant 统一命令行入口。

用法::

    python -m quant info
    python -m quant check
    python -m quant download-jibenmian --start-year 2023 --end-year 2024 --season 0331
    python -m quant calc-growth --from-year 2021 --out data/202101-lastseason.csv
    python -m quant download-price --mode cur
    python -m quant download-price --mode yearly
    python -m quant download-etf --start 20180101 --end 20230201
    python -m quant download-us

安装为可编辑包后也可直接使用 quant 命令（见 pyproject.toml 的 project.scripts）。
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

from quant import config

BASE_DEPS = [
    "akshare", "backtrader", "pandas", "numpy", "matplotlib", "scipy",
    "mplfinance", "yfinance", "requests", "openpyxl", "ta", "talib", "statsmodels",
]
OPTIONAL_DEPS = ["wx"]


# --------------------------------------------------------------------------
# info / check
# --------------------------------------------------------------------------
def cmd_info(_args: argparse.Namespace) -> int:
    """打印配置与依赖自检结果。"""
    print(f"quant {config.__version__}")
    print("-" * 60)
    for key, value in config.as_dict().items():
        print(f"{key:<14} {value}")

    print("-" * 60)
    print("依赖:")
    for name in BASE_DEPS:
        try:
            module = importlib.import_module(name)
            version = getattr(module, "__version__", "?")
            print(f"  OK   {name:<12} {version}")
        except Exception as exc:
            print(f"  FAIL {name:<12} {type(exc).__name__}")

    for name in OPTIONAL_DEPS:
        try:
            module = importlib.import_module(name)
            print(f"  OK   {name:<12} {getattr(module, '__version__', '?')} (optional)")
        except Exception:
            print(f"  MISS {name:<12} (optional, 阶段 2.4 需要)")
    return 0


def cmd_check(_args: argparse.Namespace) -> int:
    """数据目录体检：文件数量、季度覆盖、缺失的价格文件。"""
    data_dir = config.DATA_DIR
    print(f"数据根目录: {data_dir}  {'存在' if data_dir.is_dir() else '不存在!'}")
    if not data_dir.is_dir():
        return 1

    jbm_dir = data_dir / "a" / "jibenmian"
    print("-" * 60)
    print("基本面 (data/a/jibenmian):")
    for table in ("zcfz", "lrb", "xjll"):
        files = sorted(jbm_dir.glob(f"{table}_*.csv")) if jbm_dir.is_dir() else []
        if files:
            seasons = [f.stem.split("_")[1] for f in files]
            print(f"  {table}: {len(files)} 个文件, {seasons[0]} ~ {seasons[-1]}")
        else:
            print(f"  {table}: 无数据")

    price_dir = data_dir / "a" / "stock" / "price"
    print("-" * 60)
    print("行情 (data/a/stock/price):")
    if price_dir.is_dir():
        pre = {f.name[len("price_"):-len("_pre.csv")] for f in price_dir.glob("price_*_pre.csv")}
        cur = {f.name[len("price_"):-len("_cur.csv")] for f in price_dir.glob("price_*_cur.csv")}
        print(f"  pre: {len(pre)} 只, cur: {len(cur)} 只")
        only_cur = sorted(cur - pre)
        only_pre = sorted(pre - cur)
        print(f"  只有 cur 的股票: {len(only_cur)} 只" + (f"  例: {only_cur[:5]}" if only_cur else ""))
        print(f"  只有 pre 的股票: {len(only_pre)} 只" + (f"  例: {only_pre[:5]}" if only_pre else ""))
        if only_cur:
            print("  ! 这些股票无法被 get_stock_price 读取（需要补 pre 文件）")
    else:
        print("  无数据")

    financial_dir = data_dir / "a" / "stock" / "financial"
    etf_dir = data_dir / "a" / "etf" / "price"
    print("-" * 60)
    print("其他:")
    print(f"  financial: {len(list(financial_dir.glob('*.csv'))) if financial_dir.is_dir() else 0} 个文件")
    print(f"  etf price: {len(list(etf_dir.glob('*.csv'))) if etf_dir.is_dir() else 0} 个文件")
    return 0


# --------------------------------------------------------------------------
# 下载
# --------------------------------------------------------------------------
def cmd_download_jibenmian(args: argparse.Namespace) -> int:
    """下载全市场季度基本面（业绩快报）。"""
    from quant.data import download_a

    seasons = [f"{{year}}{s}" for s in args.season]
    for table in args.tables:
        print(f"[{table}] {args.start_year} ~ {args.end_year - 1}, 季度 {args.season}")
        download_a.jibenmian_all_fast(table, args.start_year, args.end_year, seasons)
    return 0


def cmd_calc_growth(args: argparse.Namespace) -> int:
    """合并基本面三表并计算单季增长，导出 CSV。"""
    from quant.foundation import growth

    print(f"开始计算增长数据...(起始年: {args.from_year})")
    df = growth.load_jibenmian(str(args.from_year) + "-01-01")
    df = growth.rm_broken_stocks(df)
    df = growth.growth_score(df)
    if df is None:
        print("计算失败：首个季度必须是 XXXX0331")
        return 1

    out = Path(args.out) if args.out else (config.DATA_DIR / f"{args.from_year}01-lastseason.csv")
    df.to_csv(out, index=False, encoding="utf_8_sig")
    print(f"已导出 {out} ({len(df)} 行)")
    return 0


def cmd_download_price(args: argparse.Namespace) -> int:
    """下载日线数据。"""
    from quant.data import download_a, fsutil

    if args.stock:
        for stock_id in args.stock:
            download_a.stock_price(stock_id, down_preyear=(args.mode == "yearly"), force=args.force)
        return 0

    stock_ids = download_a.all_a_stocks()
    if args.limit:
        stock_ids = stock_ids[: args.limit]

    if args.mode == "yearly":
        print("归档现有 pre/cur 文件到 temp 目录 ...")
        fsutil.clear_price_a_files("pre")
        fsutil.clear_price_a_files("cur")
        down_pre = True
    else:
        print("归档现有 cur 文件到 temp 目录 ...")
        fsutil.clear_price_a_files("cur")
        down_pre = False

    print(f"开始下载 {len(stock_ids)} 只股票的日线 (down_pre={down_pre}) ...")
    for index, stock_id in enumerate(stock_ids, 1):
        print(f"[{index}/{len(stock_ids)}] {stock_id}")
        download_a.stock_price(stock_id, down_pre, force=args.force)
    return 0


def cmd_download_etf(args: argparse.Namespace) -> int:
    """下载 ETF 日线。"""
    from quant.data import download_a

    download_a.download_etf(start_date=args.start, end_date=args.end)
    return 0


def cmd_download_us(args: argparse.Namespace) -> int:
    """下载知名美股清单。"""
    from quant.data import download_us

    download_us.good_stocks(args.out)
    return 0


# --------------------------------------------------------------------------
# 参数解析
# --------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quant", description="A股/美股选股研究与策略回测工具")
    parser.add_argument("--version", action="version", version=f"quant {config.__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("info", help="打印配置与依赖自检").set_defaults(func=cmd_info)
    sub.add_parser("check", help="数据目录体检").set_defaults(func=cmd_check)

    p = sub.add_parser("download-jibenmian", help="下载全市场季度基本面")
    p.add_argument("--start-year", type=int, default=2023)
    p.add_argument("--end-year", type=int, default=2024, help="结束年（不含）")
    p.add_argument("--tables", nargs="+", default=["zcfz", "lrb", "xjll"], choices=["zcfz", "lrb", "xjll"])
    p.add_argument("--season", nargs="+", default=["0331", "0630", "0930", "1231"])
    p.set_defaults(func=cmd_download_jibenmian)

    p = sub.add_parser("calc-growth", help="计算基本面单季增长并导出 CSV")
    p.add_argument("--from-year", type=int, default=2021)
    p.add_argument("--out", default=None, help="输出路径，默认 <DATA_DIR>/<from-year>01-lastseason.csv")
    p.set_defaults(func=cmd_calc_growth)

    p = sub.add_parser("download-price", help="下载日线数据")
    p.add_argument("--mode", choices=["cur", "yearly"], default="cur")
    p.add_argument("--stock", nargs="+", default=None, help="指定股票代码，缺省为全市场")
    p.add_argument("--limit", type=int, default=None, help="只处理前 N 只（调试用）")
    p.add_argument("--force", action="store_true", help="强制重下当年数据")
    p.set_defaults(func=cmd_download_price)

    p = sub.add_parser("download-etf", help="下载 ETF 日线")
    p.add_argument("--start", default="20180101")
    p.add_argument("--end", default="20230201")
    p.set_defaults(func=cmd_download_etf)

    p = sub.add_parser("download-us", help="下载知名美股清单")
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_download_us)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 主函数，返回进程退出码。"""
    config.setup_logging()
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
