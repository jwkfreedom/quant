"""    
    get_seasondate  获得 季报日期列表
    load_jibenmian  读取并合并 data/a/jibenmian 目录下多个季度的数据
    rm_broken_stocks 整理load_jibenmian 返回基本面数据，删除数据不全的股票
    growth_score 计算每个季度单独的数据
    
    get_stock_price 读取一个股票的日线数据
"""
import pandas as pd
import datetime as dt
import backtrader as bt
from config import DATA_DIR

from datetime import datetime
#  获得 季报日期列表，
#   input: start_date(格式: '2010-01-04')
#           beforedays: 截止日期为多少天前
#   return: 格式: ['20100331', '20100630'....., 最后季报]

def get_seasondate(start_date, beforedays=90): 
    seasonstrs = ['0331', '0630', '0930', '1231']
    startStrs = start_date.split('-')
    start_year = int(startStrs[0])
    start_date = int(startStrs[0] + startStrs[1] + startStrs[2])

    # Get date 3 months ago
    end_date = dt.date.today() - dt.timedelta(beforedays)
    end_year = int(end_date.strftime('%Y'))
    end_season = int(end_date.strftime('%Y%m%d'))

    seasons = []
    for year in range(start_year, end_year + 1):
        for seasonstr in seasonstrs:
            v = int(str(year) + seasonstr)
            # print(v)
            if(v > start_date and v <= end_season):
                seasons.append(str(v))
    
    return seasons



"""
    读取并合并 data/a/jibenmian 目录下多个季度的数据
        season_start : 起始季度  格式: '2010-03-01'
        beforedays:   截至到多少天前  缺省为90天，即上季度
        
"""
def load_jibenmian(season_start, beforedays=90):
    seasons = get_seasondate(season_start, beforedays)
    src_dir = f'{DATA_DIR}/a/jibenmian'


    dfs = []
    for season in seasons:
        print(f"season={season}")
        df_zcfz = pd.read_csv(f'{src_dir}/zcfz_{season}.csv')
        df_lrb = pd.read_csv(f'{src_dir}/lrb_{season}.csv')
        df_xjll = pd.read_csv(f'{src_dir}/xjll_{season}.csv')

        df = pd.merge(df_zcfz, df_lrb, on='股票代码')
        df = pd.merge(df_xjll, df, on='股票代码')
        df['DATE'] = season
        df['iDATE'] = int(season)
        dfs.append(df)

    dftotal = pd.concat(dfs, ignore_index=False)
    return dftotal
    

"""
    整理load_jibenmian 返回基本面数据，删除数据不全的股票
"""
def rm_broken_stocks(df):
    # df['DATE_NUM'] = pd.to_numeric(df['DATE'], errors='coerce')
    # Then, find the maximum value in the column
    seasonSet = set(df['iDATE'].unique())

    set_list=[]
    for season in seasonSet:
        df_season = df.loc[df['iDATE'] == season]
        stock_set = set(df_season['股票代码'].unique())
        set_list.append(stock_set)
    
    # 找出所有季报的stock的交集，即在这些季报中都存在stock
    common_elements = set.intersection(*set_list)
    df_result = df[df['股票代码'].isin(common_elements)]

    return df_result

"""
    获得去年同一个财季的季报id，季报id是一个8为整数，比如20120331
"""
def pre_year_season(year_season):
    year = int(year_season / 10000)
    season = year_season % 10000

    pre_season_map = {331: 1231, 630: 331, 930: 630, 1231: 930}
    
    pre_season = pre_season_map[season]
    if pre_season > season:
        return (year - 1) * 10000 + pre_season
    return year * 10000 + pre_season


# date格式: '2012-12-21'
# 获得 季报的iDATE 20120930
def get_season_iDATE(date):
    iDATE = int(date.replace('-', ''))
    year = int(iDATE / 10000)
    monthday = iDATE % 10000
    if monthday < 331:
        iDATE = (year - 1) * 10000 + 1231
    elif monthday < 630: 
        iDATE = year * 10000 + 331
    elif monthday < 930:
        iDATE = year * 10000 + 630
    else:
        iDATE = year * 10000 + 930
    
    return iDATE

def growth_score(df):
    stockIdSet = set(df['股票代码'].unique())
    print(f"共有 {len(stockIdSet)} 个股票数据")

    seasonSet = set(df['iDATE'].unique())
    seasons = sorted(list(seasonSet))

    if seasons[0] % 10000 != 331:
        print(f"first season should be XXXX0331. Now is {seasons[0]}")
        return
    
    for stockId in stockIdSet:
        df = calc_season_growth(df, stockId, seasons, '营业总收入')

    for stockId in stockIdSet:
        df = calc_season_growth(df, stockId, seasons, '净利润')


    return df


