## 数据准备
#### 下载 所有股票的基本面数据
process.py
```python
    编辑&运行 download_a_jibenmian()
```

#### 处理 基本面数据，计算每季的增长数据
process.py
```python
    编辑并运行 calc_a_growth()
    导出的csv是一个所有股票多季度基本数据 

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

#### 下载 所有股票的日线数据
每年 执行一次 process.py 中 download_a_price_yearly() 函数, 这样可以更新之前的数据
如果需要更新最新的数据，执行 process.py 中的 download_a_price_cur() 函数

## 数据使用
| 文件 | 函数 | 内容 |
| --- | --- | --- |
| stockdata.py | get_stock_price() | 读取一个股票的日线数据 | 
| SeasonIncome | 当季收入 |

