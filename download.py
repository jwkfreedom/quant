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
def jibenmian_all():
    stockIds = all_a_stocks()
    for stockId in stockIds:
        stock_jibenmian(stockId, 0)

# 获取所有股价的日K
def stock_price_all(down_2022=False):
    stockIds = all_a_stocks()
    for stockId in stockIds:
        stock_price(stockId, down_2022)

# ----- 下载 一只股票的基本面数据 ------
    """
    ak.stock_balance_sheet_by_report_em(symbol) # 资产负债表-按报告期  eastmoney
    ak.stock_balance_sheet_by_yearly_em(symbol)  # 资产负债表-年度

    ak.stock_profit_sheet_by_report_em(symbol) # 利润表-报告期  eastmoney
    ak.stock_profit_sheet_by_yearly_em(symbol) # 利润表-年度

    ak.stock_cash_flow_sheet_by_report_em(symbol) # 现金流量表-按报告期 eastmoney
    ak.stock_cash_flow_sheet_by_yearly_em(symbol) # 现金流量表-年度

    ak.stock_financial_analysis_indicator(symbol) # 主要财务指标 新浪 (eastmoney的资产负债表的数据没有具体说明， 所以资产负债率等数据可以使用本表)
    """
# symbol: 股票代码 格式: SHXXXXX or SZXXXXXX
# delay: 每下载一个文件延迟的时间(秒)
# type: None: 所有种类的基本面数据, "zcfz_report" or other: 指定的基本面数据
def stock_jibenmian(symbol, delay, jbm_type=None):
    funcList = [#{type: 'zcfz_report', func: ak.stock_balance_sheet_by_report_em, platform: 'eastmoney'},
               #{'type':'lrb_report', 'func' : ak.stock_profit_sheet_by_report_em, platform: 'eastmoney'},
               #{'type':'xjll_report', 'func': ak.stock_cash_flow_sheet_by_report_em, platform: 'eastmoney'},
               {'type': 'financial_report', 'func': ak.stock_financial_analysis_indicator, 'platform': 'sina'}]
    dest = 'data/a/stock/{}/{}_{}.csv'    # data/a/SHXXX/lrb_report_SHXXXXXX.csv
    for funcItem in funcList:
        type = funcItem['type']
        func = funcItem['func']
        platform = funcItem['platform']

        if jbm_type != None and jbm_type != type:
            continue
        subdir = symbol[:3]
        filename = dest.format(subdir, type, symbol)
        if not os.path.exists(filename):
            try:
                p_symbol = PlatformSymbol(symbol, platform)
                df = func(p_symbol)
                print(f"write {filename}")
                df.to_csv(filename)
                if(delay > 0):
                    time.sleep(delay)
            except:
                print(f"exec error: stock={symbol}, type={type}")
            else:
                print(f"exec ok: stock={symbol}, type={type}")
        else:
            print(f"skip: stock={symbol}, type={type}")
# ------ 下载股票日线数据 ------
# A股股票日线数据，整合了前复权和未复权数据到一张表里
# down_2022: 是否下载2022年之前的数据
def stock_price(symbol, down_2022=False):
    file_2022 = f"data/a/price_{symbol}_2022.csv"   # 2022年(含)以前的数据
    file_cur = f"data/a/price_{symbol}_cur.csv"     # 2023年~当前的数据

    p_symbol = PlatformSymbol(symbol, 'sinaprice')
    if down_2022:
        df_stock_2022 = ak.stock_zh_a_daily(symbol=p_symbol, start_date="20100101", end_date="20221231", adjust="")
        df_stock_2022_qfq = ak.stock_zh_a_daily(symbol=p_symbol, start_date="20100101", end_date="20221231", adjust="qfq")
        copy_qfq_data(df_stock_2022_qfq, df_stock_2022)
        df_stock_2022.to_csv(file_2022)

    cur_date = datetime.datetime.now().strftime("%Y%m%d")   # YYYYMMDD
    df_stock_cur = ak.stock_zh_a_daily(symbol=p_symbol, start_date="20230101", end_date=cur_date, adjust="")
    df_stock_cur_qfq = ak.stock_zh_a_daily(symbol=p_symbol, start_date="20230101", end_date=cur_date, adjust="qfq")
    copy_qfq_data(df_stock_cur_qfq, df_stock_cur)
    df_stock_cur.to_csv(file_cur)




# 把前复权的数据拷贝到没有前复权的数据中
# dfqfq: 前复权的股票价格
def copy_qfq_data(dfqfq, df):
    columns=['open','high','low','close']

    for column in columns:
        df[f'{column}_qfq'] = dfqfq[column]

# 获取所有 A股股票Id
# 返回: [600332, 2278...] 格式
def all_a_stocks():
    full_stock_file = 'data/a/jibenmian/zcfz_20220930.csv'    # 注意！！只会拉取这个文件中的 股票列表 中的股票。所以一般选取距拉取时间半年前的 资产负债表 的数据
    df = pd.read_csv(full_stock_file)
    stockIds = map(PlatformSymbol, df['股票代码']) # df['股票代码']
    return stockIds

# 数字转为 股票代码 
#   例如 
#       eastmoney: 603339->'SH603339', 2985->'SZ002985'
#       sina: 603339->603339, 2985->002985
def PlatformSymbol(stockId, platform="") :
    stockId = str(stockId).zfill(6)

    if platform == "eastmoney":
        if stockId.startswith(('0', '3')):
            stockId = 'SZ' + stockId
        elif stockId.startswith('6'):
            stockId = 'SH' + stockId
        else:
            print("not support stockId:" + stockId)
    elif platform == "sinaprice":   # 新浪获取日K数据和财务数据对symbol要求不一样
        if stockId.startswith(('0', '3')):
            stockId = 'sz' + stockId
        elif stockId.startswith('6'):
            stockId = 'sh' + stockId
        else:
            print("not support stockId:" + stockId)       
           
    return stockId
 


# jibenmian('xjll', 2022, 2023)
# jibenmian_details()
# stock_price("600036", True)
# stock_jibenmian("600111", 0)


jibenmian_all()