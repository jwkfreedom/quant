# 导入相关模块
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import mplfinance as mpf
from scipy.signal import find_peaks


import sys
sys.path.append("..") 
import stockdata as sd

# 定义函数：寻找价格峰值
def find_price_peaks(prices):
    peaks, _ = find_peaks(prices)
    peaks = peaks[np.diff(peaks, prepend=[0]) > 7]
    return peaks


# 定义函数：检测头肩顶形态
def detect_head_and_shoulder(prices):
    # 获取三个峰点
    peaks = find_price_peaks(prices)
    print(peaks)
    if len(peaks) < 3:
        return False

    # 根据峰值位置，计算左右肩峰值之间的谷底位置
    left_peak, peak, right_peak = np.sort(peaks)[-3:]
    left_min = np.argmin(prices[left_peak:peak]) + left_peak
    right_min = np.argmin(prices[peak:right_peak]) + peak

    # 判断形态是否符合要求
    is_left_side_downward_slope = prices[left_peak] > prices[left_min]
    is_right_side_downward_slope = prices[right_peak] > prices[right_min]
    is_head_wider_than_shoulders = np.abs(left_peak-peak) > np.abs(right_peak-peak)
    is_price_below_neckline = prices[right_min] > prices[peak]

    return (is_left_side_downward_slope and
            is_right_side_downward_slope and
            is_head_wider_than_shoulders and
            is_price_below_neckline)

# 下载并展示股票数据
stockId = '000505'
df = sd.get_full_price(stockId)

prices = df['close']

# 检测头肩顶形态
if detect_head_and_shoulder(prices):
    print('检测到头肩顶形态')
else:
    print('未检测到头肩顶形态')

# 绘制K线图并展示
mpf.plot(df, type='candle', style='charles', warn_too_much_data=10000)