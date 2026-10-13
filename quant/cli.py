"""quant 统一命令行入口。

数据流：取数 -> 归档原始件 -> 摄入 SQLite -> 派生表 -> 查询/回测

    quant info                        配置与依赖自检
    quant check                       数据体检（数据库 + 归档区）

    quant db-init                     建库建表
    quant db-migrate                  历史 CSV -> SQLite（可重复执行）
    quant db-migrate --archive        迁移后把原始 CSV 归档到 data/original/
    quant db-migrate --cleanup --yes  归档后删除已入库的行情 CSV（不可逆）
    quant db-stats                    查看各表行数

    quant update-jibenmian            补齐缺失季度并摄入
    quant update-price                追加最新日线（默认增量）
    quant update-etf                  追加 ETF 日线
    quant update-all                  一键按顺序全部更新
    quant rebuild-growth              重算单季增长表

    quant calc-growth                 导出单季增长 CSV（英文列名）
"""

from __future__ import annotations

import argparse
import importlib
import logging
import sys
from pathlib import Path

from quant import config

BASE_DEPS = [
    "akshare", "backtrader", "pandas", "numpy", "matplotlib", "scipy",
    "mplfinance", "yfinance", "requests", "openpyxl", "ta", "talib", "statsmodels",
]
OPTIONAL_DEPS = ["wx"]


