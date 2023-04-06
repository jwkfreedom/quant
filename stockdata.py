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
    """
    max_val = df['iDATE'].max()
    min_val = df['iDATE'].min()

    season_start = str(min_val)
    season_end = str(max_val)
    print(f"rm_broken_stocks  {season_start} => {season_end}")

    df_end = df.loc[df['DATE'] == season_end]
    set_end = set(df_end['股票代码'].unique())

    df_start = df.loc[df['DATE'] == season_start]
    set_start = set(df_start['股票代码'].unique())

    # Find values that are in df1 but not in df2
    diff1 = set_start - set_end
    print(set_start)
    diff2 = set_end - set_start

    diff = diff1 | diff2

    df_diff = df['股票代码'].isin(diff)
    df_result = df[~df_diff]
    """
    seasonSet = set(df['iDATE'].unique())

    set_list=[]
    for season in seasonSet:
        df_season = df.loc[df['iDATE'] == season]
        stock_set = set(df_season['股票代码'].unique())
        set_list.append(stock_set)
    
    # 找出所有季报的stock的交集，即在这些季报中都存在stock
    common_elements = set.intersection(*set_list)
    print(common_elements)
    df_result = df[df['股票代码'].isin(common_elements)]

    return df_result




def growth_score(df):
    stockIdSet = set(df['股票代码'].unique())
    seasonSet = set(df['iDATE'].unique())

    # 成长分数上下限为0~100
    df['营业总收入同比'] = df['营业总收入同比'].clip(lower=0.0, upper=100.0)

    dfgrow = df.groupby('股票代码')['营业总收入同比'].mean()
    
    # 经营规模
    dfscale = df.groupby('股票代码')['营业总收入'].max()
    

    #seasons = sorted_array = sorted(list(seasonSet))
    #dfgrow = pd.DataFrame()
    #dfgrow['股票代码'] = list(stockIdSet)

    #dfgrow['股票代码', 'score'] = df[]
    """
    for stockId in stockIdSet:
        score = 0
        for season in seasons:
            season_score = df.loc[(df['股票代码'] == stockId) & (df['iDATE']== season), '营业总收入同比']
            season_score = max(0, season_score)
            season_score = min(100, season_score)

            score += season_score
        
        print(f"stockId={stockId}, score={score}")
    """
            

    return dfscale

#df.loc[df['other_col'] == 'value1', 'col1'] *= 0.2
#df.loc[df['other_col'] == 'value2', 'col1'] *= 0.3









#------------------------
df = load_jibenmian('2021-01-01')
df = rm_broken_stocks(df)
df = growth_score(df)
print(df)