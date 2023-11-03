"""
数据准备:
    step1. 下载基本面数据
        process.py: 运行: download_a_jibenmian,  
        注意要修改日期
    
    step2. 生成包括所有股票的基本面数据文件
        process.py: calc_a_growth(2021, 'data/202101-lastseason.csv') 得到2021年至上个季度的数据
        注意: 这里只包括数据完整的股票，如果有股票数据不完整，会被删除
        生成文件中增加了以下数据
            preYearIncome,SeasonIncomeGrowth,SeasonIncome,preYearProfit,SeasonProfitGrowth,SeasonProfit
"""
import pandas as pd
import numpy as np
import stockdata as sd

DATA_ROOT='d:/github/quant/data'

def ana_XXX() :
    df = pd.read_csv(f'{DATA_ROOT}/202101-202204.csv')

