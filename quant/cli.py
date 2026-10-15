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
    quant update-financial            更新财务指标（逐股，慢）
    quant update-all                  一键按顺序全部更新
    quant rebuild-growth              重算单季增长表
    quant rebuild-ttm                 回填 fundamental 的 TTM 列
    quant rebuild-valuation           重建估值历史分位表

    quant calc-growth                 导出单季增长 CSV（英文列名）

    quant screen                      按过滤链选股（--list 查看可用过滤器）
    quant filter-guide                筛选条件说明书（参数含义与例子）
    quant backtest                    运行策略回测（--list 查看可用策略）

    quant ui [symbol]                 启动桌面界面
"""

from __future__ import annotations

import argparse
import importlib
import logging
import sys
from pathlib import Path

import pandas as pd

from quant import config
from quant import query as quant_query

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
        args.stock, mode=mode, start=args.start, limit=args.limit,
        delay=args.delay, workers=args.workers, timeout=args.timeout, source=args.source,
    )
    print("-" * 62)
    print(f"模式 {result['mode']}：处理 {result['symbols']} 只，更新 {result['updated']} 只，"
          f"跳过 {result['skipped']} 只，新增 {result['rows']:,} 行")
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


def cmd_update_financial(args: argparse.Namespace) -> int:
    from quant.data import update

    result = update.update_financial(
        args.stock, limit=args.limit, delay=args.delay,
        workers=args.workers, timeout=args.timeout,
        stale_days=args.stale_days, skip_unchanged=not args.force,
    )
    print("-" * 62)
    print(f"财务指标：处理 {result['symbols']} 只，更新 {result['updated']} 只，"
          f"跳过 {result['skipped']} 只，写入 {result['rows']} 行")
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


def cmd_filter_guide(args: argparse.Namespace) -> int:
    """打印筛选条件说明书（与界面「说明」按钮内容一致）。"""
    from quant.filter.guide import FILTER_GUIDE, build_guide, describe_filter

    if args.filter:
        for name in args.filter:
            print(describe_filter(name))
            print()
        return 0

    if args.list:
        for name in sorted(FILTER_GUIDE):
            print(f"{name:<18}{FILTER_GUIDE[name].get('intro', '')}")
        return 0

    print(build_guide())
    return 0


def cmd_ui(args: argparse.Namespace) -> int:
    """启动桌面界面。"""
    try:
        import wx  # noqa: F401
    except ImportError:
        print("未安装 wxPython，无法启动桌面界面。")
        print(r"安装： .venv\Scripts\python.exe -m pip install wxPython")
        return 1

    from quant.ui.app import run

    argv = [args.symbol] if args.symbol else []
    return run(argv)


def cmd_rebuild_ttm(_args: argparse.Namespace) -> int:
    """回填 fundamental 的 TTM 列（PS 需要）。"""
    from quant.data import store
    from quant.foundation.valuation import rebuild_fundamental_ttm

    with store.open_db() as conn:
        result = rebuild_fundamental_ttm(conn)
    print("-" * 62)
    print(f"TTM 回填：{result.get('rows', 0):,} 行 / {result.get('symbols', 0)} 只股票")
    return 0


def cmd_rebuild_valuation(args: argparse.Namespace) -> int:
    """重建估值历史分位表。"""
    from quant.data import store
    from quant.foundation.valuation import rebuild_fundamental_ttm, rebuild_valuation

    with store.open_db() as conn:
        ttm = rebuild_fundamental_ttm(conn)
        print(f"TTM 回填：{ttm.get('rows', 0):,} 行")
        result = rebuild_valuation(
            args.stock,
            windows=tuple(args.windows),
            limit=args.limit,
            workers=args.workers,
            conn=conn,
        )

    print("-" * 62)
    print(f"估值分位：{result['symbols']} 只股票，写入 {result['rows']:,} 行，"
          f"用时 {result['elapsed_seconds']:.0f}s")
    if result["failures"]:
        print(f"失败 {len(result['failures'])} 只: {result['failures'][:10]}")
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
# 选股与回测
# --------------------------------------------------------------------------
def cmd_screen(args: argparse.Namespace) -> int:
    """按过滤链选股。"""
    from quant.filter import FilterChain, FilterContext, describe_filters

    if args.list:
        print("可用过滤器：")
        for name, description in describe_filters():
            print(f"  {name:<16} {description}")
        print("\n用法示例： quant screen --filter exclude_st --filter market_cap:max=80 "
              "--filter growth:min=30")
        return 0

    if not args.filter:
        print("没有指定 --filter，将输出全市场快照（可用 --limit 限制行数）")

    chain = FilterChain.from_specs(args.filter or [])
    as_of = int(args.as_of) if args.as_of else None

    with FilterContext(as_of=as_of) as ctx:
        if as_of is None:
            ctx.as_of = int(quant_query.latest_trading_date(ctx.conn).replace("-", ""))
        result = chain.run(ctx)
        as_of = ctx.as_of

    if not args.filter:
        result = type(result)(frame=result.frame, steps=result.steps, as_of=as_of)

    print(result.report())

    frame = result.frame
    if args.sort and args.sort in frame.columns:
        frame = frame.sort_values(args.sort, ascending=args.ascending)
    if args.limit:
        frame = frame.head(args.limit)

    columns = args.columns or ["symbol", "name", "close_org", "market_cap", "pe", "pb"]
    columns = [c for c in columns if c in frame.columns]
    preview = frame.loc[:, columns] if columns else frame

    if args.display_columns:
        from quant.data import schema

        preview = schema.rename_for_display(preview)

    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 50)
    print()
    if len(preview):
        print(preview.to_string(index=False))
    else:
        print("（没有符合条件的股票）")

    if args.out:
        out = Path(args.out)
        frame.to_csv(out, index=False, encoding="utf_8_sig")
        print(f"\n已导出 {out}（{len(frame)} 行）")
    return 0


def cmd_backtest(args: argparse.Namespace) -> int:
    """运行策略回测。"""
    from quant.strategy import default_params, get_strategy, list_strategies, run_backtest

    if args.list:
        print("可用策略：")
        for info in list_strategies():
            print(f"  {info.name:<18} 默认标的 {info.default_symbol:<8} {info.description}")
            for param in info.params:
                print(f"      --{param['name']:<14} {param.get('label', '')} "
                      f"(默认 {param.get('default')})")
        return 0

    if not args.strategy:
        print("请用 --strategy 指定策略（或用 --list 查看全部）")
        return 1

    # 未显式给出的参数用策略默认值
    info = get_strategy(args.strategy)
    params = default_params(args.strategy)
    for param in info.params:
        value = getattr(args, param["name"], None)
        if value is not None:
            params[param["name"]] = value

    result = run_backtest(
        args.strategy,
        symbol=args.symbol,
        cash=args.cash,
        commission=args.commission,
        plot=args.plot,
        **params,
    )
    print()
    print(result.report())
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
    p.add_argument("--workers", type=int, default=4, help="并发抓取线程数（写库仍是单线程）")
    p.add_argument("--timeout", type=float, default=40.0, help="单次请求 socket 超时（秒）")
    p.add_argument("--source", choices=["auto", "eastmoney", "sina"], default="auto",
                   help="数据源：auto 先试东财、失败自动改用新浪")
    p.set_defaults(func=cmd_update_price)

    p = sub.add_parser("update-etf", help="追加 ETF 日线")
    p.add_argument("--symbol", nargs="+", default=None)
    p.add_argument("--start", default="20180101")
    p.add_argument("--end", default=None)
    p.add_argument("--delay", type=float, default=0.3)
    p.set_defaults(func=cmd_update_etf)

    p = sub.add_parser("update-financial", help="更新财务指标（逐股，较慢，建议后台跑）")
    p.add_argument("--stock", nargs="+", default=None, help="指定股票代码，缺省为股票列表全部")
    p.add_argument("--limit", type=int, default=None, help="只处理前 N 只（试跑用）")
    p.add_argument("--delay", type=float, default=0.2, help="每只股票请求间隔秒数")
    p.add_argument("--workers", type=int, default=3, help="并发抓取线程数（写库仍是单线程，建议不超过 4）")
    p.add_argument("--timeout", type=float, default=40.0, help="单次请求的 socket 超时（秒）")
    p.add_argument("--stale-days", type=int, default=None,
                   help="只更新「最新报告期早于 N 天前或没有数据」的股票（推荐日常增量用）")
    p.add_argument("--force", action="store_true", help="即使库中已是最新报告期也重写")
    p.set_defaults(func=cmd_update_financial)

    p = sub.add_parser("update-all", help="一键更新（基本面 -> 增长 -> 日线 -> ETF）")
    p.add_argument("--price-limit", type=int, default=None)
    p.set_defaults(func=cmd_update_all)

    p = sub.add_parser("rebuild-growth", help="从 fundamental 重算单季增长表")
    p.add_argument("--season-start", type=int, default=None, help="只重算该季度及以后（YYYYMMDD）")
    p.add_argument("--only-complete", action="store_true",
                   help="只保留所有季度都完整的股票（默认全市场，缺失季度留空）")
    p.set_defaults(func=cmd_rebuild_growth)

    # --- 选股 / 回测 ---
    p = sub.add_parser("screen", help="按过滤链选股")
    p.add_argument("--filter", action="append", default=[],
                   help="过滤器，格式 name 或 name:k=v,k=v，可重复，例如 "
                        "market_cap:max=80  growth:field=season_income_growth,min=30")
    p.add_argument("--as-of", default=None, help="快照日期 YYYYMMDD，缺省用库中最新交易日")
    p.add_argument("--sort", default=None, help="按某列排序")
    p.add_argument("--asc", dest="ascending", action="store_true", help="升序（默认降序）")
    p.add_argument("--limit", type=int, default=20, help="只打印前 N 行（默认 20，0 表示全部）")
    p.add_argument("--columns", nargs="+", default=None, help="打印哪些列")
    p.add_argument("--display-columns", action="store_true", help="列名用中文展示名")
    p.add_argument("--out", default=None, help="导出 CSV 路径")
    p.add_argument("--list", action="store_true", help="列出所有可用过滤器")
    p.set_defaults(func=cmd_screen)

    p = sub.add_parser("backtest", help="运行策略回测")
    p.add_argument("--strategy", default=None, help="策略名（--list 查看）")
    p.add_argument("--symbol", default=None, help="标的代码，缺省用策略默认标的")
    p.add_argument("--cash", type=float, default=100000.0, help="初始资金")
    p.add_argument("--commission", type=float, default=0.001, help="手续费率")
    p.add_argument("--plot", action="store_true", help="回测结束后画图")
    p.add_argument("--list", action="store_true", help="列出所有可用策略")
    # 各策略的参数（不传则用策略默认值）
    p.add_argument("--ma-period", type=int, default=None, help="ma_obv: 均线周期")
    p.add_argument("--obv-period", type=int, default=None, help="ma_obv: OBV 周期")
    p.add_argument("--volume-ratio", type=float, default=None, help="volume_breakout: 缩量阈值")
    p.add_argument("--volume-ma", type=int, default=None, help="volume_breakout: 均量周期")
    p.add_argument("--stop-loss", type=float, default=None, help="volume_breakout: 止损比例")
    p.add_argument("--take-profit", type=float, default=None, help="volume_breakout: 止盈比例")
    p.set_defaults(func=cmd_backtest)

    p = sub.add_parser("filter-guide", help="打印筛选条件说明书")
    p.add_argument("--filter", nargs="+", default=None, help="只看指定条件")
    p.add_argument("--list", action="store_true", help="只列名称与一句话说明")
    p.set_defaults(func=cmd_filter_guide)

    p = sub.add_parser("ui", help="启动桌面界面（需要 wxPython）")
    p.add_argument("symbol", nargs="?", default=None, help="可选：直接打开某只股票")
    p.set_defaults(func=cmd_ui)

    p = sub.add_parser("rebuild-ttm", help="回填 fundamental 的 TTM 列（PS 依赖）")
    p.set_defaults(func=cmd_rebuild_ttm)

    p = sub.add_parser("rebuild-valuation", help="重建估值历史分位表（PE/PB/PS 分位）")
    p.add_argument("--windows", nargs="+", type=int, default=[3, 5, 10, 0],
                   help="窗口年数，0 表示全部可得历史（默认 3 5 10 0）")
    p.add_argument("--stock", nargs="+", default=None, help="只算指定股票")
    p.add_argument("--limit", type=int, default=None, help="只算前 N 只（试跑用）")
    p.add_argument("--workers", type=int, default=4, help="并发计算线程数")
    p.set_defaults(func=cmd_rebuild_valuation)

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
