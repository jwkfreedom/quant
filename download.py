"""
下载数据
    jibenmian: 下载基本面数据（业绩快报），支持 资产负债表，利润表，现金流量表
    stock_daily: 下载股票日线
"""
import akshare as ak
import pandas as pd
import time
import os
import datetime


# ----- 下载所有A股股票基本面概要数据数据（业绩快报） ------
# 资产负债表    'zcfz': ak.stock_zcfz_em
# 利润表        'lrb': ak.stock_lrb_em
# 现金流量表    'xjll' : ak.stock_xjll_em
#   jibenmian = 基本面
#       type = 'zcfz'(资产负债)， lrb(利润表), xjll(现金流量)
#       year = YYYY (比如2010)
#       season = ["{year}0331", "{year}0630", "{year}0930", "{year}1231"] 数组中的一个或几个
def all_jibenmian(type, yStart, yEnd, season=["{year}0331", "{year}0630", "{year}0930", "{year}1231"]):
    funcMap = {'zcfz': ak.stock_zcfz_em, 'lrb': ak.stock_lrb_em, 'xjll' : ak.stock_xjll_em}
    dest = "data/a/jibenmian/{}_{}.csv"   # 输出文件位置

    if not type in funcMap :
        print("error type:" + type)
        return
    func = funcMap[type]

    for year in range(yStart, yEnd):
        for downDate in season:
            date = downDate.format(year=year)
            filename = dest.format(type, date)
            
            df = func(date=date)
            df.to_csv(filename)

            time.sleep(3)


#
#   下载所有A股股票的基本面详细数据，包括 资产负债表， 利润表， 现金流量表
#
def jibenmian_details():
    stockIds = all_a_stocks()
    for stockId in stockIds:
        stock_jibenmian(stockId, 0)


# ----- 下载 一只股票的基本面数据 ------
    """
    ak.stock_balance_sheet_by_report_em(symbol) # 资产负债表-按报告期
    ak.stock_balance_sheet_by_yearly_em(symbol)  # 资产负债表-年度

    ak.stock_profit_sheet_by_report_em(symbol) # 利润表-报告期
    ak.stock_profit_sheet_by_yearly_em(symbol) # 利润表-年度

    ak.stock_cash_flow_sheet_by_report_em(symbol) # 现金流量表-按报告期
    ak.stock_cash_flow_sheet_by_yearly_em(symbol) # 现金流量表-年度
    """
# symbol: 股票代码 格式: SHXXXXX or SZXXXXXX
# delay: 每下载一个文件延迟的时间(秒)
def stock_jibenmian(symbol, delay):
    funcMap = {'zcfz_report': ak.stock_balance_sheet_by_report_em, 
               'lrb_report' : ak.stock_profit_sheet_by_report_em,
               'xjll_report': ak.stock_cash_flow_sheet_by_report_em}
    dest = 'data/a/{}/{}_{}.csv'    # data/a/SHXXX/lrb_report_SHXXXXXX.csv
    for type, func in funcMap.items():
        subdir = symbol[:5]

        filename = dest.format(subdir, type, symbol)
        if not os.path.exists(filename):
            try:
                df = func(symbol)
                df.to_csv(filename)
                if(delay > 0):
                    time.sleep(delay)
            except:
                print(f"exec error: stock={symbol}")
            else:
                print(f"exec ok: stock={symbol}")
        else:
            print(f"skip: stock={symbol}, type={type}")
# ------ 下载股票日线数据 ------
# A股股票日线数据，整合了前复权和未复权数据到一张表里
# down_2022: 是否下载2022年之前的数据
def stock_price(symbol, down_2022=False):
    file_2022 = f"data/a/price_{symbol}_2022.csv"   # 2022年(含)以前的数据
    file_cur = f"data/a/price_{symbol}_cur.csv"     # 2023年~当前的数据

    if down_2022:
        cur_date = datetime.datetime.now().strftime("%Y%m%d")   # YYYYMMDD
        df_stock_2022 = ak.stock_zh_a_daily(symbol=symbol, start_date="20100101", end_date="20221231", adjust="")
        df_stock_2022_qfq = ak.stock_zh_a_daily(symbol=symbol, start_date="20100101", end_date="20221231", adjust="qfq")
        copy_qfq_data(df_stock_2022_qfq, df_stock_2022)
        df_stock_2022.to_csv(file_2022)

    df_stock_cur = ak.stock_zh_a_daily(symbol=symbol, start_date="20230101", end_date=cur_date, adjust="")
    df_stock_cur_qfq = ak.stock_zh_a_daily(symbol=symbol, start_date="20230101", end_date=cur_date, adjust="qfq")
    copy_qfq_data(df_stock_cur_qfq, df_stock_cur)
    df_stock_cur.to_csv(file_cur)




# 把前复权的数据拷贝到没有前复权的数据中
# dfqfq: 前复权的股票价格
def copy_qfq_data(dfqfq, df):
    columns=['open','high','low','close']

    for column in columns:
        df[f'{column}_qfq'] = dfqfq[column]

# 获取所有 A股股票Id
def all_a_stocks():
    full_stock_file = 'data/jibenmian/zcfz_20220930.csv'    # 注意！！只会拉取这个文件中的 股票列表 中的股票。所以一般选取距拉取时间半年前的 资产负债表 的数据
    df = pd.read_csv(full_stock_file)
    stockIds = map(StockFormat, df['股票代码'])
    return stockIds

# 数字转为 股票代码 例如: 603339->'SH603339', 2985->'SZ002985'
def StockFormat(stockId) :
    stockId = str(stockId).zfill(6)
    if stockId.startswith(('0', '3')):
        stockId = 'SZ' + stockId
    elif stockId.startswith('6'):
        stockId = 'SH' + stockId
    else:
        print("not support stockId:" + stockId)
    return stockId
 


# jibenmian('xjll', 2022, 2023)
# jibenmian_details()
# stock_price("sh600036")
stock_price("sz002508", True)