def _human(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


# --------------------------------------------------------------------------
# info / check
# --------------------------------------------------------------------------
def cmd_info(_args: argparse.Namespace) -> int:
    """打印配置与依赖自检结果。"""
    print(f"quant {config.__version__}")
    print("-" * 62)
    for key, value in config.as_dict().items():
        print(f"{key:<14} {value}")

    print("-" * 62)
    print("依赖:")
    for name in BASE_DEPS:
        try:
            module = importlib.import_module(name)
            print(f"  OK   {name:<12} {getattr(module, '__version__', '?')}")
        except Exception as exc:
            print(f"  FAIL {name:<12} {type(exc).__name__}")

    for name in OPTIONAL_DEPS:
        try:
            module = importlib.import_module(name)
            print(f"  OK   {name:<12} {getattr(module, '__version__', '?')} (optional)")
        except Exception:
            print(f"  MISS {name:<12} (optional, UI 需要)")
    return 0


def cmd_check(_args: argparse.Namespace) -> int:
    """数据体检：数据库各表行数 + 归档区文件数。"""
    from quant.config import DATA_DIR, DB_PATH, ORIGINAL_DIR
    from quant.data import schema, store

    print(f"数据根目录: {DATA_DIR}  {'存在' if DATA_DIR.is_dir() else '不存在!'}")
    print(f"数据库    : {DB_PATH}  {'存在' if DB_PATH.is_file() else '不存在（先运行 quant db-init / db-migrate）'}")
    print("-" * 62)

    if DB_PATH.is_file():
        with store.open_db() as conn:
            counts = store.stats(conn)
            for table in schema.ALL_TABLES:
                if table == schema.TABLE_META:
                    continue
                print(f"  {table:<22} {counts.get(table, 0):>12,} 行")

            if counts.get(schema.TABLE_DAILY_PRICE):
                row = conn.execute(
                    f"SELECT COUNT(DISTINCT symbol), MIN(date), MAX(date) FROM {schema.TABLE_DAILY_PRICE}"
                ).fetchone()
                print(f"  日线覆盖: {row[0]} 只股票, {row[1]} ~ {row[2]}")
            if counts.get(schema.TABLE_FUNDAMENTAL):
                row = conn.execute(
                    f"SELECT COUNT(DISTINCT symbol), COUNT(DISTINCT season), MIN(season), MAX(season) "
                    f"FROM {schema.TABLE_FUNDAMENTAL}"
                ).fetchone()
                print(f"  基本面覆盖: {row[0]} 只股票, {row[1]} 个季度, {row[2]} ~ {row[3]}")
            version = store.get_meta(conn, "schema_version")
            print(f"  schema_version: {version}（代码要求 {schema.SCHEMA_VERSION}）")

            prices = conn.execute(f"SELECT COUNT(*) FROM {schema.TABLE_DAILY_PRICE}").fetchone()[0]
            if prices == 0:
                print("  ! 日线为空：先运行 quant db-migrate")
            stocks = conn.execute(f"SELECT COUNT(*) FROM {schema.TABLE_STOCK_LIST}").fetchone()[0]
            if stocks == 0:
                print("  ! 股票列表为空：迁移后运行一次 quant db-migrate")
    else:
        print("  （数据库不存在，跳过）")

    print("-" * 62)
    print("归档区 data/original:")
    if ORIGINAL_DIR.is_dir():
        for sub in sorted(p for p in ORIGINAL_DIR.iterdir() if p.is_dir()):
            files = [f for f in sub.rglob("*") if f.is_file()]
            size = sum(f.stat().st_size for f in files)
            print(f"  {sub.name:<20} {len(files):>7} 个文件   {_human(size)}")
    else:
        print("  （尚无归档，运行 quant db-migrate --archive）")
    return 0


# --------------------------------------------------------------------------
# 数据库
# --------------------------------------------------------------------------
def cmd_db_init(_args: argparse.Namespace) -> int:
    from quant.data import store

    path = store.init_db()
    print(f"数据库已就绪: {path}")
    return 0


def cmd_db_stats(_args: argparse.Namespace) -> int:
    from quant.config import DB_PATH
    from quant.data import schema, store

    if not DB_PATH.is_file():
        print(f"数据库不存在: {DB_PATH}；先运行 quant db-init")
        return 1

    with store.open_db() as conn:
        for table in schema.ALL_TABLES:
            if table == schema.TABLE_META:
                continue
            print(f"{table:<24} {store.table_count(conn, table):>12,}")
    return 0


def cmd_db_migrate(args: argparse.Namespace) -> int:
    from quant.data import migrate, store

    store.init_db()
    with store.open_db() as conn:
        result = migrate.run_all(
            conn,
            price_limit=args.price_limit,
            financial_limit=args.financial_limit,
        )
    print("-" * 62)
    for key, value in result.items():
        print(f"{key:<14} {value}")

    if args.archive or args.cleanup:
        print("-" * 62)
        moved = migrate.archive_originals()
        total = sum(moved.values())
        for path, size in moved.items():
            print(f"归档 {path}  {_human(size)}")
        print(f"共归档 {_human(total)}")

    if args.cleanup:
        freed = migrate.cleanup_sources(dry_run=not args.yes)
        print("-" * 62)
        total = sum(freed.values())
        for path, size in freed.items():
            action = "已删除" if args.yes else "将删除(加 --yes 执行)"
            print(f"{action} {path}  {_human(size)}")
        print(f"合计 {_human(total)}")
        if not args.yes:
            print("提示：确认数据无误后加 --yes 真正删除。")
    return 0


# --------------------------------------------------------------------------
# 更新
# --------------------------------------------------------------------------
def cmd_update_jibenmian(args: argparse.Namespace) -> int:
    from quant.data import update

    result = update.update_jibenmian(
        args.from_year, args.to_year, tuple(args.tables), force=args.force, delay=args.delay
    )
    print("-" * 62)
    print(f"目标季度: {len(result.get('seasons', []))} 个，新下载 {result.get('downloaded', 0)} 个文件")
    print(f"摄入数据库: {result.get('rows', 0)} 行 / {result.get('ingested_seasons', 0)} 个季度")
    return 0


def cmd_update_price(args: argparse.Namespace) -> int:
    from quant.data import update

    mode = "full" if args.full else args.mode
    result = update.update_price(
        args.stock, mode=mode, start=args.start, limit=args.limit, delay=args.delay
    )
    print("-" * 62)
    print(f"模式 {result['mode']}：处理 {result['symbols']} 只，更新 {result['updated']} 只，"
          f"跳过 {result['skipped']} 只，新增 {result['rows']} 行")
    if result["failures"]:
        print(f"失败 {len(result['failures'])} 只: {result['failures'][:10]}")
    return 0


def cmd_update_etf(args: argparse.Namespace) -> int:
    from quant.data import update

    result = update.update_etf(args.symbol, start=args.start, end=args.end, delay=args.delay)
    print("-" * 62)
    print(f"ETF：处理 {result['symbols']} 只，更新 {result['updated']} 只，新增 {result['rows']} 行")
    if result["failures"]:
        print(f"失败 {len(result['failures'])} 只: {result['failures'][:10]}")
    return 0


def cmd_update_all(args: argparse.Namespace) -> int:
    from quant.data import update

    result = update.update_all(price_limit=args.price_limit)
    print("-" * 62)
    for key, value in result.items():
        print(f"{key:<12} {value}")
    return 0


def cmd_rebuild_growth(args: argparse.Namespace) -> int:
    from quant.data import update

    result = update.rebuild_growth(
        season_start=args.season_start, drop_broken=args.only_complete
    )
    print("-" * 62)
    print(f"单季增长表: {result.get('rows', 0)} 行 / {result.get('symbols', 0)} 只股票")
    if result.get("message"):
        print(result["message"])
    return 0


def cmd_calc_growth(args: argparse.Namespace) -> int:
    """导出单季增长 CSV（英文列名）。

    口径与重构前的 calc_a_growth 一致：读取指定起始年以后的季度 ->
    剔除季度不全的股票 -> 计算单季增长 -> 导出。
    """
    from quant.data import store
    from quant.foundation import growth as growth_module

    season_start = int(f"{args.from_year}0101")
    with store.open_db() as conn:
        raw = store.read_fundamental(conn, season_start, None)

    if raw.empty:
        print(f"数据库中没有 {season_start} 之后的基本面数据")
        return 1

    df = growth_module.rm_broken_stocks(raw) if args.complete_only else raw
    df = growth_module.compute_growth(df)

    columns = ["symbol", "season", *[c for c in raw.columns if c not in ("symbol", "season")],
               "pre_year_income", "season_income", "season_income_growth",
               "pre_year_profit", "season_profit", "season_profit_growth"]
    df = df.loc[:, [c for c in columns if c in df.columns]]

    if args.legacy_columns:
        from quant.data.schema import LEGACY_GROWTH_COLUMN_MAP

        df = df.rename(columns=LEGACY_GROWTH_COLUMN_MAP)

    out = Path(args.out) if args.out else (config.DATA_DIR / f"{args.from_year}01-lastseason.csv")
    df.to_csv(out, index=False, encoding="utf_8_sig")
    seasons = df["season"].nunique() if "season" in df.columns else "?"
    print(f"已导出 {out} ({len(df)} 行, {seasons} 个季度)")
    return 0


# --------------------------------------------------------------------------
# 参数解析
# --------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quant", description="A股/美股选股研究与策略回测工具")
    parser.add_argument("--version", action="version", version=f"quant {config.__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("info", help="打印配置与依赖自检").set_defaults(func=cmd_info)
    sub.add_parser("check", help="数据体检（数据库 + 归档区）").set_defaults(func=cmd_check)

    # --- 数据库 ---
    sub.add_parser("db-init", help="建库建表").set_defaults(func=cmd_db_init)
    sub.add_parser("db-stats", help="查看各表行数").set_defaults(func=cmd_db_stats)

    p = sub.add_parser("db-migrate", help="历史 CSV 迁移到 SQLite")
    p.add_argument("--price-limit", type=int, default=None, help="只迁移前 N 只股票的日线（试跑用）")
    p.add_argument("--financial-limit", type=int, default=None, help="只迁移前 N 只财务指标")
    p.add_argument("--archive", action="store_true", help="迁移后把原始 CSV 归档到 data/original/")
    p.add_argument("--cleanup", action="store_true", help="归档后删除已入库的行情 CSV（需配 --yes）")
    p.add_argument("--yes", action="store_true", help="确认执行删除")
    p.set_defaults(func=cmd_db_migrate)

    # --- 更新 ---
    p = sub.add_parser("update-jibenmian", help="补齐缺失季度并摄入数据库")
    p.add_argument("--from-year", type=int, default=None, help="起始年，默认从库中最新季度继续")
    p.add_argument("--to-year", type=int, default=None, help="结束年（含），默认今年")
    p.add_argument("--tables", nargs="+", default=["zcfz", "lrb", "xjll"], choices=["zcfz", "lrb", "xjll"])
    p.add_argument("--force", action="store_true", help="已存在的季度文件也重新下载")
    p.add_argument("--delay", type=float, default=3.0, help="每次请求间隔秒数")
    p.set_defaults(func=cmd_update_jibenmian)

    p = sub.add_parser("update-price", help="追加最新日线")
    p.add_argument("--stock", nargs="+", default=None, help="指定股票代码，缺省为全市场")
    p.add_argument("--limit", type=int, default=None, help="只处理前 N 只（试跑用）")
    p.add_argument("--mode", choices=["incremental", "full"], default="incremental")
    p.add_argument("--full", action="store_true", help="等同于 --mode full")
    p.add_argument("--start", default="20100101", help="full 模式或首次入库的起始日期")
    p.add_argument("--delay", type=float, default=0.3, help="每只股票请求间隔秒数")
    p.set_defaults(func=cmd_update_price)

    p = sub.add_parser("update-etf", help="追加 ETF 日线")
    p.add_argument("--symbol", nargs="+", default=None)
    p.add_argument("--start", default="20180101")
    p.add_argument("--end", default=None)
    p.add_argument("--delay", type=float, default=0.3)
    p.set_defaults(func=cmd_update_etf)

    p = sub.add_parser("update-all", help="一键更新（基本面 -> 增长 -> 日线 -> ETF）")
    p.add_argument("--price-limit", type=int, default=None)
    p.set_defaults(func=cmd_update_all)

    p = sub.add_parser("rebuild-growth", help="从 fundamental 重算单季增长表")
    p.add_argument("--season-start", type=int, default=None, help="只重算该季度及以后（YYYYMMDD）")
    p.add_argument("--only-complete", action="store_true",
                   help="只保留所有季度都完整的股票（默认全市场，缺失季度留空）")
    p.set_defaults(func=cmd_rebuild_growth)

    p = sub.add_parser("calc-growth", help="导出单季增长 CSV（与旧 calc_a_growth 同口径）")
    p.add_argument("--from-year", type=int, default=2021)
    p.add_argument("--out", default=None)
    p.add_argument("--all-stocks", dest="complete_only", action="store_false",
                   help="不剔除季度不全的股票（默认剔除，与旧实现一致）")
    p.add_argument("--legacy-columns", action="store_true", help="输出旧版中文列名")
    p.set_defaults(func=cmd_calc_growth, complete_only=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 主函数，返回进程退出码。"""
    config.setup_logging(logging.INFO)
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
