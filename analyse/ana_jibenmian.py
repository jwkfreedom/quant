"""
数据准备:
    step1. 下载基本面数据
        process.py: 运行: download_a_jibenmian,  
        注意要修改日期
    
    step2. 生成包括所有股票的基本面数据文件
        process.py: calc_a_growth(2021, 'data/202101-lastseason.csv') 得到2021年至上个季度的数据
        注意: 这里只包括数据完整的股票，如果有股票数据不完整，会被删除
        生成文件中增加了以下数据
            preYearIncome,SeasonIncomeGrowth,SeasonIncome,preYearProfit,SeasonProfitGrowth,SeasonProfit
"""
import pandas as pd
import numpy as np
import sys
sys.path.append("..") 
import stockdata as sd

DATA_ROOT='d:/github/quant/data'

def ana_XXX() :
    df = pd.read_csv(f'{DATA_ROOT}/202101-lastseason.csv')

    print(df)





ana_XXX()

"""
要分析交易量突然增大与价格变动以及后续10个交易日涨跌的关系，你可以使用pandas库来处理数据。以下是一个Python代码示例：
import pandas as pd

# 读取CSV文件
df = pd.read_csv('stock_data.csv')

# 计算20日交易量平均值
df['MA_Volume20'] = df['volumn'].rolling(window=20).mean()

# 找出交易量突然增大到之前20个交易日的平均交易量的3倍的点
df['volume_spike'] = df['volumn'] > 3 * df['MA_Volume20']

# 计算价格变动
df['price_change'] = df['close'] - df['open']

# 计算后10个交易日的涨跌
df['future_change'] = df['close'].shift(-10) - df['close']

# 分析交易量突然增大的点的价格变动和后10个交易日的涨跌
volume_spike_data = df[df['volume_spike']]
print(volume_spike_data[['price_change', 'future_change']].describe())
"""


"""
这个代码会找出5日移动平均线上穿20日移动平均线的点，并在图上标记出来。这些点可能是股票强势上涨的开始。
但请注意，这只是一个基本的示例，实际的股票交易策略可能需要考虑更多的因素和更复杂的算法。
import pandas as pd
import matplotlib.pyplot as plt

# 读取CSV文件
df = pd.read_csv('stock_data.csv')

# 计算5日移动平均线
df['MA5'] = df['收盘价'].rolling(window=5).mean()

# 计算20日移动平均线
df['MA20'] = df['收盘价'].rolling(window=20).mean()

# 找出5日移动平均线上穿20日移动平均线的点，这些点可能是股票强势上涨的开始
df['buy_signal'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) < df['MA20'].shift(1))

# 绘制收盘价和移动平均线
plt.figure(figsize=(12,6))
plt.plot(df['收盘价'], label='Close Price')
plt.plot(df['MA5'], label='MA5')
plt.plot(df['MA20'], label='MA20')

# 标记买入点
plt.plot(df[df['buy_signal']]['收盘价'], '^', markersize=10, color='r', label='buy signal')

plt.title('Stock Price with Buy Signals')
plt.xlabel('Date')
plt.ylabel('Price')
plt.legend()
plt.grid(True)
plt.show()

"""