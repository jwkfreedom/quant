import pandas as pd

import numpy as np
import talib 


def get_stock_price(symbol, fq="qfq"):
    file_src=f"data/a/stock/price/price_{symbol}_"

    df_price_2022 = pd.read_csv(file_src + "2022.csv")
    df_price_cur = pd.read_csv(file_src + "cur.csv")
    df_price = pd.concat([df_price_2022, df_price_cur])
    df_price.index = pd.DatetimeIndex(df_price['date'])

    if fq=="qfq":
        columns=['open','high','low','close']
        for column in columns:
            df_price[column] = df_price[f'{column}_qfq']

    # df_price = df_price.loc["2023-02-06": "2023-03-10"]
    # print(df_price)
    return df_price

# 读入financial 数据，
def get_financail_data(symbol):
    file_src=f"data/a/stock/financial/financial_report_{symbol}.csv"
    df_org = pd.read_csv(file_src)
    df = pd.DataFrame()
    df['date'] = df_org['日期']
    df['netprofit'] = df_org['扣除非经常性损益后的净利润(元)']
    df['coreprofit'] = df_org['主营业务利润(元)']
    return df
    

# 由日期获得前复权的factor
# df 是前复权因子的dataframe
def get_qfq_factor(df, date_find):
    df['date2'] = pd.to_datetime(df['date'])
    df = df.sort_values(by='date2')
    # loop through the date column and find values before a certain date
    for i, date in enumerate(df['date2']):
        if date >= pd.to_datetime(date_find):
            break
    return df.iloc[i]['qfq_factor']

def ana_stock(data):
    # 计算指标
    data['MA5'] = talib.MA(data['close'], timeperiod=5)
    data['MA10'] = talib.MA(data['close'], timeperiod=60)
    data['RSI'] = talib.RSI(data['close'], timeperiod=14)

    
    # 判断买卖信号
    data['signal'] = np.where((data['MA5'] > data['MA10']) & (data['RSI'] < 30), 1, 0)
    data['position'] = data['signal'].diff()

    # 回测
    data['pnl'] = data['position'] * data['close'].pct_change()
    data['cum_pnl'] = data['pnl'].cumsum()
    data['cum_return'] = np.exp(np.log1p(data['cum_pnl']).cumsum()) - 1

    # 输出结果
    # print(data[['date', 'open', 'high', 'low', 'close', 'signal', 'pnl', 'cum_return']])
    print(data[data['signal']>0])

    return data



df = get_financail_data('000001')
print(df)

