"""筛选条件说明书（界面「说明」按钮弹出的内容）。

为什么单独放一个模块
--------------------
过滤器的**行为**写在 `builtin.py`，这里只放**给人看的散文**（每个参数的含义、取值范围、例子）。
两者的一致性由 `tests/test_filter_guide.py` 保证：它会用反射核对
「文档里写的参数」与「`__init__` 实际参数」完全一致，缺一个就测试失败。
"""

from __future__ import annotations

import inspect

from quant.filter import base

SNAPSHOT_DOC = """【快照日期（as_of）】

筛选是「某一天的全市场横截面」，这一天的数据叫快照。

· 留空 = 用数据库里最新的交易日。
· 填 YYYYMMDD（例如 20231229）= 用**该日期当天或之前**的最后一个交易日。

具体取数规则：
  1. 行情：每只股票取「不晚于快照日」的最后一条日线。
     所以长期停牌或已退市的股票会用它自己的最后一个交易日，不会被丢掉。
  2. 基本面（营收/利润/资产负债）：取报告期 <= 快照日的最近一个季度。
  3. 财务指标（ROE/毛利率/EPS_TTM 等）：取报告期 <= 快照日的最近一期。
  4. 估值分位：`valuation_percentile` 表是按「最新交易日」算的，
     指定历史快照日时，分位仍是最近一次 `rebuild-valuation` 的结果。

⚠️ 注意：季度数据按「报告期」而不是「实际公告日」判断，
   所以年初几天的快照可能已经用到尚未公告的年报（与项目原有口径一致）。

例子：
  快照 20231229 → 2023 年最后一个交易日，用的是 2023 三季报及之前的财务数据
  快照留空     → 数据库里最新的一天（看「数据总览」页的行情日线日期）
"""

MECHANICS_DOC = """【过滤链是怎么工作的】

1. 从全市场快照出发（一行一只股票）。
2. 按**从上到下**的顺序执行每个勾选的条件，每一步只保留满足条件的股票。
3. 某一步之后剩 0 只就提前结束；界面上会显示每一步剩余多少只。
4. 多个条件之间是**「与」**的关系（同时满足）。要表达「或」，请分两次筛选再看结果。

关于缺失值：
  · 所有条件在判断前都会剔除该字段为空（NaN）的股票。
    例如勾了「PE 0~30」，PE 为空的股票会在这步被滤掉。
  · 所以「想保留缺数据的股票」就不要勾那条条件。

命令行等价写法（界面上的条件都能一一对应）：
  quant screen --filter exclude_st --filter market_cap:max=80 --filter growth:min=30

界面右侧的「复制命令行」按钮会直接生成当前条件的命令。
"""


