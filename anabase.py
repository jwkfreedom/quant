import stockdata as sd
import pandas as pd
import ta
import matplotlib.pyplot as plt


def MACD(df):
    # 计算MACD
    df['MACD'] = ta.trend.macd(df['close'])

    # MACD信号线
    df['MACD_Signal'] = ta.trend.macd_signal(df['close'])

    # MACD差异
    df['MACD_Diff'] = ta.trend.macd_diff(df['close'])

        # 创建一个新的figure
    plt.figure(figsize=(12,8))

    # 绘制MACD线
    plt.plot(df.index, df['MACD'], label='MACD')
    # 绘制MACD信号线
    plt.plot(df.index, df['MACD_Signal'], label='Signal Line')
    # 填充MACD差异
    plt.fill_between(df.index, df['MACD_Diff'], 0, alpha=0.5, label='MACD Histogram')
    # 添加图例
    plt.legend(loc='upper left')
    # 显示图形
    plt.show()



stockId = '688050'
df = sd.get_full_price(stockId)
MACD(df)