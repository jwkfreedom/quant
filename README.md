# quant

## netres
网络资源


## study
学习记录


## strategy
策略

## utils
基本功能函数

### download.py
    - jibenmian_all_fast: 下载基本面数据（业绩快报），支持 资产负债表，利润表，现金流量表
    - jibenmian_all: 下载所有A股股票的基本面详细数据，包括 资产负债表， 利润表， 现金流量表
    - stock_jibenmian: 单一股票的基本面详细数据
    - stock_price_all: 下载所有股票日线数据
    - stock_price: 下载单一股票的日线数据

### stockdata.py
    - get_full_price: 读取一个股票的完整价格!!!
    - get_seasondate  获得 季报日期列表
    - load_jibenmian  读取并合并 data/a/jibenmian 目录下多个季度的数据
        - 数据包括:  '序号', '股票代码', '股票简称', '净现金流-净现金流', '净现金流-同比增长',
       '经营性现金流-现金流量净额', '经营性现金流-净现金流占比', '投资性现金流-现金流量净额', '投资性现金流-净现金流占比',
       '融资性现金流-现金流量净额', '融资性现金流-净现金流占比', '公告日期', 'Unnamed: 0_x', '序号_x',
       '股票简称_x', '资产-货币资金', '资产-应收账款', '资产-存货', '资产-总资产', '资产-总资产同比',
       '负债-应付账款', '负债-预收账款', '负债-总负债', '负债-总负债同比', '资产负债率', '股东权益合计', '公告日期_x',
       'Unnamed: 0_y', '序号_y', '股票简称_y', '净利润', '净利润同比', '营业总收入', '营业总收入同比',
       '营业总支出-营业支出', '营业总支出-销售费用', '营业总支出-管理费用', '营业总支出-财务费用', '营业总支出-营业总支出',
       '营业利润', '利润总额', '公告日期_y', 'DATE', 'iDATE'
    - rm_broken_stocks 整理load_jibenmian 返回基本面数据，删除数据不全的股票
    - growth_score 计算每个季度单独的数据
    - get_stock_price(symbol) 读取一个股票的日线数据 symbol='000001', 返回: dataframe


## 数据下载
### process.py
    - download_a_jibenmian: 下载A股基本面数据
    - calc_a_growth: 计算基本面增长数据，导出到指定文件

## 数据分析 analyse 目录
    - ana_jibemmian.py  基本面数据的使用分析