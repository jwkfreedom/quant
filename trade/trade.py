import pandas as pd
import numpy as np
import sys
sys.path.append("..") 
import stockdata as sd
import utils.download as dl

# 交易策略 涨幅大于win_sell  或 跌幅大于 lose_sell 卖出， 最大持股日为5天(第一天为第0天)
strategy = {'win_sell': 0.03, 'lose_sell' : 0.05, 'max_hold': 5}
!!! 下一步是根据strategy 统计交易结果

def prepareData(df) :
    for index, row in df.iterrows():
        stockId = row['stockId']
        dl.stock_price(stockId, force=True)
        dl.stock_jibenmian(stockId, 0)

def calcScore(stockId, startdate):
    iDATE = int(startdate.replace("/", ""))
    df = sd.get_full_price(stockId)
    df = df[df['iDATE'] >= iDATE]
    prices = []
    for index, row in df.iterrows():
        prices.append(row['close_org'])
    
    return prices
    


df = pd.read_csv('record.csv')
#prepareData(df)
print(checkStockPrice('300491', '2023/11/28'))