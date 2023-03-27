import pandas as pd
import mplfinance as mpf

def ana_a_stock(symbol):
    df_price_2022 = pd.read_csv(f"data/a/price_{symbol}_2022.csv")
    df_price_cur = pd.read_csv(f"data/a/price_{symbol}_cur.csv")
    df_price = pd.concat([df_price_2022, df_price_cur])
    df_price.index = pd.DatetimeIndex(df_price['date'])
    df_price = df_price.loc["2023-02-06": "2023-03-10"]
    mpf.plot(df_price, type='candle')

    print(df_price)
    



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

ana_a_stock('sh600036')