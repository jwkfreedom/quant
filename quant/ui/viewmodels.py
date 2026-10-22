"""UI 视图模型：所有取数、过滤、导出逻辑都放在这里。

**不导入任何 GUI 库** —— 这样可以在无显示环境下用 pytest 完整验证；
GUI 层（`quant/ui/screens/`）只负责把这里的结果画出来。
"""

from __future__ import annotations

import datetime
import json
import logging
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from quant import config, query
from quant.data import schema, store

logger = logging.getLogger(__name__)

#: 数据浏览器允许访问的表（白名单）
EXPLORER_TABLES: tuple[str, ...] = (
    schema.TABLE_DAILY_PRICE,
    schema.TABLE_ETF_DAILY,
    schema.TABLE_FUNDAMENTAL,
    schema.TABLE_FUNDAMENTAL_GROWTH,
    schema.TABLE_FINANCIAL,
    schema.TABLE_STOCK_LIST,
    schema.TABLE_VALUATION_PERCENTILE,
    schema.TABLE_TRADE_RECORD,
)

#: 「新鲜度」判断阈值（天）
STALE_DAYS = 7

#: 基本面允许的滞后天数（季度披露有天然延迟）
FUNDAMENTAL_STALE_DAYS = 150


# --------------------------------------------------------------------------
# P1 数据总览
# --------------------------------------------------------------------------
@dataclass
class DataStatus:
    """数据总览页需要的一切。"""

    counts: dict[str, int] = field(default_factory=dict)
    price_latest: str | None = None
    price_start: str | None = None
    price_symbols: int = 0
    fundamental_latest: int | None = None
    fundamental_seasons: int = 0
    financial_latest: str | None = None
    financial_symbols: int = 0
    valuation_latest: str | None = None
    valuation_symbols: int = 0
    db_size_mb: float = 0.0
    archive_size_mb: float = 0.0
    stale: dict[str, str] = field(default_factory=dict)

    def report(self) -> list[tuple[str, str, bool]]:
        """返回 (项目, 值, 是否陈旧) 列表，供界面渲染。"""
        return [
            ("行情日线", f"{self.price_latest}（{self.price_symbols:,} 只）", "price" in self.stale),
            ("季度基本面", f"{self.fundamental_latest}（{self.fundamental_seasons} 个季度）",
             "fundamental" in self.stale),
            ("财务指标", f"{self.financial_latest}（{self.financial_symbols:,} 只）",
             "financial" in self.stale),
            ("估值分位", f"{self.valuation_latest}（{self.valuation_symbols:,} 只）",
             "valuation" in self.stale),
        ]


def _days_since(text) -> int | None:
    if not text:
        return None
    try:
        day = datetime.date.fromisoformat(str(text)[:10])
    except ValueError:
        return None
    return (datetime.date.today() - day).days


def data_status(conn: sqlite3.Connection | None = None) -> DataStatus:
    """汇总数据新鲜度与体量。"""
    own = conn is None
    if own:
        conn = store.connect()

    try:
        status = DataStatus(counts=store.stats(conn))

        row = conn.execute(
            f"SELECT MIN(date), MAX(date), COUNT(DISTINCT symbol) FROM {schema.TABLE_DAILY_PRICE}"
        ).fetchone()
        status.price_start, status.price_latest = row[0], row[1]
        status.price_symbols = row[2] or 0

        row = conn.execute(
            f"SELECT MAX(season), COUNT(DISTINCT season) FROM {schema.TABLE_FUNDAMENTAL}"
        ).fetchone()
        status.fundamental_latest, status.fundamental_seasons = row[0], row[1] or 0

        row = conn.execute(
            f"SELECT MAX(report_date), COUNT(DISTINCT symbol) FROM {schema.TABLE_FINANCIAL}"
        ).fetchone()
        status.financial_latest, status.financial_symbols = row[0], row[1] or 0

        if store.table_exists(conn, schema.TABLE_VALUATION_PERCENTILE):
            row = conn.execute(
                f"SELECT MAX(as_of), COUNT(DISTINCT symbol) FROM {schema.TABLE_VALUATION_PERCENTILE}"
            ).fetchone()
            status.valuation_latest, status.valuation_symbols = row[0], row[1] or 0
    finally:
        if own:
            conn.close()

    if config.DB_PATH.is_file():
        status.db_size_mb = config.DB_PATH.stat().st_size / 1048576
    if config.ORIGINAL_DIR.is_dir():
        status.archive_size_mb = sum(
            p.stat().st_size for p in config.ORIGINAL_DIR.rglob("*") if p.is_file()
        ) / 1048576

    # 行情与估值分位是每日数据，超过一周就算陈旧
    for key, value in (("price", status.price_latest), ("valuation", status.valuation_latest)):
        days = _days_since(value)
        if days is None or days > STALE_DAYS:
            status.stale[key] = "无数据" if days is None else f"{days} 天前"

    # 财务指标与季度基本面本身是季度数据，用季度口径判断
    for key, value in (("financial", status.financial_latest),
                       ("fundamental", status.fundamental_latest)):
        text = str(value) if value else ""
        days = _days_since(f"{text[:4]}-{text[4:6]}-{text[6:8]}") if len(text) >= 8 else None
        if days is None or days > FUNDAMENTAL_STALE_DAYS:
            status.stale[key] = "无数据" if days is None else f"{days} 天前"

    return status


