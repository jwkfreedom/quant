import pandas as pd
import numpy as np
import sys
sys.path.append("..") 
import stockdata as sd
import utils.download as dl

# 交易策略 涨幅大于win_sell  或 跌幅大于 lose_sell 卖出， 最大持股日为5天(第一天为第0天)
strategy = {'win_sell': 0.03, 'lose_sell' : 0.05, 'max_hold': 5}


def prepareData(df) :
    for index, row in df.iterrows():
        stockId = row['stockId']
        stockIdStr = str(stockId).zfill(6)
        dl.stock_price(stockIdStr, force=True)

def doStrategy(stockId, startdate):
    iDATE = int(startdate.replace("/", ""))
    df = sd.get_stock_price(stockId)
    df = df[df['iDATE'] >= iDATE]
    prices = []
    print(df)
    index = 0
    for _index, row in df.iterrows():
        print(f"index={index}")
        prices.append(row['close_org'])
        index += 1
    
    return prices
    


df = pd.read_csv('record.csv')
# prepareData(df)
doStrategy('002334', '2023/11/28')