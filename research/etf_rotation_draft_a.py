import backtrader as bt

etf_list = ["515050",	"512480",	"159867",	"512980",	"159992",	"515400",	"159611",	"159997",	"512200",	"515210",	"159638",	"515790",	"512670",	"510880",	"159870",	"518880",	"159937",	"518800",	"516950",	"159998",	"159996",	"159745",	"510230",	"512690",	"512660",	"588200",	"588100",	"515000",	"516050",	"159840",	"159766",	"515220",	"159825",	"516110",	"512000",	"159819",	"515230",	"515710",	"515170",	"560800",	"561190",	"159790",	"516150",	"159928",	"159995",	"516160",	"515030",	"159939",	"512330",	"159959",	"159865",	"512170",	"159883",	"512010",	"512800",	"159736",	"159869",	"512400",	"516510",	"515250",	"513050",	"560080"]

class MultiStockStrategy(bt.Strategy):
    
    def __init__(self):
        self.stocks = self.datas[1:]
        self.current_stock = 0
        
    def next(self):
        if self.data.datetime.time() == datetime.time(15, 0):
            highest_close = -1
            highest_stock = None
            for stock in self.stocks:
                if stock.close[0] > highest_close:
                    highest_close = stock.close[0]
                    highest_stock = stock
            self.log('Buying ' + highest_stock._name + ' at ' + str(highest_close))
            self.order_target_percent(target=1, data=highest_stock)

            
    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print('%s, %s' % (dt.isoformat(), txt))
        
cerebro = bt.Cerebro()
for stock in etf_list:
    data = bt.feeds.YahooFinanceData(dataname=stock, fromdate=datetime.datetime(2019, 1, 1), todate=datetime.datetime(2020, 1, 1))
    cerebro.adddata(data, name=stock)
    
cerebro.addstrategy(MultiStockStrategy)
cerebro.run()