# --------------------------------------------------------------------------
# P5 数据浏览器
# --------------------------------------------------------------------------
def _validate_table(table: str) -> str:
    if table not in EXPLORER_TABLES:
        raise ValueError(f"不支持的表: {table}；可选 {list(EXPLORER_TABLES)}")
    return table


def table_columns(conn: sqlite3.Connection, table: str) -> list[tuple[str, str]]:
    """返回表的 (列名, 中文展示名) 列表。"""
    table = _validate_table(table)
    columns = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
    return [(name, schema.display_name(name)) for name in columns]


def query_table(
    table: str,
    *,
    symbols: list[str] | None = None,
    date_start: str | None = None,
    date_end: str | None = None,
    extra_conditions: list[tuple[str, str, str]] | None = None,
    page: int = 1,
    page_size: int = 200,
    order_desc: bool = True,
    conn: sqlite3.Connection | None = None,
) -> tuple[pd.DataFrame, int]:
    """分页查询白名单表，返回 (当前页数据, 总行数)。

    参数 extra_conditions 形如 `[("roe", ">", "10")]`；列名会被校验、值以参数绑定。
    """
    table = _validate_table(table)
    own = conn is None
    if own:
        conn = store.connect()

    try:
        columns = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
        where: list[str] = []
        params: list = []

        codes = [str(s).zfill(6) for s in (symbols or []) if str(s).strip()]
        if codes and "symbol" in columns:
            where.append(f"symbol IN ({', '.join('?' for _ in codes)})")
            params.extend(codes)

        if date_start and "date" in columns:
            where.append("date >= ?")
            params.append(str(date_start))
        if date_end and "date" in columns:
            where.append("date <= ?")
            params.append(str(date_end))

        for column, operator, value in (extra_conditions or []):
            if column not in columns:
                raise ValueError(f"{table} 没有列 {column}")
            if operator not in (">", ">=", "<", "<=", "=", "!=", "like"):
                raise ValueError(f"不支持的运算符: {operator}")
            if operator == "like":
                where.append(f"{column} LIKE ?")
                params.append(f"%{value}%")
            else:
                where.append(f"{column} {operator} ?")
                params.append(value)

        clause = f" WHERE {' AND '.join(where)}" if where else ""
        total = int(conn.execute(f"SELECT COUNT(*) FROM {table}{clause}", params).fetchone()[0])

        order_column = "date" if "date" in columns else ("symbol" if "symbol" in columns else columns[0])
        direction = "DESC" if order_desc else "ASC"
        offset = max(0, (page - 1) * page_size)
        sql = (f"SELECT * FROM {table}{clause} "
               f"ORDER BY {order_column} {direction} LIMIT ? OFFSET ?")
        df = pd.read_sql_query(sql, conn, params=[*params, page_size, offset])
        return df, total
    finally:
        if own:
            conn.close()


