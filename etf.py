import pandas as pd
import akshare as ak

start_date = "20180101"
end_date = "20230201"

etf_list = ["515050",	"512480",	"159867",	"512980",	"159992",	"515400",	"159611",	"159997",	"512200",	"515210",	"159638",	"515790",	"512670",	"510880",	"159870",	"518880",	"159937",	"518800",	"516950",	"159998",	"159996",	"159745",	"510230",	"512690",	"512660",	"588200",	"588100",	"515000",	"516050",	"159840",	"159766",	"515220",	"159825",	"516110",	"512000",	"159819",	"515230",	"515710",	"515170",	"560800",	"561190",	"159790",	"516150",	"159928",	"159995",	"516160",	"515030",	"159939",	"512330",	"159959",	"159865",	"512170",	"159883",	"512010",	"562860",	"512800",	"159736",	"159869",	"512400",	"516510",	"515250",	"513050",	"560080"]

def download_daily():
    dfs = []
    for symbol in etf_list:
        df = ak.fund_etf_hist_em(symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
        df.to_csv(f"data/a/etf/price/etf_{symbol}.csv",index=False, encoding='utf_8_sig')

        df['name'] = symbol
        dfs.append(df)
        print(f"download etf_{symbol} ok")
    dftotal = pd.concat(dfs, ignore_index=False)
    dftotal.to_csv('data/a/etf/etf_all.csv', index=False, encoding='utf_8_sig')

download_daily()




