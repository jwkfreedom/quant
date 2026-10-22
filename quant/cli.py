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


def cmd_db_fill_qfq(_args: argparse.Namespace) -> int:
    """把 daily_price 里缺失的前复权列用不复权价回填。

    新浪数据源增量更新的行只有不复权价，前复权列为空；
    留空会让回测和图表算出 NaN，所以统一回填。
    """
    from quant import config
    from quant.data import store

    pairs = (("open_qfq", "open"), ("high_qfq", "high"),
             ("low_qfq", "low"), ("close_qfq", "close"))
    try:
        with store.open_db(config.DB_PATH) as conn:
            total = 0
            for qfq, raw in pairs:
                cursor = conn.execute(
                    f"UPDATE daily_price SET {qfq} = {raw} "
                    f"WHERE {qfq} IS NULL AND {raw} IS NOT NULL"
                )
                print(f"  {qfq} <- {raw}: {cursor.rowcount:,} 行")
                total += cursor.rowcount
            conn.commit()
            left = conn.execute(
                "SELECT COUNT(*) FROM daily_price WHERE close_qfq IS NULL"
            ).fetchone()[0]
    except Exception as exc:
        message = str(exc).lower()
        if "locked" in message or "busy" in message:
            print("数据库被占用（多半是「更新行情」还在跑）。")
            print("等更新完成后再执行一次：quant db-fill-qfq")
            return 1
        raise

    print(f"合计回填 {total:,} 行；剩余 close_qfq 为空 {left:,} 行（不复权价也缺，属正常）")
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
# 资产管理（portfolio-*）
# --------------------------------------------------------------------------
def _portfolio_ctx():
    """打开资产库并保证表结构存在。"""
    from contextlib import contextmanager

    from quant.portfolio import Portfolio, open_db, store

    @contextmanager
    def _ctx():
        with open_db() as conn:
            store.ensure_schema(conn)
            yield conn, Portfolio(conn)

    return _ctx()


def _print_table(frame, columns=None, limit=None, empty="（无数据）") -> None:
    """打印 DataFrame（终端友好）。"""
    if frame is None or len(frame) == 0:
        print(empty)
        return
    view = frame if columns is None else frame[[c for c in columns if c in frame.columns]]
    if limit:
        view = view.head(limit)
    print(view.to_string(index=False))


def _find_account(book, accounts, *, account_id=None, account_name=None):
    """按 id 或名称定位资金账户。"""
    from quant.portfolio import schema

    if account_id is not None:
        row = book.conn.execute(
            f"SELECT * FROM {schema.TABLE_ACCOUNT} WHERE id = ?", (account_id,)
        ).fetchone()
        if row is None:
            raise SystemExit(f"资金账户不存在: {account_id}")
        return dict(row)

    matches = [a for a in accounts if a["name"] == account_name]
    if not matches:
        raise SystemExit(f"找不到资金账户: {account_name}")
    if len(matches) > 1:
        ids = ", ".join(f"{a['id']}={a['name']}" for a in matches)
        raise SystemExit(f"有多个同名账户，请改用 --account-id：{ids}")
    return matches[0]


def _resolve_account(book, args):
    """命令行里统一用 --account 名称或 --account-id。"""
    from quant.portfolio import store

    return _find_account(book, store.list_accounts(book.conn),
                         account_id=getattr(args, "account_id", None),
                         account_name=getattr(args, "account", None))


def cmd_portfolio_init(_args: argparse.Namespace) -> int:
    """建资产库（幂等）。"""
    from quant.portfolio import init_db

    path = init_db()
    print(f"资产库就绪：{path}")
    return 0


def cmd_portfolio_owner(args: argparse.Namespace) -> int:
    from quant.portfolio import store

    with _portfolio_ctx() as (conn, book):
        if args.add:
            owner_id = book.create_owner(args.add, note=args.note or "")
            print(f"已新建资产账户：{args.add}（id={owner_id}）")
        if args.rename:
            old, _, new = args.rename.partition(":")
            target = store.find_owner(conn, old)
            if target is None:
                raise SystemExit(f"找不到资产账户: {old}")
            store.update_owner(conn, target["id"], name=new)
            print(f"已改名：{old} -> {new}")
        if args.delete:
            target = store.find_owner(conn, args.delete)
            if target is None:
                raise SystemExit(f"找不到资产账户: {args.delete}")
            store.delete_owner(conn, target["id"])
            print(f"已删除资产账户：{args.delete}（其下资金账户与流水一并删除）")

        owners = store.list_owners(conn)
        print(f"\n共 {len(owners)} 个资产账户：")
        for owner in owners:
            accounts = store.list_accounts(conn, owner["id"])
            print(f"  [{owner['id']}] {owner['name']}  —— {len(accounts)} 个资金账户")
            for account in accounts:
                print(f"      [{account['id']}] {account['name']} "
                      f"（{account['currency']}，{account['account_type']}）")
    return 0


