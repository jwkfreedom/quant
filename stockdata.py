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
    print(end_date)
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


print(get_seasondate('2010-01-04'))

    
    



