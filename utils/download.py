"""
下载数据
    jibenmian_all_fast: 下载基本面数据（业绩快报），支持 资产负债表，利润表，现金流量表
    jibenmian_all: 下载所有A股股票的基本面详细数据，包括 资产负债表， 利润表， 现金流量表
    stock_jibenmian: 单一股票的基本面详细数据

    stock_price_all: 下载所有股票日线数据
    stock_price: 下载单一股票的日线数据
"""
import akshare as ak
import pandas as pd
import time
import os
import datetime

DATA_PATH="data"





#
# 下载etf的日成交数据 
#
def download_etf(start_date = "20180101", end_date = "20230201"):
    etf_list = ["515050",	"512480",	"159867",	"512980",	"159992",	"515400",	"159611",	"159997",	"512200",	"515210",	"159638",	"515790",	"512670",	"510880",	"159870",	"518880",	"159937",	"518800",	"516950",	"159998",	"159996",	"159745",	"510230",	"512690",	"512660",	"588200",	"588100",	"515000",	"516050",	"159840",	"159766",	"515220",	"159825",	"516110",	"512000",	"159819",	"515230",	"515710",	"515170",	"560800",	"561190",	"159790",	"516150",	"159928",	"159995",	"516160",	"515030",	"159939",	"512330",	"159959",	"159865",	"512170",	"159883",	"512010",	"562860",	"512800",	"159736",	"159869",	"512400",	"516510",	"515250",	"513050",	"560080"]

    dfs = []
    columns = {"开盘": "open" , "日期": "date", "收盘": "close", "最高": "high", "最低": "low", "成交量": "volumn", "成交额": "turnover", "振幅":"amp", "涨跌幅": "percent_change", "涨跌额": "value_change", "换手率":"turnover_rate"}
    for symbol in etf_list:
        df = ak.fund_etf_hist_em(symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
        df.rename(columns=columns, inplace=True)
        df.to_csv(f"{DATA_PATH}/a/etf/price/etf_{symbol}.csv", index=False)

        df['name'] = symbol
        dfs.append(df)
        print(f"download etf_{symbol} ok")
    #dftotal = pd.concat(dfs, ignore_index=False)
    #dftotal.to_csv(f'{DATA_PATH}/a/etf/etf_all.csv', index=False, encoding='utf_8_sig')


# ----- 下载所有A股股票基本面概要数据数据（业绩快报） ------
# 资产负债表    'zcfz': ak.stock_zcfz_em
# 利润表        'lrb': ak.stock_lrb_em
# 现金流量表    'xjll' : ak.stock_xjll_em
# 业绩报表(正式) '' : ak.stock_yjbb_em
#   jibenmian = 基本面
#       type = 'zcfz'(资产负债)， lrb(利润表), xjll(现金流量)
#       year = YYYY (比如2010)
#       season = ["{year}0331", "{year}0630", "{year}0930", "{year}1231"] 数组中的一个或几个
def jibenmian_all_fast(type, yStart, yEnd, season=["{year}0331", "{year}0630", "{year}0930", "{year}1231"]):
    funcMap = {'zcfz': ak.stock_zcfz_em, 'lrb': ak.stock_lrb_em, 'xjll' : ak.stock_xjll_em}
    dest = DATA_PATH + "/a/jibenmian/{}_{}.csv"   # 输出文件位置

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
def stock_price_all(down_pre=False):
    stockIds = all_a_stocks()
    for stockId in stockIds:
        stock_price(stockId, down_pre)

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
    dest = DATA_PATH + '/a/stock/{}/{}_{}.csv'    # data/a/SHXXX/lrb_report_SHXXXXXX.csv
    for funcItem in funcList:
        type = funcItem['type']
        func = funcItem['func']
        platform = funcItem['platform']

        if jbm_type != None and jbm_type != type:
            continue
        subdir = type.split('_')[0]
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
def stock_price(symbol, down_preyear=False):
    thisyear = int(datetime.datetime.now().strftime("%Y"))
    preyear = thisyear - 1

    file_pre = f"{DATA_PATH}/a/stock/price/price_{symbol}_pre.csv"   # 2022年(含)以前的数据
    file_cur = f"{DATA_PATH}/a/stock/price/price_{symbol}_cur.csv"     # 2023年~当前的数据
    p_symbol = PlatformSymbol(symbol)

    if not os.path.exists(file_pre):
        try:
            if down_preyear:
                end_date = f"{preyear}1231"
                df_stock_pre = ak.stock_zh_a_hist (symbol=p_symbol, period="daily", start_date="20100101", end_date=end_date, adjust="")
                df_stock_pre_qfq = ak.stock_zh_a_hist (symbol=p_symbol, period="daily", start_date="20100101", end_date=end_date, adjust="qfq")
                copy_qfq_data(df_stock_pre_qfq, df_stock_pre)
                df_stock_pre.to_csv(file_pre)
        except:
            print(f"exec stock_price error: stock={symbol}, type=pre")
        else:
            print(f"exec stock_price ok: stock={symbol}, type=pre")
    else:
        print(f"exec stock_price skip: stock={symbol}, type=pre")

    thisyear_start = f"{thisyear}0101"
    cur_date = datetime.datetime.now().strftime("%Y%m%d")   # YYYYMMDD

    if not os.path.exists(file_cur):
        try:
            df_stock_cur = ak.stock_zh_a_hist(symbol=p_symbol, period="daily", start_date=thisyear_start, end_date=cur_date, adjust="")
            df_stock_cur_qfq = ak.stock_zh_a_hist(symbol=p_symbol, period="daily", start_date=thisyear_start, end_date=cur_date, adjust="qfq")
            copy_qfq_data(df_stock_cur_qfq, df_stock_cur)
            df_stock_cur.to_csv(file_cur)
        except:
            print(f"exec stock_price error: stock={symbol}, type=cur")
        else:
            print(f"exec stock_price ok: stock={symbol}, type=cur")
    else:
        print(f"exec stock_price skip: stock={symbol}, type=cur")


# 把前复权的数据拷贝到没有前复权的数据中
# dfqfq: 前复权的股票价格
def copy_qfq_data(dfqfq, df):
    columns=['开盘','收盘','最高','最低']

    for column in columns:
        df[f'{column}_qfq'] = dfqfq[column]

# 获取所有 A股股票Id
# 返回: [600332, 2278...] 格式
def all_a_stocks():
    full_stock_file = f'{DATA_PATH}/a/jibenmian/zcfz_20220930.csv'    # 注意！！只会拉取这个文件中的 股票列表 中的股票。所以一般选取距拉取时间半年前的 资产负债表 的数据
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


# jibenmian_all_fast('xjll', 2022, 2023, ["{year}1231"])
# jibenmian_all_fast('zcfz', 2022, 2023, ["{year}1231"])
# jibenmian_all_fast('lrb', 2022, 2023, ["{year}1231"])
# download_etf()