def cmd_portfolio_account(args: argparse.Namespace) -> int:
    from quant.portfolio import schema, store

    with _portfolio_ctx() as (conn, book):
        if args.add:
            owner = store.find_owner(conn, args.owner or "")
            if owner is None:
                raise SystemExit(f"找不到资产账户: {args.owner}（先用 portfolio-owner --add 创建）")
            account_id = book.add_account(owner["id"], args.add,
                                          account_type=args.type, currency=args.currency,
                                          note=args.note or "")
            print(f"已新建资金账户：{args.add}（id={account_id}，{args.currency}）")
        if args.delete:
            account = _find_account(book, store.list_accounts(conn), account_id=args.delete)
            store.delete_account(conn, account["id"])
            print(f"已删除资金账户：{account['name']}（持仓与流水一并删除）")
        if args.rename:
            old, _, new = args.rename.partition(":")
            account = _find_account(book, store.list_accounts(conn), account_name=old)
            store.update_account(conn, account["id"], name=new)
            print(f"已改名：{old} -> {new}")

        accounts = store.list_accounts(conn)
        print(f"\n共 {len(accounts)} 个资金账户：")
        for account in accounts:
            cash = book.cash_balance(account["id"])
            owner = store.get_owner(conn, account["owner_id"])
            type_name = schema.ACCOUNT_TYPE_NAMES.get(account["account_type"], "")
            print(f"  [{account['id']}] {owner['name'] if owner else '?'} / {account['name']}"
                  f"  {account['currency']}  {type_name}  现金 {cash:,.2f}")
    return 0


def _trade_args(args) -> dict:
    return {
        "kind": args.kind,
        "market": args.market,
        "symbol": args.symbol,
        "name": args.name or "",
        "trade_date": args.date,
        "note": args.note or "",
    }


def cmd_portfolio_buy(args: argparse.Namespace) -> int:
    with _portfolio_ctx() as (_conn, book):
        account = _resolve_account(book, args)
        result = book.buy(account["id"], quantity=args.quantity, price=args.price,
                          fee=args.fee, risk=args.risk, **_trade_args(args))
        print(f"买入成功：{args.symbol} 持仓 {result['quantity']:,.2f} "
              f"成本 {result['cost_price']:,.4f}")
        print(f"现金余额：{result['cash']:,.2f}")
        for warning in result["warnings"]:
            print(f"[警告] {warning}")
    return 0


def cmd_portfolio_sell(args: argparse.Namespace) -> int:
    with _portfolio_ctx() as (_conn, book):
        account = _resolve_account(book, args)
        result = book.sell(account["id"], quantity=args.quantity, price=args.price,
                           fee=args.fee, **_trade_args(args))
        print(f"卖出成功：{args.symbol} 剩余 {result['quantity']:,.2f} "
              f"已实现盈亏 {result['realized_pnl']:,.2f}")
        print(f"现金余额：{result['cash']:,.2f}")
    return 0


def cmd_portfolio_adjust(args: argparse.Namespace) -> int:
    with _portfolio_ctx() as (_conn, book):
        account = _resolve_account(book, args)
        result = book.adjust(account["id"], quantity=args.quantity,
                             cost_price=args.cost, risk=args.risk, **_trade_args(args))
        print(f"已调整：{args.symbol} 目标数量 {result['quantity']:,.2f} "
              f"成本 {result['cost_price']:,.4f}（变动 {result['delta']:+,.2f}）")
    return 0


def cmd_portfolio_cash(args: argparse.Namespace) -> int:
    with _portfolio_ctx() as (_conn, book):
        account = _resolve_account(book, args)
        if args.deposit is not None:
            balance = book.deposit(account["id"], args.deposit, trade_date=args.date,
                                   note=args.note or "")
            print(f"已存入 {args.deposit:,.2f}，当前现金 {balance:,.2f}")
        if args.withdraw is not None:
            balance = book.withdraw(account["id"], args.withdraw, trade_date=args.date,
                                    note=args.note or "")
            print(f"已取出 {args.withdraw:,.2f}，当前现金 {balance:,.2f}")
        if args.deposit is None and args.withdraw is None:
            print(f"当前现金：{book.cash_balance(account['id']):,.2f}")
    return 0


