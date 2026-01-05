import akshare as ak
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# 获取 SPY 和 SSO 的历史日线数据（美股）
spy = ak.stock_us_daily(symbol="SPY", adjust="qfq")  # qfq 表示前复权
sso = ak.stock_us_daily(symbol="SSO", adjust="qfq")

# 只保留收盘价并重命名
spy = spy[['date', 'close']].rename(columns={'close': 'spy_close'})
sso = sso[['date', 'close']].rename(columns={'close': 'sso_close'})

# 合并数据（按日期对齐）
df = pd.merge(spy, sso, on='date', how='inner')
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values('date').reset_index(drop=True)

# 初始资金分配（假设总资金为 1.0）
initial_capital = 1.0
spy_weight = 1.0  # 初始全部持有 SPY
sso_weight = 0.0

# 记录每个持仓的成本（用于判断 SSO 是否上涨 10%）
sso_cost_basis = 0.0  # 平均持仓成本
sso_position_value = 0.0  # 当前 SSO 持仓市值
buy_sso_high = 0.0

# 记录历史净值
net_values = []
dates = []

# 初始化前期高点
prev_high = df.loc[0, 'spy_close']


for i, row in df.iterrows():
    date = row['date']
    spy_price = row['spy_close']
    sso_price = row['sso_close']

    # 更新前期高点（只向上更新）
    if spy_price > prev_high:
        prev_high = spy_price

    # 条件1: SPY 从前期高点下跌 >=3%
    if spy_price <= prev_high * (1 - 0.03):
        # 将当前总资产的 5% 从 SPY 转为 SSO
        total_value = spy_weight + sso_weight
        transfer_amount = total_value * 0.05
        if sso_weight <= 0.010:
            buy_sso_high = spy_price

        # 限制不能卖空
        if spy_weight >= transfer_amount:
            spy_weight -= transfer_amount
            print(f"==SPY->SSO==Sell {transfer_amount:.2f} SPY at {spy_price:.2f}  on{date}")
            sso_weight += transfer_amount
            print(f"==SPY->SSO==Buy {transfer_amount:.2f} SSO at {sso_price:.2f}  on{date}")

            # # 更新 SSO 成本基础（加权平均）
            # if sso_position_value == 0:
            #     sso_cost_basis = sso_price
            # else:
            #     total_sso_value = sso_position_value + transfer_amount
            #     sso_cost_basis = (sso_cost_basis * sso_position_value + sso_price * transfer_amount) / total_sso_value

            # sso_position_value = sso_weight  # 因为以净值单位计算，这里简化处理

            # 重置前期高点，避免连续触发
            prev_high = spy_price

    # 条件2: SSO 当前价格比成本高 >=10%，且有持仓
    if sso_weight > 0 :
        if spy_price >= buy_sso_high * (1 + 0.10):
            # 卖出 1/5 的 SSO 换回 SPY
            sell_amount = sso_weight * (1/5)
            sso_weight -= sell_amount
            print(f"====SSO->SPY==Sell {sell_amount:.2f} SSO at {sso_price:.2f}  on{date}")
            spy_weight += sell_amount
            print(f"====SSO->SPY==Buy {sell_amount:.2f} SPY at {spy_price:.2f}  on{date}")


            buy_sso_high = buy_sso_high * (1 + 0.10)
            # 更新 SSO 成本（剩余部分的成本不变）
            #J sso_position_value = sso_weight
            # 若全部卖出，则重置成本
            if sso_weight == 0:
                sso_cost_basis = 0.0

    # 计算当前总资产（按当日价格）
    # 注意：我们以“份额”方式跟踪更准确，但这里简化用“权重 × 价格比例”模拟
    # 更严谨的做法是记录份额数量，此处为简化，假设初始1元全买SPY，然后按比例转换
    # 我们用净值法：每一步资产 = spy_weight * (spy_price / spy_initial) + sso_weight * (sso_price / sso_initial)
    # 但为了简化，我们直接用相对收益累积（见下方替代方法）

    # 替代方案：记录实际份额
    # 由于上面用了“权重”作为金额，我们可以直接用 spy_weight + sso_weight 作为净值（因为每天价格已隐含在转换中）
    # 但这样不准确！更好的方式是从头记录份额。

    # —— 修正：改用份额跟踪 ——
    # 我们重新设计：用实际份额而非“权重”

