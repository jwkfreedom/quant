import akshare as ak

def download():
    """
    df = ak.index_stock_info()
    df.to_csv("data/a/etf/a_etf_list.csv",index=False, encoding='utf_8_sig')
    """
    """
    df = ak.index_stock_cons(symbol="000300")
    df.to_csv("data/etf/hushen300.csv")
    """
    """
    df = ak.index_stock_cons(symbol="000905")
    df.to_csv("data/etf/zhongzheng500.csv")
    """
    """
    # 行业etf 列表
    df = ak.fund_etf_spot_em()
    df = df.loc[df['总市值'] > 500000000]
    df['总市值'] = df['总市值'] // 100000000
    df = df[~df['名称'].str.contains('50|300|500|1000')]
    df.to_csv("data/etf/hangye_etf.csv",index=False, encoding='utf_8_sig')
    """


    
download()