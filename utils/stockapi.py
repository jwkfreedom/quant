import requests
import json

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
api_key ="pk_63e59b9f85d84ae68e140a2cdae738af"  # "sk_d3b9987f52354e9e9d9b7a0a948ca548"


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

        # Print the company name and latest price
        print(json_data)
    else:
        # Handle the error
        print(f"Error: {response.status_code}")