#
# 计算一个股票的所有季度的单季数据
# type: "营业总收入" or "净利润"
#
def calc_season_growth(df, stockId, seasons, type): 
    typeTongbi = type + "同比"  # 营业总收入 or 净利润同比
    nameMap = {"营业总收入": ['preYearIncome', 'SeasonIncome', 'SeasonIncomeGrowth'], "净利润":['preYearProfit', 'SeasonProfit', 'SeasonProfitGrowth']}
    preYear = nameMap[type][0]
    seasonName = nameMap[type][1]
    seasonGrowthName = nameMap[type][2]

    for season in seasons:
        totalGrowth = df.loc[(df['股票代码'] == stockId) & (df['iDATE']== season), typeTongbi]
        preYearValue =  df.loc[(df['股票代码'] == stockId) & (df['iDATE']== season), type] / (1 + totalGrowth / 100.0)
        income = df.loc[(df['股票代码'] == stockId) & (df['iDATE']== season), type]
        df.loc[(df['股票代码'] == stockId) & (df['iDATE']== season), preYear] = preYearValue

        if season % 10000 == 331:   # 每年第一季度，单季增长不用特殊计算
            df.loc[(df['股票代码'] == stockId) & (df['iDATE']== season), seasonGrowthName] = totalGrowth
            df.loc[(df['股票代码'] == stockId) & (df['iDATE']== season), seasonName] = income
        else:
            income = df.loc[(df['股票代码'] == stockId) & (df['iDATE']== season), type].item()
            preTotalIncome = df.loc[(df['股票代码'] == stockId) & (df['iDATE']== pre_year_season(season)), type].item()
            seasonIncome = income - preTotalIncome
            df.loc[(df['股票代码'] == stockId) & (df['iDATE']== season), seasonName] = seasonIncome
            preYearSeasonIncome = preYearValue - df.loc[(df['股票代码'] == stockId) & (df['iDATE']== pre_year_season(season)), preYear].item()
            growth = (seasonIncome / preYearSeasonIncome - 1) * 100
            df.loc[(df['股票代码'] == stockId) & (df['iDATE']== season), seasonGrowthName] = growth
    return df

#
#  读取一个股票的日线数据
#     
def get_stock_price(symbol):
    file_src=f"{DATA_DIR}/a/stock/price/price_{symbol}_"

    df_price_pre = pd.read_csv(file_src + "pre.csv")
    df_price_cur = pd.read_csv(file_src + "cur.csv")
    df_price = pd.concat([df_price_pre, df_price_cur])
    # df_price.index = pd.DatetimeIndex(df_price['日期'])

    #,,,,,,,,,,,开盘_qfq,收盘_qfq,最高_qfq,最低_qfq
    columns = {"开盘": "open" , "日期": "date", "收盘": "close", "最高": "high", "最低": "low", "开盘_qfq": "open_qfq","收盘_qfq":"close_qfq","最高_qfq": "high_qfq","最低_qfq":"low_qfq",
               "成交量": "volumn", "成交额": "turnover", "振幅":"amp", "涨跌幅": "percent_change", "涨跌额": "value_change", "换手率":"turnover_rate"}

    df_price.rename(columns=columns, inplace=True)


    price_columns = ['open', 'close', 'high', 'low']
    for price_column in price_columns:
        df_price[f"{price_column}_org"] = df_price[price_column]
    
    for price_column in price_columns:
        df_price[price_column] = df_price[f"{price_column}_qfq"]


    df_price['DATE'] = df_price['date'].str.replace('-', '')
    df_price['iDATE'] = pd.to_numeric(df_price['DATE'], errors='coerce')
    df_price = df_price.drop('DATE', axis=1)
    return df_price


#------------------------
# df = load_jibenmian('2021-01-01')
# df = rm_broken_stocks(df)
# df = growth_score(df)
# df.to_csv('data/temp.csv',index=False, encoding='utf_8_sig')
#print(df)

# print(pre_season(20110630))

#df = get_stock_price('000001')
#print(df)


#
# 计算financial数据中的TTM值
# df = calc_ttm(df, '摊薄每股收益(元)', 'profitTTM')
# df = calc_ttm(df, '每股净资产_调整后(元)', 'netassetTTM')
#
def calc_ttm(df, NameProfit, TTMName):
    df[NameProfit] = pd.to_numeric(df[NameProfit], errors='coerce')
    # Use dropna method to drop rows with non-numeric values in the specified column
    df.dropna(subset=[NameProfit], inplace=True)

    if not 'iDATE' in df.columns:
        df['DATE'] = df['日期'].str.replace('-', '')
        df['iDATE'] = pd.to_numeric(df['DATE'], errors='coerce')
        df.drop(df[df['iDATE'] < 20110101].index, inplace=True)

    seasonSet = set(df['iDATE'].unique())
    seasons = sorted(list(seasonSet))

    for season in seasons:
        preyearSeason = df.loc[df['iDATE']==season, 'iDATE'].item() - 10000
        preyear = int(preyearSeason / 10000)
        preyearEnd = preyear * 10000 + 1231
        
        seasonProfit = df.loc[df['iDATE']==season, NameProfit].item()
        if (not df.loc[df['iDATE']==preyearSeason].empty) and (not df.loc[df['iDATE']==preyearEnd].empty):
            preyearSeasonProfit = df.loc[df['iDATE']==preyearSeason, NameProfit].item()
            preyearEndProfit = df.loc[df['iDATE']==preyearEnd, NameProfit].item()
            ttmValue = preyearEndProfit - preyearSeasonProfit + seasonProfit
            df.loc[df['iDATE']==season, TTMName] = ttmValue
        else:
            df.loc[df['iDATE']==season, TTMName] = '--'

    return df


