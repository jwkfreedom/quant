import pandas as pd

def ana_a_stock(symbol):
    df_price = pd.read_csv(f"data/a/price_{symbol}.csv")
    df_price_qfq = pd.read_csv(f"data/a/price_{symbol}_qfq.csv")
    df_qfq_factor = pd.read_csv(f"data/a/qfq_{symbol}.csv")


    date = '2010-03-16'
    price = (df_price[df_price["date"]==date]['open'])
    price_qfq = (df_price_qfq[df_price["date"]==date]['open'])

    v = price / price_qfq

    print(f'v={v}')
    print(df_qfq_factor)


def get_qfq_factor(df, date_find):
    # loop through the date column and find values before a certain date
    for i, date in enumerate(df['date2']):
        if date >= pd.to_datetime(date_find):
            break
    return df.iloc[i]['qfq_factor']


symbol='sh600036'
df_qfq_factor = pd.read_csv(f"data/a/qfq_{symbol}.csv")
df_qfq_factor['date2'] = pd.to_datetime(df_qfq_factor['date'])

# sort the dataframe by date
df = df_qfq_factor.sort_values(by='date2')
print(get_qfq_factor(df, '2012-12-26'))