#: 每个过滤器的详细说明：intro 一句话，params 逐参数，examples 用法示例，caveats 注意事项
FILTER_GUIDE: dict[str, dict] = {
    "exclude_st": {
        "intro": "按名称关键字剔除股票，默认剔除 ST / 退市类。这是最常用的基础条件。",
        "params": {
            "keywords": "要剔除的关键字，多个用英文逗号分隔；不区分大小写。"
                        "默认 \"ST,退\"（同时匹配 ST 与「退」）。",
        },
        "examples": [
            "exclude_st  　→ 剔除名称含 ST 或「退」的股票（默认）",
            "exclude_st:keywords=ST  　→ 只剔除 ST，保留退市整理期股票",
        ],
    },
    "min_listing": {
        "intro": "要求上市时间足够长，用来剔除次新股。",
        "params": {
            "bars": "自上市以来（截至快照日）至少要有的 K 线根数。"
                    "A 股一年约 244 个交易日，所以 250 ≈ 上市满一年、500 ≈ 满两年。",
        },
        "examples": [
            "min_listing:bars=250  　→ 上市满一年以上",
            "min_listing:bars=60  　→ 上市满一个季度（宽松）",
        ],
        "caveats": "长期停牌的股票 K 线根数少，可能被误剔除。",
    },

    # ---------------- 估值 ----------------
    "market_cap": {
        "intro": "按总市值筛选。市值 = 不复权收盘价 × 总股本。",
        "params": {
            "min": "市值下限，单位**亿元**，可留空表示不限。",
            "max": "市值上限，单位**亿元**，可留空表示不限。",
        },
        "examples": [
            "market_cap:max=80  　→ 市值小于 80 亿（小盘股）",
            "market_cap:min=100,max=500  　→ 市值 100~500 亿（中盘）",
        ],
        "caveats": "股本 = 净利润(TTM) ÷ 每股收益(TTM)，用最近报告期的值；"
                   "新股或报表缺失的股票市值为空，会被剔除。",
    },
    "pe": {
        "intro": "按市盈率（TTM，滚动四季度）筛选。",
        "params": {
            "min": "PE 下限。写 0（或留空）可排除亏损股。",
            "max": "PE 上限。",
        },
        "examples": [
            "pe:min=0,max=20  　→ PE 在 0~20 之间（0 表示自动排除亏损）",
            "pe:max=15  　→ PE 小于 15",
        ],
        "caveats": "PE = 不复权收盘价 ÷ 每股收益(TTM)。亏损公司 PE 为负，"
                   "所以想排除亏损必须写 min=0。",
    },
    "pb": {
        "intro": "按市净率（TTM）筛选。",
        "params": {"min": "PB 下限。", "max": "PB 上限。"},
        "examples": ["pb:max=2  　→ PB 小于 2（破净或低估值）", "pb:min=0,max=1  　→ 破净股"],
        "caveats": "PB = 不复权收盘价 ÷ 每股净资产(TTM)，净资产为负的股票 PB 为负。",
    },
    "ps": {
        "intro": "按市销率（TTM）筛选。适合还没盈利、看收入规模的成长股。",
        "params": {"min": "PS 下限。", "max": "PS 上限。"},
        "examples": ["ps:max=3  　→ 市销率小于 3", "ps:min=0,max=1  　→ 收入远大于市值"],
        "caveats": "PS = 总市值 ÷ 营业总收入(TTM)。需要 fundamental 表已更新到最新季度。",
    },
    "pe_percentile": {
        "intro": "按 **PE 的历史分位**筛选 —— 回答「现在的估值在历史上算贵还是便宜」。",
        "params": {
            "window_years": "回看窗口，单位年，可选 3 / 5 / 10 / 0（0 = 全部可得历史）。默认 10。",
            "min": "分位下限（%）。",
            "max": "分位上限（%）。",
        },
        "examples": [
            "pe_percentile:window_years=10,max=10  　→ PE 处于近 10 年最低的 10%"
            "（即 10 年里至少 90% 的交易日比现在贵）",
            "pe_percentile:window_years=5,max=20  　→ 近 5 年 PE 最低 20%",
            "pe_percentile:window_years=0,min=80  　→ 处于历史高位（可用来反向排查）",
        ],
        "caveats": "分位 = 窗口内「PE 低于当前」的交易日占比。"
                   "计算时**剔除 PE ≤ 0 的交易日**（亏损期），否则负数会污染分位。"
                   "历史不足窗口长度时用全部可得历史（样本数见「个股分析 → 分位」）。",
    },
    "pb_percentile": {
        "intro": "按 **PB 的历史分位**筛选，口径与 PE 分位相同。",
        "params": {
            "window_years": "目前只提供 10 年（快照里只有 pb_pct_10y 列）。",
            "min": "分位下限（%）。",
            "max": "分位上限（%）。",
        },
        "examples": ["pb_percentile:max=20  　→ PB 处于近 10 年最低 20%"],
        "caveats": "净资产为负的交易日同样被剔除。",
    },
    "ps_percentile": {
        "intro": "按 **PS 的历史分位**筛选，口径与 PE 分位相同。",
        "params": {
            "window_years": "目前只提供 10 年。",
            "min": "分位下限（%）。",
            "max": "分位上限（%）。",
        },
        "examples": ["ps_percentile:max=20  　→ PS 处于近 10 年最低 20%"],
        "caveats": "需要营业总收入(TTM) 有值（依赖 fundamental 表的新鲜度）。",
    },

    # ---------------- 财务 ----------------
    "roe": {
        "intro": "按净资产收益率筛选，衡量赚钱效率。",
        "params": {"min": "ROE 下限，单位 %。"},
        "examples": ["roe:min=15  　→ ROE 高于 15%（优质盈利）", "roe:min=0  　→ 只要不亏损"],
        "caveats": "取自最近一期财报，是**累计值**（一季报即一季度 ROE）。",
    },
    "debt_ratio": {
        "intro": "按资产负债率筛选，衡量财务杠杆。",
        "params": {"max": "资产负债率上限，单位 %。"},
        "examples": ["debt_ratio:max=50  　→ 资产负债率低于 50%（负债较轻）"],
        "caveats": "银行、地产等行业的负债率天然很高，单独用这条会误伤，建议配合市值一起用。",
    },
    "gross_margin": {
        "intro": "按销售毛利率筛选，反映产品竞争力。",
        "params": {"min": "毛利率下限（%）。", "max": "毛利率上限（%）。"},
        "examples": ["gross_margin:min=40  　→ 毛利率高于 40%"],
        "caveats": "该字段在部分报告期缺失（约一半），缺失的股票会被剔除。",
    },
    "growth": {
        "intro": "按**单季**增长筛选（不是累计同比，已换算成单季口径）。",
        "params": {
            "field": "看哪个指标：season_income_growth = 单季营收同比，"
                     "season_profit_growth = 单季利润同比。",
            "min": "增长下限（%）。",
            "max": "增长上限（%）。",
        },
        "examples": [
            "growth:field=season_income_growth,min=30  　→ 单季营收同比 > 30%",
            "growth:field=season_profit_growth,min=50  　→ 单季利润同比 > 50%",
        ],
        "caveats": "取最近一个已披露季度；一季报的单季值即累计值。"
                   "依赖 fundamental 表已更新到最新季度。",
    },

    # ---------------- 行情技术 ----------------
    "break_ma": {
        "intro": "均线突破 —— 最常用的「启动」信号。",
        "params": {
            "period": "均线周期，例如 5（5 日线）、20（月线）、60（季线）。默认 5。",
            "mode": "cross = 突破（前一日收盘在均线下、当日收盘在均线上）；"
                    "above = 站上（当日收盘在均线上即可，不要求刚刚突破）。默认 cross。",
        },
        "examples": [
            "break_ma:period=5  　→ 今天刚突破 5 日均线",
            "break_ma:period=20,mode=above  　→ 收在 20 日均线上方",
        ],
        "caveats": "用的是**前复权**收盘价；cross 当天信号很少，放宽可用 mode=above。",
    },
    "ma_align": {
        "intro": "均线多头排列（趋势向上的一种刻画）。",
        "params": {
            "periods": "均线周期，用短横线连接，按**从短到长**写。默认 5-10-20。",
        },
        "examples": [
            "ma_align:periods=5-10-20  　→ MA5 > MA10 > MA20（多头排列）",
            "ma_align:periods=20-10-5  　→ MA20 > MA10 > MA5（空头排列，用于找弱势股）",
        ],
        "caveats": "顺序即含义：写反了筛的是反向排列。",
    },
    "ma_trend": {
        "intro": "短均线在长均线之上（比 ma_align 宽松，只要求两条）。",
        "params": {
            "short": "短均线周期，默认 5。",
            "long": "长均线周期，默认 20，必须大于 short。",
        },
        "examples": ["ma_trend:short=5,long=20  　→ MA5 在 MA20 上方"],
    },
    "ma_cross": {
        "intro": "均线金叉：短均线在最近若干天内上穿长均线。",
        "params": {
            "short": "短均线周期，默认 5。",
            "long": "长均线周期，默认 20。",
            "window": "在最近多少个交易日内发生过金叉，默认 3。",
        },
        "examples": ["ma_cross:short=5,long=20,window=3  　→ 最近 3 日内 MA5 上穿 MA20"],
        "caveats": "窗口越大信号越多，但越滞后。",
    },
    "price_change": {
        "intro": "按区间涨跌幅筛选，基于**前复权**收盘价。",
        "params": {
            "bars": "回看多少个交易日。默认 20（约一个月）。",
            "min": "涨幅下限（%）。",
            "max": "涨幅上限（%）。",
        },
        "examples": [
            "price_change:bars=20,min=10  　→ 近 20 个交易日涨幅超过 10%",
            "price_change:bars=1,max=1  　→ 今天涨幅小于 1%",
            "price_change:bars=60,max=-5  　→ 近 3 个月累计下跌超过 5%",
        ],
    },
    "price_range": {
        "intro": "按区间振幅筛选，用来找「横盘整理」形态。",
        "params": {
            "bars": "回看多少个交易日，默认 5。",
            "max": "振幅上限（%），振幅 =(区间最高价 - 最低价) ÷ 最低价 × 100。",
        },
        "examples": [
            "price_range:bars=5,max=5  　→ 最近 5 日最高最低价差小于 5%（窄幅整理）",
            "price_range:bars=20,max=15  　→ 最近一个月波动不大",
        ],
    },
    "volume_ratio": {
        "intro": "按量比筛选：当日成交量 ÷ 之前若干日的平均成交量。",
        "params": {
            "bars": "均量的计算窗口（不含当日），默认 20。",
            "min": "量比下限。",
            "max": "量比上限。",
        },
        "examples": [
            "volume_ratio:min=2  　→ 今天放量到平时的 2 倍以上",
            "volume_ratio:max=0.5  　→ 今天明显缩量（配合突破可做「缩量回调」）",
        ],
    },
    "turnover_rate": {
        "intro": "按换手率筛选，衡量交易活跃度。",
        "params": {"min": "换手率下限（%）。", "max": "换手率上限（%）。"},
        "examples": ["turnover_rate:min=3  　→ 换手率高于 3%（活跃）",
                     "turnover_rate:max=1  　→ 换手率低于 1%（冷门、流动性差）"],
    },
}


