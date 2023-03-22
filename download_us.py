"""
下载 美股 数据
"""
import akshare as ak
import pandas as pd

# 知名美股
def good_stocks():
    types = ['科技类', '金融类', '医药食品类', '媒体类', '汽车能源类', '制造零售类']
    dftotal = pd.DataFrame()

    for type in types:
        df = ak.stock_us_famous_spot_em(symbol=type)
        print(df)
        if dftotal.empty:
            dftotal = df
        else :
            dftotal = pd.merge(dftotal, df)
    
    print(dftotal)


good_stocks()