def cmd_portfolio_position(args: argparse.Namespace) -> int:
    from quant.portfolio import prices, store

    with _portfolio_ctx() as (conn, book):
        if args.refresh:
            result = prices.refresh_prices(conn, include_funds=not args.no_funds)
            print(f"价格刷新：更新 {result['updated']} 个，跳过 {result['skipped']} 个")
            if result["failed"]:
                print("取价失败：" + "、".join(result["failed"]))

        owner_id = None
        if args.owner:
            owner = store.find_owner(conn, args.owner)
            if owner is None:
                raise SystemExit(f"找不到资产账户: {args.owner}")
            owner_id = owner["id"]
        account_id = args.account_id
        if args.account:
            account_id = _resolve_account(book, args)["id"]

        frame = book.positions(owner_id=owner_id, account_id=account_id,
                               prices=prices.price_map(conn))
        _print_table(frame, columns=["account", "symbol", "name", "kind", "risk", "quantity",
                                     "cost_price", "price", "market_value", "pnl", "pnl_pct"])

        summary = book.summary(owner_id=owner_id, account_id=account_id, frame=frame)
        print(f"\n总资产 {summary['total_value']:,.2f}  成本 {summary['total_cost']:,.2f}  "
              f"浮动盈亏 {summary['pnl']:,.2f}（{summary['pnl_pct']:+.2f}%）")
        if summary["missing_price"]:
            print(f"[提示] {summary['missing_price']} 个产品缺价格，未计入总资产")
        for warning in summary["negative_cash"]:
            print(f"[警告] {warning}")
    return 0


def cmd_portfolio_stats(args: argparse.Namespace) -> int:
    from quant.portfolio import prices, store

    with _portfolio_ctx() as (conn, book):
        owner_id = None
        if args.owner:
            owner = store.find_owner(conn, args.owner)
            if owner is None:
                raise SystemExit(f"找不到资产账户: {args.owner}")
            owner_id = owner["id"]
        account_id = args.account_id
        if args.account:
            account_id = _resolve_account(book, args)["id"]

        frame = book.positions(owner_id=owner_id, account_id=account_id,
                               prices=prices.price_map(conn))
        summary = book.summary(frame=frame)
        print(f"总资产 {summary['total_value']:,.2f}（人民币口径，{summary['as_of']}）")
        print(f"持仓成本 {summary['total_cost']:,.2f}   浮动盈亏 {summary['pnl']:,.2f} "
              f"（{summary['pnl_pct']:+.2f}%）")
        if summary["cash_by_currency"]:
            cash = "，".join(f"{k} {v:,.2f}" for k, v in summary["cash_by_currency"].items())
            print(f"现金余额：{cash}")
        if summary["by_currency"]:
            parts = "，".join(f"{k} {v['value']:,.2f}" for k, v in summary["by_currency"].items())
            print(f"分币种市值：{parts}")
        if summary["missing_price"]:
            print(f"[提示] {summary['missing_price']} 个产品缺价格，未计入总资产")
        for warning in summary["negative_cash"]:
            print(f"[警告] {warning}")

        print("\n风险占比：")
        _print_table(book.risk_breakdown(frame=frame),
                     columns=["risk_name", "value", "weight", "count", "missing"])
    return 0


def cmd_portfolio_txn(args: argparse.Namespace) -> int:
    import pandas as pd

    from quant.portfolio import store

    with _portfolio_ctx() as (conn, _book):
        txns = store.list_txns(conn, account_id=args.account_id, limit=args.limit)
        _print_table(pd.DataFrame(txns),
                     columns=["trade_date", "account_name", "symbol", "name", "action",
                              "quantity", "price", "fee", "realized_pnl", "note"])
    return 0


def cmd_portfolio_update(args: argparse.Namespace) -> int:
    from quant.portfolio import prices

    with _portfolio_ctx() as (conn, _book):
        print("刷新汇率…")
        for currency, count in prices.update_fx(conn, days=args.fx_days).items():
            print(f"  {currency}: 写入 {count} 天")
        print("刷新价格…")
        result = prices.refresh_prices(conn, include_funds=not args.no_funds)
        print(f"  更新 {result['updated']} 个，跳过 {result['skipped']} 个")
        if result["failed"]:
            print("  取价失败：" + "、".join(result["failed"]))
    return 0


