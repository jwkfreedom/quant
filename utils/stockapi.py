import requests
import json

#-------------------------------------------------
#   SNOWBALL
#-------------------------------------------------
SNOWBALL_STOCKURL = 'https://stock.xueqiu.com/v5/stock/realtime/quotec.json?symbol={}'
SNOWBALL_headers = {
    'Accept': '*/*',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
    'Connection': 'keep-alive',
    'host': 'stock.xueqiu.com',
    'Referer': 'https://stock.xueqiu.com/',
    'User-agent': 'Mozilla/5.0 (Windows NT 10.0; WOW 64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36 QIHU 360SE'
}

def stock_info(symbol):
    url = SNOWBALL_STOCKURL.format(symbol)
    rt = requests.get(url, headers=SNOWBALL_headers)
    rt_json= json.loads(rt.text)
    return rt_json


#-------------------------------------------------
#   IEX 
#-------------------------------------------------
api_key ="pk_63e59b9f85d84ae68e140a2cdae738af"  # 


# Define the API endpoint and parameters

def iex_stock(symbol):
    # endpoint = "https://api.iex.cloud/v1/data/CORE/HISTORICAL_PRICES/{}?token={}".format(symbol, api_key)
    # endpoint = "https://sandbox.iex.cloud/v1/data/CORE/HISTORICAL_PRICES/{}?token={}".format(symbol, api_key)
    endpoint = "https://sandbox.iex.cloud/stable/stock/{}/quote?token={}".format(symbol, api_key)

    # Make the API request
    response = requests.get(endpoint)

    # Check if the request was successful
    if response.status_code == 200:
        # Extract the JSON data from the response
        json_data = response.json()

        return json_data
    else:
        # Handle the error
        print(f"Error: {response.status_code}")
        return {'err': response.status_code}

# types: quote or stats
def iex_stocks(symbols, types):
    endpoint="https://sandbox.iex.cloud/stable/stock/market/batch?symbols={}&types={}&token={}".format(symbols, types, api_key)
        # Make the API request
    response = requests.get(endpoint)

    # Check if the request was successful
    if response.status_code == 200:
        # Extract the JSON data from the response
        json_data = response.json()

        return json_data
    else:
        # Handle the error
        print(f"Error: {response.status_code}")
        return {'err': response.status_code}
    
print(iex_stocks('AAPL,MMM', 'stats'))
#-------------------------------------------------
#   EASTMONEY
#-------------------------------------------------
def eastmoney_stock():
    url = 'http://18.push2.eastmoney.com/api/qt/clist/get'
    param = {"pn": "1","pz": "3000", "po": "1", "np": "1","ut": "bd1d9ddb04089700cf9c27f6f7426281",
"fltt": "2",
"invt": "2",
"fid": "f3",
"fs": "m:1+t:2,m:1+t:23",
"fields": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f26,f38,f39,f22,f11,f62,f128,f136,f115,f152,f297",
"invt": "2",
"invt": "2",
"invt": "2"}
    
    response=requests.get(url, params=param)

        # Check if the request was successful
    if response.status_code == 200:
        # Extract the JSON data from the response
        json_data = response.json()

        return json_data
    else:
        # Handle the error
        print(f"Error: {response.status_code}")
        return {'err': response.status_code}


# print(eastmoney_stock())
#-------------------------------------------------
#   CSV数据保存
#-------------------------------------------------