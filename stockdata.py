"""    
    get_seasondate  获得 季报日期列表
    load_jibenmian  读取并合并 data/a/jibenmian 目录下多个季度的数据
    rm_broken_stocks 整理load_jibenmian 返回基本面数据，删除数据不全的股票
"""
import pandas as pd
import datetime as dt


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
    src_dir = 'data/a/jibenmian'

    dfs = []
    for season in seasons:
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
    max_val = df['iDATE'].max()
    min_val = df['iDATE'].min()

    season_start = str(min_val)
    season_end = str(max_val)

    df_end = df.loc[df['DATE'] == season_end]
    set_end = set(df_end['股票代码'].unique())

    df_start = df.loc[df['DATE'] == season_start]
    set_start = set(df_start['股票代码'].unique())

    # Find values that are in df1 but not in df2
    diff1 = set_start - set_end
    diff2 = set_end - set_start

    diff = diff1 | diff2

    df_diff = df['股票代码'].isin(diff)
    df_result = df[~df_diff]
    return df_result




def growth_score(df):
    stockIdSet = set(df['股票代码'].unique())
    seasonSet = set(df['iDATE'].unique())

    seasons = sorted_array = sorted(list(seasonSet))

    dfgrow = pd.DataFrame()
    dfgrow['股票代码'] = list(stockIdSet)

    for stockId in stockIdSet:
        score = 0
        for season in seasons:
            score += df.loc[df'']
        

    return








#------------------------
df = load_jibenmian('2021-01-01')
df = rm_broken_stocks(df)
df = growth_score(df)
print(df)