import backtrader as bt
import pandas as pd
import os

class MyStrategy(bt.Strategy):
    
    def __init__(self):
        self.stocks = self.datas[1:]
        self.buy_price = {}
        self.buy_size = 5000
        self.cash = 10000
        self.score = {}
        self.order = {}
        self.dataclose = {}
        self.buy_signal = {}
        self.sell_signal = {}
        self.buy_count = 0
        self.sell_count = 0
        
        # calculate score for each stock
        for stock in self.stocks:
            df = pd.read_csv(f"data/a/etf/price/{stock._name}.csv")
            df['pct_change'] = df['close'].pct_change()
            df['group'] = pd.qcut(df['pct_change'], 10, labels=False)
            df['score'] = pd.qcut(df['group'], 10, labels=False, duplicates='drop')
            self.score[stock] = df['score'].iloc[-5:].mean()
            self.dataclose[stock] = df['close']
        
    def next(self):
        for stock in self.stocks:
            if self.score[stock] > 7 and stock not in self.buy_signal:
                self.buy_signal[stock] = True
            if self.score[stock] < 3 and stock not in self.sell_signal:
                self.sell_signal[stock] = True
        
        for stock in self.buy_signal:
            if self.cash > self.buy_size and stock not in self.buy_price:
                self.order[stock] = self.buy(size=self.buy_size)
                self.buy_price[stock] = self.dataclose[stock][0]
                self.cash -= self.buy_size
                self.buy_count += 1
        
        for stock in self.sell_signal:
            if stock in self.buy_price:
                self.order[stock] = self.sell(size=self.buy_size)
                self.cash += self.buy_size
                self.sell_count += 1
                del self.buy_price[stock]
        
        self.buy_signal = {}
        self.sell_signal = {}
        
    def stop(self):
        print('Buy count:', self.buy_count)
        print('Sell count:', self.sell_count)
        print('Final value:', self.cash + sum([self.buy_price[stock] * self.buy_size for stock in self.buy_price]))
        
cerebro = bt.Cerebro()

# add data
# add data
etf_list = ["515050",	"512480",	"159867",	"512980",	"159992",	"515400",	"159611",	"159997",	"512200",	"515210",	"159638",	"515790",	"512670",	"510880",	"159870",	"518880",	"159937",	"518800",	"516950",	"159998",	"159996",	"159745",	"510230",	"512690",	"512660",	"588200",	"588100",	"515000",	"516050",	"159840",	"159766",	"515220",	"159825",	"516110",	"512000",	"159819",	"515230",	"515710",	"515170",	"560800",	"561190",	"159790",	"516150",	"159928",	"159995",	"516160",	"515030",	"159939",	"512330",	"159959",	"159865",	"512170",	"159883",	"512010",	"512800",	"159736",	"159869",	"512400",	"516510",	"515250",	"513050",	"560080"]
for symbol in etf_list:
    data = bt.feeds.GenericCSVData(
        dataname=f"data/a/etf/price/etf_{symbol}.csv",
        dtformat='%Y-%m-%d',
        openinterest=-1,
        nullvalue=0.0,
        plot=False
    )
    cerebro.adddata(data)

# add strategy
cerebro.addstrategy(MyStrategy)

# set initial cash
cerebro.broker.setcash(10000)

# set commission
cerebro.broker.setcommission(commission=0.001)

# run backtest
cerebro.run()