def cmd_portfolio_dividend(args: argparse.Namespace) -> int:
    from quant.portfolio import dividends, store

    with _portfolio_ctx() as (conn, book):
        if args.refresh:
            result = dividends.refresh_dividends(conn, include_funds=not args.no_funds)
            print(f"分红拉取：写入/更新 {result['saved']} 条")
            if result["failed"]:
                print("未取到：" + "、".join(result["failed"]))

        if args.add:
            instrument = store.find_instrument(conn, args.kind, args.market, args.add)
            if instrument is None:
                raise SystemExit(f"还没有这个产品的持仓，先买入或调整: {args.add}")
            dividends.add_manual_dividend(
                conn, instrument["id"], ex_date=args.ex_date,
                cash_per_share=args.per_share, pay_date=args.pay_date,
                currency=instrument["currency"], note=args.note or "",
            )
            print(f"已手动登记分红：{args.add} {args.ex_date} 每股 {args.per_share}")

        if args.record:
            account = _resolve_account(book, args)
            balance = dividends.record_as_cash(conn, args.record, account["id"],
                                               trade_date=args.date)
            print(f"已记入现金，当前余额 {balance:,.2f}")

        account_id = None
        if args.account or args.account_id:
            account_id = _resolve_account(book, args)["id"]

        frame = dividends.dividend_report(conn, account_id=account_id, year=args.year)
        _print_table(frame, columns=["id", "account", "symbol", "name", "ex_date", "pay_date",
                                     "cash_per_share", "quantity", "amount", "currency",
                                     "recorded"])

        summary = dividends.dividend_summary(conn, account_id=account_id, year=args.year)
        scope = f"{args.year} 年" if args.year else "全部"
        print(f"\n{scope}分红合计 {summary['total']:,.2f}（共 {summary['count']} 笔）")
        for name, value in summary["by_account"].items():
            print(f"  {name}: {value:,.2f}")
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

    sub.add_parser(
        "db-fill-qfq",
        help="用不复权价回填缺失的前复权列（新浪源增量更新后跑一次）",
    ).set_defaults(func=cmd_db_fill_qfq)

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

    # ---- 资产管理 ----
    sub.add_parser("portfolio-init", help="建资产库（data/portfolio.db）").set_defaults(
        func=cmd_portfolio_init)

    p = sub.add_parser("portfolio-owner", help="资产账户（人）：新建 / 改名 / 删除 / 列表")
    p.add_argument("--add", metavar="NAME", help="新建资产账户")
    p.add_argument("--rename", metavar="OLD:NEW", help="改名")
    p.add_argument("--delete", metavar="NAME", help="删除（其下资金账户与流水一并删除）")
    p.add_argument("--note", default="", help="备注")
    p.set_defaults(func=cmd_portfolio_owner)

    p = sub.add_parser("portfolio-account", help="资金账户：新建 / 改名 / 删除 / 列表")
    p.add_argument("--owner", default="", help="所属资产账户（--add 时必填）")
    p.add_argument("--add", metavar="NAME", help="新建资金账户")
    p.add_argument("--rename", metavar="OLD:NEW", help="改名")
    p.add_argument("--delete", type=int, metavar="ID", help="按 id 删除")
    p.add_argument("--type", default="securities",
                   choices=["securities", "fund", "bank", "other"], help="账户类型")
    p.add_argument("--currency", default="CNY", choices=["CNY", "HKD", "USD"],
                   help="结算币种")
    p.add_argument("--note", default="", help="备注")
    p.set_defaults(func=cmd_portfolio_account)

    def add_trade_args(parser, *, need_price=True):
        parser.add_argument("--account", default=None, help="资金账户名称")
        parser.add_argument("--account-id", type=int, default=None, help="资金账户 id")
        parser.add_argument("--kind", default="stock",
                            choices=["stock", "etf", "fund"], help="产品类型")
        parser.add_argument("--market", default="CN", choices=["CN", "HK", "US"],
                            help="市场")
        parser.add_argument("--symbol", required=True, help="代码")
        parser.add_argument("--name", default="", help="名称")
        if need_price:
            parser.add_argument("--price", type=float, required=True, help="成交价")
        parser.add_argument("--date", default=None, help="日期 YYYY-MM-DD（默认今天）")
        parser.add_argument("--note", default="", help="备注")
        parser.add_argument("--risk", default=None, choices=["high", "mid", "low"],
                            help="风险等级（新建产品时用）")

    p = sub.add_parser("portfolio-buy", help="买入")
    add_trade_args(p)
    p.add_argument("--quantity", type=float, required=True, help="数量")
    p.add_argument("--fee", type=float, default=0.0, help="手续费")
    p.set_defaults(func=cmd_portfolio_buy)

    p = sub.add_parser("portfolio-sell", help="卖出")
    add_trade_args(p)
    p.add_argument("--quantity", type=float, required=True, help="数量")
    p.add_argument("--fee", type=float, default=0.0, help="手续费")
    p.set_defaults(func=cmd_portfolio_sell)

    p = sub.add_parser("portfolio-adjust", help="数量调整 / 期初导入")
    add_trade_args(p, need_price=False)
    p.add_argument("--quantity", type=float, required=True, help="目标持有数量")
    p.add_argument("--cost", type=float, default=0.0, help="成本价")
    p.set_defaults(func=cmd_portfolio_adjust)

    p = sub.add_parser("portfolio-cash", help="现金存入 / 取出 / 查询")
    p.add_argument("--account", default=None, help="资金账户名称")
    p.add_argument("--account-id", type=int, default=None, help="资金账户 id")
    p.add_argument("--deposit", type=float, default=None, help="存入金额")
    p.add_argument("--withdraw", type=float, default=None, help="取出金额")
    p.add_argument("--date", default=None, help="日期 YYYY-MM-DD")
    p.add_argument("--note", default="", help="备注")
    p.set_defaults(func=cmd_portfolio_cash)

    p = sub.add_parser("portfolio-position", help="持仓表与总资产")
    p.add_argument("--owner", default=None, help="只看某个资产账户")
    p.add_argument("--account", default=None, help="只看某个资金账户")
    p.add_argument("--account-id", type=int, default=None)
    p.add_argument("--refresh", action="store_true", help="先刷新价格")
    p.add_argument("--no-funds", dest="no_funds", action="store_true",
                   help="刷新时跳过场外基金净值")
    p.set_defaults(func=cmd_portfolio_position)

    p = sub.add_parser("portfolio-stats", help="总资产与高中低风险占比")
    p.add_argument("--owner", default=None)
    p.add_argument("--account", default=None)
    p.add_argument("--account-id", type=int, default=None)
    p.set_defaults(func=cmd_portfolio_stats)

    p = sub.add_parser("portfolio-txn", help="交易流水")
    p.add_argument("--account-id", type=int, default=None)
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_portfolio_txn)

    p = sub.add_parser("portfolio-update", help="刷新汇率与持仓价格")
    p.add_argument("--no-funds", dest="no_funds", action="store_true",
                   help="跳过场外基金净值")
    p.add_argument("--fx-days", type=int, default=30, help="汇率回看天数")
    p.set_defaults(func=cmd_portfolio_update)

    p = sub.add_parser("portfolio-dividend", help="分红：拉取 / 查看 / 手动登记 / 记入现金")
    p.add_argument("--refresh", action="store_true", help="自动拉取分红")
    p.add_argument("--no-funds", dest="no_funds", action="store_true", help="跳过基金分红")
    p.add_argument("--year", type=int, default=None, help="只看某年（按除息日）")
    p.add_argument("--account", default=None, help="只看某个资金账户")
    p.add_argument("--account-id", type=int, default=None)
    p.add_argument("--add", metavar="SYMBOL", help="手动登记分红：产品代码")
    p.add_argument("--kind", default="stock", choices=["stock", "etf", "fund"])
    p.add_argument("--market", default="CN", choices=["CN", "HK", "US"])
    p.add_argument("--ex-date", dest="ex_date", default=None, help="除息日")
    p.add_argument("--pay-date", dest="pay_date", default=None, help="派息日")
    p.add_argument("--per-share", dest="per_share", type=float, default=0.0,
                   help="每股分红")
    p.add_argument("--record", type=int, metavar="DIVIDEND_ID", default=None,
                   help="把这笔分红记入现金")
    p.add_argument("--date", default=None, help="入账日期")
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_portfolio_dividend)

    return parser


def _relax_console_encoding() -> None:
    """让控制台输出不至于因为个别字符而崩掉。

    pandas 在 to_string 对齐时会插入私有区填充字符（\ue000 段），
    Windows 默认的 GBK 代码页编不了它们，会直接抛 UnicodeEncodeError。
    这里改成「编不了就替换」，保证表格总能打印出来。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover - 非文本流
            pass


def main(argv: list[str] | None = None) -> int:
    """CLI 主函数，返回进程退出码。"""
    _relax_console_encoding()
    config.setup_logging(logging.INFO)
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
