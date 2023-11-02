## 数据准备
### 下载 所有股票的基本面数据
process.py
```python
    编辑&运行 download_a_jibenmian()
```
#### 基本面数据说明
- 所有基本面数据是每个季度一个文件， 放在data/a/jibenmian 目录
- xjll_YYYYMMDD.csv 现金流量表
- lrb_YYYYMMDD.csv 利润表
- zcfz_YYYYMMDD.csv 资产负债表




### 处理 基本面数据，计算每季的增长数据
process.py
```python
    编辑并运行 calc_a_growth()
    导出的csv是一个 所有股票 多季度 基本数据 (合并data/a/jibenmian/ 下的所有指定时间范围内的文件)
    导出时间是从 指定的时间 开始到 上个季度(导出时间的90日前) 的数据
    # ['iDATE', 'preYearIncome', 'SeasonIncome', 'SeasonIncomeGrowth', 'preYearProfit', 'SeasonProfit', 'SeasonProfitGrowth']
```
| 增加的数据 | 内容 |
| --- | --- |
| preYearIncome | 前一年当季收入 |
| SeasonIncome | 当季收入 |
| SeasonIncomeGrowth | 当季收入增长 |
| preYearProfit | 前一年当季利润 |
| SeasonProfit | 当季利润 |
| SeasonProfitGrowth | 当季利润增长 |




### 下载 所有股票的日线数据
每年 执行一次 process.py 中 download_a_price_yearly() 函数, 这样可以更新之前的数据
如果需要更新最新的数据，执行 process.py 中的 download_a_price_cur() 函数
- price_XXXXXX_pre.csv 是指今年(不包括今年)所有年份的数据
- price_XXXXXX_cur.csv 是今年的数据
- 数据下载说明
    - download_a_price_yearly() 是下载所有数据
    - download_a_price_cur() 仅仅下载今年的数据
    - 所以一年内如果调用过 download_a_price_yearly(), 只是要更新最新数据，就调用download_a_price_cur()。如果今年没有调用过，那就应该调用 download_a_price_yearly()

## 数据使用
| 文件 | 函数 | 内容 |
| --- | --- | --- |
| stockdata.py | get_stock_price() | 读取一个股票的日线数据 | 
| SeasonIncome | 当季收入 |

