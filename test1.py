import backtrader as bt
import stockdata as sd
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

class MyStrategy(bt.Strategy):
    
    def __init__(self):
        self.dataclose = self.datas[0].close
        self.dataopen = self.datas[0].open
        self.datavolume = self.datas[0].volume
        
        self.order = None
        self.buyprice = None
        self.buycomm = None
        
        self.avg_volume = bt.indicators.SMA(self.datavolume, period=20)
        
    def next(self):
        if self.order:
            return
            
        if self.datavolume[0] < 0.4 * self.avg_volume[0]:
            self.order = self.buy()
                
        if self.order:
            return
            
        if self.buyprice is not None and (self.dataclose[0] < self.buyprice * 0.95 or self.dataclose[0] > self.buyprice * 1.3):
            self.order = self.sell()
            
    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
            else:
                self.log(f'SELL EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
                
            self.order = None
            
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            # self.log('Order Canceled/Margin/Rejected')
            print('Order Canceled/Margin/Rejected')
            
    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        
        self.log(f'OPERATION PROFIT, GROSS {trade.pnl:.2f}, NET {trade.pnlcomm:.2f}')
    def log(slef, str):
        print(str)
        
cerebro = bt.Cerebro()

#bt.feeds.YahooFinanceData(dataname='AAPL', fromdate=datetime(2019, 1, 1), todate=datetime(2021, 1, 1))
df = sd.get_stock_price('000002')
df = df.sort_values('date')
df['date'] = pd.to_datetime(df['date'], format='%Y-%m-%d')
data = bt.feeds.PandasData(dataname=df, datetime='date', open='open', high='high', low='low', close='close', volume='volumn', fromdate=datetime(2022, 1,1))
cerebro.adddata(data)
cerebro.addstrategy(MyStrategy)
cerebro.run()

plt.rcParams['figure.figsize'] = [15, 12]
plt.rcParams.update({'font.size': 12}) 
cerebro.plot(iplot=False)