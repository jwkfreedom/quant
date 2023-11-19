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
import matplotlib.pyplot as plt
from scipy.signal import argrelextrema

sys.path.append("..") 
import stockdata as sd



"""
找出5日移动平均线上穿20日移动平均线的点，并在图上标记出来。这些点可能是股票强势上涨的开始。
"""
def ana_XXX(stockId) :
    # 读取CSV文件
    df = sd.get_full_price(stockId)

    # 计算5日移动平均线
    df['MA5'] = df['close'].rolling(window=5).mean()

    # 计算20日移动平均线
    df['MA20'] = df['close'].rolling(window=20).mean()

    # 找出5日移动平均线上穿20日移动平均线的点，这些点可能是股票强势上涨的开始
    df['buy_signal'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) < df['MA20'].shift(1))

    print(df.dtypes)
"""
    # 绘制收盘价和移动平均线
    plt.figure(figsize=(12,6))
    plt.plot(df['close'], label='Close Price')
    plt.plot(df['MA5'], label='MA5')
    plt.plot(df['MA20'], label='MA20')

    # 标记买入点
    plt.plot(df[df['buy_signal']]['close'], '^', markersize=10, color='r', label='buy signal')

    plt.title('Stock Price with Buy Signals')
    plt.xlabel('Date')
    plt.ylabel('Price')
    plt.legend()
    plt.grid(True)
    plt.show()
"""

"""
分析交易量突然增大与价格变动以及后续10个交易日涨跌的关系
"""
def ana_YYY(stockId):
    # 读取CSV文件
    df = sd.get_full_price(stockId)

    # 计算20日交易量平均值
    #df['MA_Volume20'] = df['volumn'].rolling(window=20).mean()
    df['volumn_mean_plus_3sigma'] = df['volumn'].rolling(window=20).mean().shift(1) * 3

    # 找出交易量突然增大到之前20个交易日的平均交易量的3倍的点
    df['volume_spike'] = df['volumn'] >  df['volumn_mean_plus_3sigma']

    # 计算价格变动
    df['price_change'] = df['close'] - df['open']

    # 计算后10个交易日的涨跌
    df['future_change'] = df['close'].shift(-10) - df['close']

    # 分析交易量突然增大的点的价格变动和后10个交易日的涨跌
    volume_spike_data = df[df['volume_spike']]
    pd.set_option('display.max_rows', 1000)
    print(df)
    #print(volume_spike_data[['price_change', 'future_change']].describe())




    # 绘制收盘价和移动平均线
    plt.figure(figsize=(12,6))
    plt.plot(df['close'], label='Close Price')

    # 标记买入点
    plt.plot(df[df['volume_spike']]['close'], '^', markersize=10, color='r', label='buy signal')

    plt.title('Stock Price with Buy Signals')
    plt.xlabel('Date')
    plt.ylabel('Price')
    plt.legend()
    plt.grid(True)
    plt.show()


#查询股票交易数据中一段时间内（比如一年）股价的多个高位和地位，即波峰和波谷，并且划线看趋势
#要找到股票价格的波峰和波谷，你可以使用 scipy 库中的 argrelextrema 函数。这个函数可以找到数组中的相对极大值和相对极小值。以下是如何使用这个函数的代码：
def ana_ZZZ(stockId):
    df = sd.get_full_price(stockId)
    df['date'] = pd.to_datetime(df['date'])  # 确保日期是 datetime 类型
    df.set_index('date', inplace=True)  # 将日期设为索引

    # 假设df是你的DataFrame，'close'是收盘价格
    data = df['close'].values
    # 计算价格变化的百分比
    change = np.diff(data) / data[:-1]

    # 找到极大值和极小值
    maxima = argrelextrema(change, np.greater)[0]
    minima = argrelextrema(change, np.less)[0]

    # 找到幅度大于30%的极大值和极小值
    significant_maxima = maxima[change[maxima] > 0.1]
    significant_minima = minima[change[minima] < -0.1]

    # 打印日期
    print("Significant maxima dates:", df.index[significant_maxima + 1])
    print("Significant minima dates:", df.index[significant_minima + 1])

    # 绘制股票价格
    plt.plot(data)

    # 绘制极大值
    plt.plot(significant_maxima, data[significant_maxima + 1], 'ro')

    # 绘制极小值
    plt.plot(significant_minima, data[significant_minima + 1], 'go')

    plt.show()
    """

    # 找到波峰和波谷
    df['min'] = df.iloc[argrelextrema(df.close.values, np.less_equal)[0]]['close']
    df['max'] = df.iloc[argrelextrema(df.close.values, np.greater_equal)[0]]['close']


    plt.figure(figsize=(15,10))
    plt.plot(df.index, df['close'])
    plt.plot(df.index, df['min'], marker='o', markersize=5, color='r')
    plt.plot(df.index, df['max'], marker='o', markersize=5, color='g')
    plt.show()
    """

ana_ZZZ('688050')






"""
要分析交易量突然增大与价格变动以及后续10个交易日涨跌的关系，你可以使用pandas库来处理数据。以下是一个Python代码示例：
import pandas as pd


"""


