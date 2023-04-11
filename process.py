import download as dl
import stockdata as sd
import pandas as pd

def download_a_jibenmian():
    # 下载2022年4季度
    dl.jibenmian_all_fast('xjll', 2022, 2023, ["{year}1231"])
    dl.jibenmian_all_fast('zcfz', 2022, 2023, ["{year}1231"])
    dl.jibenmian_all_fast('lrb', 2022, 2023, ["{year}1231"])

    # 下载2022年所有数据
    """
    dl.jibenmian_all_fast('xjll', 2022, 2023)
    dl.jibenmian_all_fast('zcfz', 2022, 2023)
    dl.jibenmian_all_fast('lrb', 2022, 2023)
    """


# startYear : 格式: 数字，例如2021
def calc_a_growth(startYear, file):
    startDate = str(startYear) + "-01-01"
    print(f"开始计算增长数据...(开始季度: {startYear}一季度)")
    df = sd.load_jibenmian(startDate)    # 从2021年 第一季度开始
    df = sd.rm_broken_stocks(df)            # 保留所有季度都有数据的股票

    df = sd.growth_score(df)                # 计算增长
    df.to_csv(file,index=False, encoding='utf_8_sig')



# download_a_jibenmian()
calc_a_growth(2021, 'data/202101-202204.csv')