def describe_filter(name: str) -> str:
    """生成单个过滤器的详细说明文本。"""
    cls = base.get_filter_class(name)
    doc = FILTER_GUIDE.get(name, {})

    lines = [f"● {name}"]
    lines.append(f"  {getattr(cls, 'description', '')}")
    if doc.get("intro"):
        lines.append(f"  {doc['intro']}")

    signature = inspect.signature(cls.__init__)
    params = [(n, p) for n, p in signature.parameters.items() if n != "self"]
    lines.append("  参数：")
    if not params:
        lines.append("    （无参数）")
    for param_name, param in params:
        if param.default is inspect.Parameter.empty or param.default is None:
            default = "，可不填"
        else:
            default = f"，默认 {param.default}"
        text = doc.get("params", {}).get(param_name, "")
        lines.append(f"    {param_name}{default}")
        if text:
            for chunk in _wrap(text, 46):
                lines.append(f"        {chunk}")

    if doc.get("examples"):
        lines.append("  例子：")
        for example in doc["examples"]:
            lines.append(f"    {example}")
    if doc.get("caveats"):
        lines.append("  注意：")
        for chunk in _wrap(doc["caveats"], 46):
            lines.append(f"    {chunk}")
    return "\n".join(lines)


def _wrap(text: str, width: int) -> list[str]:
    """按宽度粗略折行（中英文混排按字符数算），优先在标点处断开。"""
    lines: list[str] = []
    current = ""
    for index, char in enumerate(text):
        current += char
        next_char = text[index + 1] if index + 1 < len(text) else ""
        at_punctuation = char in "，。；、）%" and next_char not in "，。；、）」"
        if len(current) >= width and at_punctuation:
            lines.append(current)
            current = ""
        elif len(current) >= int(width * 1.6):   # 一直没有标点就硬断
            lines.append(current)
            current = ""
    if current:
        lines.append(current)
    return lines or [""]


def build_guide(groups: list[tuple[str, list[str]]] | None = None) -> str:
    """生成完整说明书（界面「说明」按钮弹出的内容）。"""
    sections = [SNAPSHOT_DOC, MECHANICS_DOC]

    if groups:
        sections.append("【筛选条件一览】\n" + "\n".join(
            f"  [{group}] " + "、".join(names) for group, names in groups if names))
        for group, names in groups:
            if not names:
                continue
            sections.append("=" * 60 + f"\n{group}\n" + "=" * 60)
            for name in names:
                sections.append(describe_filter(name))
    else:
        for name in base.available_filters():
            sections.append(describe_filter(name))

    return "\n\n".join(sections)