#
# financial_report_XXXX 数据完善
# 每股净资产_调整后(元) 数据有缺陷，需要用 每股净资产_调整前(元) 来计算调整
#
def fix_financial_data(df):
    df['DATE'] = df['日期'].str.replace('-', '')
    df['iDATE'] = pd.to_numeric(df['DATE'], errors='coerce')

    seasonSet = set(df['iDATE'].unique())
    seasons = sorted(list(seasonSet))

    diff = 0

    NAME_PREFIX = '每股净资产_调整前(元)'
    NAME_POSTFIX = '每股净资产_调整后(元)'

    df[NAME_PREFIX] = pd.to_numeric(df[NAME_PREFIX], errors='coerce')
    df[NAME_POSTFIX] = pd.to_numeric(df[NAME_POSTFIX], errors='coerce')

    for season in seasons:
        seasonPreFix = df.loc[df['iDATE']==season, NAME_PREFIX]
        seasonPostFix = df.loc[df['iDATE']==season, NAME_POSTFIX]
        if pd.isna(seasonPostFix.item()):
            value = seasonPreFix.item() - diff
            df.loc[df['iDATE']==season, NAME_POSTFIX] = value
            print(f"fix season={season}, value={value}")
        else: 
            diff = seasonPreFix.item() - seasonPostFix.item()

    df.drop(df[df['iDATE'] < 20110101].index, inplace=True)
    return

def calc_pepb_by_season(group):
    # print(group.dtypes)
    if group.loc[group.index[0], 'profitTTM'].item() != 0:
        group.loc[group.index[0], 'PE'] = group.loc[group.index[0], 'close_org'] / group.loc[group.index[0], 'profitTTM']
        group.loc[group.index[1:], 'PE'] = (group.loc[group.index[1:], 'close_org'] / group.loc[group.index[0], 'close_org']) * group.loc[group.index[0], 'PE']
    else:
        group.loc[:, 'PE'] = 0.0

    if group.loc[group.index[0], 'netassetTTM'].item() != 0:
        group.loc[group.index[0], 'PB'] = group.loc[group.index[0], 'close_org'] / group.loc[group.index[0], 'netassetTTM']
        group.loc[group.index[1:], 'PB'] = (group.loc[group.index[1:], 'close_org'] / group.loc[group.index[0], 'close_org']) * group.loc[group.index[0], 'PB']
    else:
        group.loc[:, 'PB'] = 0.0
 
    return group




def update_price_pe(df_price, df_financial):
    merged_df = pd.merge(df_price, df_financial, left_on='season', right_on='iDATE', how='left')
    merged_df.fillna({'profitTTM': 0}, inplace=True)
    merged_df.fillna({'netassetTTM': 0}, inplace=True)

    df_price['profitTTM'] = merged_df['profitTTM']
    df_price['PE'] = 0.0

    df_price['netassetTTM'] = merged_df['netassetTTM']
    df_price['PB'] = 0.0
    df_price = df_price.groupby('season', group_keys=False).apply(calc_pepb_by_season)


    return df_price


#
# 读取一个股票的完整数据
#
def get_full_price(symbol):  
    # step 1. 读取financial 数据，需要用到其中的 每股利润 和 每股净资产，用来计算pe和pb
    df_financial = pd.read_csv(f'{DATA_DIR}/a/stock/financial/financial_report_{symbol}.csv')

    fix_financial_data(df_financial)
    df_financial = calc_ttm(df_financial, '摊薄每股收益(元)', 'profitTTM')
    df_financial = calc_ttm(df_financial, '每股净资产_调整后(元)', 'netassetTTM')

    df_financial.drop(df_financial[df_financial['profitTTM'] == '--'].index, inplace=True)
    # print(df_financial.loc[df_financial['iDATE'] == 20120331, '每股净资产_调整后(元)'])  
    
    # print(df_financial.loc[df_financial['netassetTTM'] == '--'])


    # step 2. 读取price 数据
    df_price = get_stock_price(symbol)

    # step 2.1 需要按照季度处理数据
    df_price['season'] = df_price['date'].apply(get_season_iDATE)
    df_price.reset_index(drop=True, inplace=True)

    # step 3. 更新pepb
    df_price = update_price_pe(df_price, df_financial)

    # step 4. 设置date为index，方便画图
    df_price['date'] = pd.to_datetime(df_price['date'])  # 确保日期是 datetime 类型
    df_price.set_index('date', inplace=True)  # 将日期设为索引    
    return df_price

#-----------------------------------------------
"""
symbol = '000002'
df_price = get_full_price(symbol)
print(df_price[df_price['season'] == 20210630])
"""
