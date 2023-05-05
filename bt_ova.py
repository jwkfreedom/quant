# 导入必要的库
import backtrader as bt
import pandas as pd



class MyOBV(bt.Indicator):
    lines = ('obv',)
    params = (('period', 14),)

    def __init__(self):
        self.addminperiod(self.params.period)

    def next(self):
        if self.data.close[0] > self.data.close[-1]:
            self.lines.obv[0] = self.lines.obv[-1] + self.data.volume[0]
        elif self.data.close[0] < self.data.close[-1]:
            self.lines.obv[0] = self.lines.obv[-1] - self.data.volume[0]
        else:
            self.lines.obv[0] = self.lines.obv[-1]

# 定义交易策略类
class MAOBVStrategy(bt.Strategy):

    # 设置参数
    params = (
        ('ma_period', 20), # 均线周期
        ('obv_period', 1), # OBV周期
    )

    # 初始化函数
    def __init__(self):
        # 计算均线和OBV指标
        self.ma = bt.indicators.SMA(self.data.close, period=self.p.ma_period)
        self.obv = MyOBV(self.data, period=14)

        # 设置交易信号
        self.buy_signal = bt.And(self.data.close > self.ma, self.obv > 0)
        self.sell_signal = bt.And(self.data.close < self.ma, self.obv < 0)

    # 下单逻辑函数
    def next(self):
        # 如果没有持仓且有买入信号，买入
        if not self.position and self.buy_signal:
            self.buy()
        # 如果有持仓且有卖出信号，卖出
        elif self.position and self.sell_signal:
            self.sell()

# 创建回测引擎对象
cerebro = bt.Cerebro()

# 加载数据
data = pd.read_csv('data/a/etf/price/etf_512480.csv', index_col=0, parse_dates=True)
datafeed = bt.feeds.PandasData(dataname=data)
cerebro.adddata(datafeed)

# 添加策略
cerebro.addstrategy(MAOBVStrategy)

# 设置初始资金和佣金
cerebro.broker.setcash(100000.0)
cerebro.broker.setcommission(commission=0.001)

# 运行回测
results = cerebro.run()

# 打印最终资金和收益率
print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
print('Return: %.2f%%' % ((cerebro.broker.getvalue() / 100000.0 - 1) * 100))

# 绘制回测结果图
#cerebro.plot()
