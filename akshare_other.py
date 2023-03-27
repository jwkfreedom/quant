import akshare as ak

def download():
    """
    df = ak.index_stock_info()
    df.to_csv("data/etf/a_etf_list.csv")

    df = ak.index_stock_cons(symbol="000300")
    df.to_csv("data/etf/hushen300.csv")
    """
    df = ak.index_stock_cons(symbol="000905")
    df.to_csv("data/etf/zhongzheng500.csv")

download()