# -----------------------------
# 重新实现：使用份额跟踪（更准确）
# -----------------------------

# 初始化
spy_shares = 1.0  # 初始用1美元买入 SPY，所以份额 = 1 / spy_price_0
sso_shares = 0.0
spy_init_price = df.loc[0, 'spy_close']
spy_shares = initial_capital / spy_init_price

prev_high = df.loc[0, 'spy_close']
sso_cost_basis_per_share = 0.0  # SSO 的平均买入成本（每份）
last_rebalance_date = None

net_values = []
dates = []

for i, row in df.iterrows():
    date = row['date']
    spy_price = row['spy_close']
    sso_price = row['sso_close']

    # 更新前期高点
    if spy_price > prev_high:
        prev_high = spy_price

    # 当前总资产
    total_value = spy_shares * spy_price + sso_shares * sso_price

    # 条件1: SPY 从前期高点回撤 >=3%
    if spy_price <= prev_high * (1 - 0.03):
        # 转移总资产的 5% 到 SSO
        transfer_value = total_value * 0.05
        # 卖出等值的 SPY
        spy_sell_shares = transfer_value / spy_price
        if spy_sell_shares <= spy_shares:
            spy_shares -= spy_sell_shares
            sso_buy_shares = transfer_value / sso_price
            sso_shares += sso_buy_shares

            # 更新 SSO 成本基础（加权平均）
            total_sso_cost = sso_cost_basis_per_share * (sso_shares - sso_buy_shares) + sso_price * sso_buy_shares
            sso_cost_basis_per_share = total_sso_cost / sso_shares if sso_shares > 0 else 0.0

            # 重置高点，防止连续触发
            prev_high = spy_price

    # 条件2: SSO 当前价格 >= 成本 * 1.10 且有持仓
    if sso_shares > 0 and sso_cost_basis_per_share > 0:
        if sso_price >= sso_cost_basis_per_share * 1.10:
            # 卖出 1/5 的 SSO 份额
            sell_shares = sso_shares * (1/5)
            sso_shares -= sell_shares
            spy_buy_shares = (sell_shares * sso_price) / spy_price
            spy_shares += spy_buy_shares

            # 更新 SSO 成本（剩余份额成本不变）
            if sso_shares == 0:
                sso_cost_basis_per_share = 0.0
            # 否则成本不变（FIFO 或平均成本，这里用平均成本，但卖出不影响剩余成本）

    # 记录净值
    current_value = spy_shares * spy_price + sso_shares * sso_price
    net_values.append(current_value)
    dates.append(date)

# 构建净值曲线
result_df = pd.DataFrame({'date': dates, 'portfolio_value': net_values})
result_df.set_index('date', inplace=True)

# 对比基准（纯 SPY）
spy_benchmark = df.copy()
spy_benchmark.set_index('date', inplace=True)
spy_benchmark = spy_benchmark.loc[result_df.index]
spy_benchmark['spy_value'] = (spy_benchmark['spy_close'] / spy_benchmark['spy_close'].iloc[0]) * initial_capital

# 合并
compare_df = pd.merge(result_df, spy_benchmark[['spy_value']], left_index=True, right_index=True)

# 绘图
plt.figure(figsize=(12, 6))
plt.plot(compare_df.index, compare_df['portfolio_value'], label='Strategy (SPY+SSO)', color='blue')
plt.plot(compare_df.index, compare_df['spy_value'], label='Buy & Hold SPY', color='gray', linestyle='--')
plt.title('Strategy vs SPY Buy & Hold')
plt.xlabel('Date')
plt.ylabel('Portfolio Value ($)')
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()

print("----------------------------")
# 输出最终收益
final_strategy = compare_df['portfolio_value'].iloc[-1]
final_spy = compare_df['spy_value'].iloc[-1]
print(f"策略最终净值: ${final_strategy:.2f}")
print(f"SPY 持有净值: ${final_spy:.2f}")
print(f"超额收益: {((final_strategy / final_spy) - 1) * 100:.2f}%")