import unittest
import stockdata as sd

# 编写测试类，继承自unittest.TestCase
class TestAddNumbers(unittest.TestCase):

    # 测试stockdata 的函数
    def test_load_jibenmian(self):
        df = sd.load_jibenmian('2021-01-01', 360)
        print(df.columns)
        self.assertGreater(len(df.columns), 10)
        self.assertGreater(df.shape[0], 2)  # 行数
    
    def test_get_stock_price(self):
        df = sd.get_stock_price('000001')
        self.assertGreater(len(df.columns), 10)
        self.assertGreater(df.shape[0], 2)  # 行数

    def test_get_full_price(self):
        symbol = '000002'
        df = sd.get_full_price(symbol)
        self.assertGreater(len(df.columns), 10)
        self.assertGreater(df.shape[0], 2)  # 行数


    @classmethod
    def setUpClass(cls):
        test_functions = [name for name in dir(cls) if name.startswith('test_')]
        print("测试函数列表:")
        for func in test_functions:
            print(func)

# 运行测试
if __name__ == '__main__':
    unittest.main()



