"""
下载 美股 数据
"""
import akshare as ak
import pandas as pd
import yfinance as yf
# 知名美股 通过该函数获得需要拉取的美股的id
def good_stocks():
    types = ['科技类', '金融类', '医药食品类', '媒体类', '汽车能源类', '制造零售类']
    dfs = []

    for type in types:
        df = ak.stock_us_famous_spot_em(symbol=type)
        dfs.append(df)

    dftotal = pd.concat(dfs, ignore_index=False)
    dftotal.to_csv('data/us/good_stocks.csv')


def get_financial_data(symbol):
# Define the ticker symbol


    # Get data for the specified ticker
    tickerData = yf.Ticker("MSFT")
    print(tickerData.info)

    # balance_sheet = tickerData.balance_sheet
    # income_statement = tickerData.financials
    # cash_flow = tickerData.cashflow

get_financial_data('MSFT')