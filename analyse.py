import pandas as pd

import numpy as np
# import talib 


def get_stock_price(symbol):
    file_src=f"data/a/stock/price/price_{symbol}_"

    df_price_pre = pd.read_csv(file_src + "pre.csv")
    df_price_cur = pd.read_csv(file_src + "cur.csv")
    df_price = pd.concat([df_price_pre, df_price_cur])
    df_price.index = pd.DatetimeIndex(df_price['日期'])

    #,,,,,,,,,,,开盘_qfq,收盘_qfq,最高_qfq,最低_qfq
    columns = {"开盘": "open" , "日期": "date", "收盘": "close", "最高": "high", "最低": "low", "开盘_qfq": "open_qfq","收盘_qfq":"close_qfq","最高_qfq": "hight_qfq","最低_qfq":"low_qfq",
               "成交量": "volumn", "成交额": "turnover", "振幅":"amp", "涨跌幅": "percent_change", "涨跌额": "value_change", "换手率":"turnover_rate"}

    df_price.rename(columns=columns, inplace=True)
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



df = get_stock_price('000001')
print(df)