def export_frame(df: pd.DataFrame, path: str | Path, *, display_names: bool = False) -> Path:
    """导出 DataFrame 到 CSV / Excel（按扩展名判断）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = schema.rename_for_display(df) if display_names else df

    if path.suffix.lower() in (".xlsx", ".xls"):
        data.to_excel(path, index=False)
    else:
        data.to_csv(path, index=False, encoding="utf_8_sig")
    logger.info("已导出 %s（%d 行）", path, len(data))
    return path


# --------------------------------------------------------------------------
# P2 选股筛选
# --------------------------------------------------------------------------
@dataclass
class ScreenSummary:
    """筛选结果的轻量摘要（供界面表格/状态栏）。"""

    as_of: int | None
    steps: list[tuple[str, int, int]]
    frame: pd.DataFrame

    @property
    def count(self) -> int:
        return len(self.frame)

    def step_text(self) -> str:
        if not self.steps:
            return ""
        parts = [f"初始 {self.steps[0][1]}"]
        for name, _before, after in self.steps:
            parts.append(f"{name} {after}")
        return " → ".join(parts)


def run_screen(
    specs: list[str],
    *,
    as_of: int | None = None,
    columns: list[str] | None = None,
    limit: int | None = None,
    conn: sqlite3.Connection | None = None,
) -> ScreenSummary:
    """执行过滤链，返回结果表与过滤过程。"""
    from quant.filter import FilterChain, FilterContext

    with FilterContext(as_of=as_of, conn=conn) as ctx:
        if ctx.as_of is None:
            latest = query.latest_trading_date(ctx.conn)
            ctx.as_of = int(latest.replace("-", "")) if latest else None
        result = FilterChain.from_specs(specs).run(ctx)

    frame = result.frame
    if columns:
        keep = [c for c in columns if c in frame.columns]
        if keep:
            frame = frame.loc[:, keep]
    if limit:
        frame = frame.head(limit)
    return ScreenSummary(as_of=result.as_of, steps=result.steps, frame=frame.reset_index(drop=True))


# --------------------------------------------------------------------------
# 筛选方案
# --------------------------------------------------------------------------
_NAME_PATTERN = re.compile(r"^[\w\u4e00-\u9fff\- ]{1,40}$")


def screens_dir() -> Path:
    config.SCREENS_DIR.mkdir(parents=True, exist_ok=True)
    return config.SCREENS_DIR


def list_screens() -> list[str]:
    """列出已保存的方案名。"""
    return sorted(p.stem for p in screens_dir().glob("*.json"))


def save_screen(name: str, specs: list[str], *, note: str = "") -> Path:
    """保存筛选方案。"""
    if not _NAME_PATTERN.match(name):
        raise ValueError("方案名只能是中英文、数字、下划线、短横线或空格，长度 1~40")
    path = screens_dir() / f"{name}.json"
    payload = {
        "name": name,
        "note": note,
        "specs": list(specs),
        "saved_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_screen(name: str) -> dict:
    """读取筛选方案。"""
    path = screens_dir() / f"{name}.json"
    if not path.is_file():
        raise FileNotFoundError(f"方案不存在: {name}")
    return json.loads(path.read_text(encoding="utf-8"))


def delete_screen(name: str) -> bool:
    path = screens_dir() / f"{name}.json"
    if path.is_file():
        path.unlink()
        return True
    return False


# --------------------------------------------------------------------------
# P3 个股分析
# --------------------------------------------------------------------------
@dataclass
class StockDetail:
    """个股页需要的数据包。"""

    symbol: str
    name: str = ""
    metrics: dict = field(default_factory=dict)
    price: pd.DataFrame = field(default_factory=pd.DataFrame)
    full_price: pd.DataFrame = field(default_factory=pd.DataFrame)
    financial: pd.DataFrame = field(default_factory=pd.DataFrame)
    fundamental: pd.DataFrame = field(default_factory=pd.DataFrame)
    growth: pd.DataFrame = field(default_factory=pd.DataFrame)
    percentiles: pd.DataFrame = field(default_factory=pd.DataFrame)
    valuation: pd.DataFrame = field(default_factory=pd.DataFrame)


def _num(value):
    """把 numpy / pandas 标量转成 Python 数字，NaN -> None。"""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def stock_detail(symbol: str, *, conn: sqlite3.Connection | None = None) -> StockDetail:
    """汇总一只股票的全部展示数据。"""
    from quant.foundation.valuation import compute_symbol_valuation
    from quant.price.loader import get_full_price

    symbol = str(symbol).zfill(6)
    own = conn is None
    if own:
        conn = store.connect()

    try:
        detail = StockDetail(symbol=symbol)

        names = query.stock_names([symbol], conn=conn)
        if not names.empty:
            detail.name = str(names.iloc[0]["name"] or "")

        detail.price = query.prices(symbol, conn=conn)
        detail.financial = store.read_financial(conn, symbol)
        detail.fundamental = store.read_fundamental(conn, symbols=[symbol])
        detail.growth = query.growth(symbols=[symbol], conn=conn)
        detail.percentiles = store.read_valuation_percentile(conn, symbols=[symbol])
        detail.valuation = compute_symbol_valuation(symbol, conn)

        try:
            detail.full_price = get_full_price(symbol, conn=conn)
        except FileNotFoundError:
            detail.full_price = pd.DataFrame()

        snapshot = query.snapshot(conn=conn)
        row = snapshot[snapshot["symbol"] == symbol]
        if not row.empty:
            record = row.iloc[0]
            detail.metrics = {
                "close": _num(record.get("close_org")),
                "pct_change": _num(record.get("pct_change")),
                "market_cap": _num(record.get("market_cap")),
                "pe": _num(record.get("pe")),
                "pb": _num(record.get("pb")),
                "ps": _num(record.get("ps")),
                "pe_pct_10y": _num(record.get("pe_pct_10y")),
                "pb_pct_10y": _num(record.get("pb_pct_10y")),
                "ps_pct_10y": _num(record.get("ps_pct_10y")),
                "roe": _num(record.get("roe")),
                "debt_ratio": _num(record.get("debt_ratio")),
                "gross_margin": _num(record.get("gross_margin")),
                "season_income_growth": _num(record.get("season_income_growth")),
                "season_profit_growth": _num(record.get("season_profit_growth")),
                "total_revenue": _num(record.get("total_revenue")),
                "report_date": record.get("report_date"),
                "season": record.get("season"),
            }
        return detail
    finally:
        if own:
            conn.close()


def stock_list(conn: sqlite3.Connection | None = None, keyword: str = "") -> pd.DataFrame:
    """股票列表（可按代码/名称模糊搜索）。"""
    own = conn is None
    if own:
        conn = store.connect()
    try:
        sql = f"SELECT symbol, name FROM {schema.TABLE_STOCK_LIST}"
        params: list = []
        if keyword:
            sql += " WHERE symbol LIKE ? OR name LIKE ?"
            params = [f"%{keyword}%", f"%{keyword}%"]
        sql += " ORDER BY symbol"
        return pd.read_sql_query(sql, conn, params=params)
    finally:
        if own:
            conn.close()


# --------------------------------------------------------------------------
# P4 回测
# --------------------------------------------------------------------------
def run_backtest(name: str, symbol: str | None = None, **kwargs):
    """转发到 `quant.strategy.run_backtest`（UI 层不直接依赖策略模块）。"""
    from quant.strategy import run_backtest as _run

    return _run(name, symbol=symbol, **kwargs)


def list_backtest_strategies():
    """返回策略元信息列表（供界面生成参数表单）。"""
    from quant.strategy import list_strategies

    return list_strategies()


def sweep_values(start: float, stop: float, step: float) -> list:
    """生成扫描用的参数序列（整数参数自动取整）。"""
    if step <= 0:
        raise ValueError("步长必须大于 0")
    if stop < start:
        raise ValueError("结束值不能小于起始值")

    values: list = []
    current = start
    is_int = float(start).is_integer() and float(stop).is_integer() and float(step).is_integer()
    guard = 0
    while current <= stop + 1e-9 and guard < 500:
        values.append(int(round(current)) if is_int else round(float(current), 6))
        current += step
        guard += 1
    if not values:
        raise ValueError("没有生成任何参数值")
    return values


def sweep_backtest(
    name: str,
    symbol: str,
    param: str,
    values,
    *,
    progress=None,
    **kwargs,
) -> pd.DataFrame:
    """对单个策略参数做网格扫描，每个取值跑一次回测。

    进度回调 progress(done, total, value) 会被逐次调用（供界面显示）。
    """
    rows = []
    total = len(values)
    for index, value in enumerate(values, 1):
        try:
            result = run_backtest(name, symbol=symbol, **{param: value}, **kwargs)
            row = {param: value, **result.metrics()}
        except Exception as exc:  # 单个取值失败不应中断整轮扫描
            row = {param: value, "return_pct": None, "annual_return": None, "sharpe": None,
                   "max_drawdown_pct": None, "trades": None, "win_rate": None,
                   "error": f"{type(exc).__name__}: {exc}"[:60]}
        rows.append(row)
        if progress is not None:
            progress(index, total, value)

    frame = pd.DataFrame(rows)
    # 去掉与参数无关的列，避免界面表格太宽
    for column in ("strategy", "symbol"):
        if column in frame.columns:
            frame = frame.drop(columns=column)
    return frame


def available_updates() -> list[dict]:
    """P1 页面上可触发的更新动作（命令 + 说明 + 是否耗时）。"""
    return [
        {"key": "price", "label": "更新行情", "command": "quant update-price --workers 4",
         "slow": True, "desc": "增量拉取最新日线（约 1 分钟/百只）"},
        {"key": "jibenmian", "label": "更新基本面",
         "command": "quant update-jibenmian --from-year {} --to-year {}",
         "slow": True, "desc": "补齐缺失季度并摄入数据库"},
        {"key": "financial", "label": "更新财务指标",
         "command": "quant update-financial --stale-days 180 --workers 4",
         "slow": True, "desc": "逐股拉取财务指标（较慢）"},
        {"key": "valuation", "label": "重建估值分位",
         "command": "quant rebuild-valuation --workers 4",
         "slow": True, "desc": "重算 PE/PB/PS 历史分位"},
    ]

# --------------------------------------------------------------------------
# 资产管理（portfolio）
# --------------------------------------------------------------------------
@contextmanager
def _portfolio_db():
    """打开资产库并保证表结构存在。"""
    from quant.portfolio import Portfolio, open_db as portfolio_open_db
    from quant.portfolio import store as portfolio_store

    with portfolio_open_db() as conn:
        portfolio_store.ensure_schema(conn)
        yield conn, Portfolio(conn)


def portfolio_display(frame: pd.DataFrame) -> pd.DataFrame:
    """把资产相关英文字段名换成中文（只在展示层做）。"""
    from quant.portfolio import schema as pschema

    if frame is None or frame.empty:
        return frame
    used: set[str] = set()
    mapping: dict[str, str] = {}
    for column in frame.columns:
        label = pschema.DISPLAY_NAMES.get(column, column)
        if label in used:          # 多个英文字段映射到同一个中文名时，退回英文避免重列
            label = column
        used.add(label)
        mapping[column] = label
    return frame.rename(columns=mapping)


def portfolio_owners() -> list[dict]:
    """资产账户 + 其下的资金账户（两级）。"""
    from quant.portfolio import store as portfolio_store

    with _portfolio_db() as (conn, book):
        owners = []
        for owner in portfolio_store.list_owners(conn):
            accounts = [
                {**account, "cash": book.cash_balance(account["id"])}
                for account in portfolio_store.list_accounts(conn, owner["id"])
            ]
            owners.append({**owner, "accounts": accounts})
        return owners


def portfolio_accounts() -> list[dict]:
    """扁平的资金账户列表（带资产账户名），供下拉框使用。"""
    result = []
    for owner in portfolio_owners():
        for account in owner["accounts"]:
            result.append({
                "id": account["id"],
                "label": f"{owner['name']} / {account['name']}",
                "owner": owner["name"],
                "name": account["name"],
                "currency": account["currency"],
                "account_type": account["account_type"],
                "cash": account["cash"],
            })
    return result


def portfolio_positions(owner_id: int | None = None,
                        account_id: int | None = None) -> pd.DataFrame:
    """持仓估值表（价格取资产库里保存的最近价）。"""
    from quant.portfolio import prices as portfolio_prices

    with _portfolio_db() as (conn, book):
        return book.positions(owner_id=owner_id, account_id=account_id,
                              prices=portfolio_prices.price_map(conn))


def portfolio_summary(owner_id: int | None = None,
                      account_id: int | None = None) -> dict:
    with _portfolio_db() as (conn, book):
        return book.summary(owner_id=owner_id, account_id=account_id)


def portfolio_risk(owner_id: int | None = None,
                   account_id: int | None = None) -> pd.DataFrame:
    with _portfolio_db() as (conn, book):
        return book.risk_breakdown(owner_id=owner_id, account_id=account_id)


def portfolio_cash(account_id: int) -> float:
    with _portfolio_db() as (_conn, book):
        return book.cash_balance(account_id)


def portfolio_txns(account_id: int | None = None, limit: int = 1000) -> pd.DataFrame:
    from quant.portfolio import store as portfolio_store

    with _portfolio_db() as (conn, _book):
        rows = portfolio_store.list_txns(conn, account_id=account_id, limit=limit)
    return pd.DataFrame(rows)


def portfolio_dividends(account_id: int | None = None,
                        year: int | None = None) -> tuple[pd.DataFrame, dict]:
    """分红明细 + 汇总。"""
    from quant.portfolio import dividends as portfolio_dividends_module

    with _portfolio_db() as (conn, _book):
        frame = portfolio_dividends_module.dividend_report(
            conn, account_id=account_id, year=year)
        summary = portfolio_dividends_module.dividend_summary(
            conn, account_id=account_id, year=year)
    return frame, summary


def portfolio_years() -> list[int]:
    """分红里出现过的年份，倒序。"""
    from quant.portfolio import store as portfolio_store

    with _portfolio_db() as (conn, _book):
        rows = portfolio_store.list_dividends(conn)
    years = {int(str(row["ex_date"])[:4]) for row in rows
             if row["ex_date"] and str(row["ex_date"])[:4].isdigit()}
    return sorted(years, reverse=True)[:15]


def portfolio_refresh(*, include_funds: bool = True, with_fx: bool = True) -> dict:
    """刷新汇率 + 持仓价格。"""
    from quant.portfolio import prices as portfolio_prices

    with _portfolio_db() as (conn, _book):
        result = portfolio_prices.refresh_prices(conn, include_funds=include_funds)
        if with_fx:
            result["fx"] = portfolio_prices.update_fx(conn)
        return result


def portfolio_refresh_dividends(*, include_funds: bool = True) -> dict:
    from quant.portfolio import dividends as portfolio_dividends_module

    with _portfolio_db() as (conn, _book):
        return portfolio_dividends_module.refresh_dividends(conn, include_funds=include_funds)


def portfolio_buy(account_id: int, *, kind: str, market: str, symbol: str,
                  quantity: float, price: float, name: str = "", fee: float = 0.0,
                  trade_date: str | None = None, note: str = "") -> dict:
    with _portfolio_db() as (_conn, book):
        return book.buy(account_id, kind=kind, market=market, symbol=symbol,
                        quantity=quantity, price=price, name=name, fee=fee,
                        trade_date=trade_date, note=note)


def portfolio_sell(account_id: int, *, kind: str, market: str, symbol: str,
                   quantity: float, price: float, name: str = "", fee: float = 0.0,
                   trade_date: str | None = None, note: str = "") -> dict:
    with _portfolio_db() as (_conn, book):
        return book.sell(account_id, kind=kind, market=market, symbol=symbol,
                         quantity=quantity, price=price, name=name, fee=fee,
                         trade_date=trade_date, note=note)


def portfolio_adjust(account_id: int, *, kind: str, market: str, symbol: str,
                     quantity: float, cost_price: float = 0.0, name: str = "",
                     trade_date: str | None = None, note: str = "") -> dict:
    with _portfolio_db() as (_conn, book):
        return book.adjust(account_id, kind=kind, market=market, symbol=symbol,
                           quantity=quantity, cost_price=cost_price, name=name,
                           trade_date=trade_date, note=note)


def portfolio_cash_move(account_id: int, amount: float, *, deposit: bool,
                        trade_date: str | None = None, note: str = "") -> float:
    with _portfolio_db() as (_conn, book):
        if deposit:
            return book.deposit(account_id, amount, trade_date=trade_date, note=note)
        return book.withdraw(account_id, amount, trade_date=trade_date, note=note)


def portfolio_record_dividend(dividend_id: int, account_id: int,
                              trade_date: str | None = None) -> float:
    from quant.portfolio import dividends as portfolio_dividends_module

    with _portfolio_db() as (conn, _book):
        return portfolio_dividends_module.record_as_cash(conn, dividend_id, account_id,
                                                         trade_date=trade_date)


def portfolio_add_account(owner_id: int, name: str, *,
                          account_type: str = "securities",
                          currency: str = "CNY") -> int:
    with _portfolio_db() as (_conn, book):
        return book.add_account(owner_id, name, account_type=account_type,
                                currency=currency)


def portfolio_add_owner(name: str) -> int:
    with _portfolio_db() as (_conn, book):
        return book.create_owner(name)


def portfolio_delete_account(account_id: int) -> None:
    from quant.portfolio import store as portfolio_store

    with _portfolio_db() as (conn, _book):
        portfolio_store.delete_account(conn, account_id)


def portfolio_set_risk(kind: str, market: str, symbol: str, risk: str) -> None:
    """改某个产品的风险等级。"""
    from quant.portfolio import store as portfolio_store

    with _portfolio_db() as (conn, _book):
        instrument = portfolio_store.find_instrument(conn, kind, market, symbol)
        if instrument is None:
            raise ValueError(f"产品不存在: {symbol}")
        portfolio_store.update_instrument(conn, instrument["id"], risk=risk)
