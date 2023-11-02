import os
import shutil

# type: 'pre' or 'cur'
# 将指定type的日线数据move到 data/a/stock/temp 目录
def clear_price_a_files(type):
    src_dir = 'data/a/stock/price'

    # 目标目录
    dst_dir = 'data/a/stock/temp'

    endfilter = f'{type}.csv'
    # 遍历源目录下所有文件
    for file_name in os.listdir(src_dir):
        # 判断文件名是否以'abc.csv'结尾
        if file_name.endswith(endfilter):
            # 构造源文件路径和目标文件路径
            src_file_path = os.path.join(src_dir, file_name)
            dst_file_path = os.path.join(dst_dir, file_name)
            # 移动文件
            shutil.move(src_file_path, dst_file_path)


# 把子目录中所有SZXXX目录名改为XXX
def rename_fold():
    path = "data/a"
    for foldername in os.listdir(path):
        print(foldername)
        if foldername.startswith("SZ") and os.path.isdir(os.path.join(path, foldername)):
            os.rename(os.path.join(path, foldername), os.path.join(path, foldername[2:]))


# 把 XXXXX_SZYYYYY.csv改为XXXXXX_YYYYY.csv
# prefix:   xjll_report_
#           lrb_report_
#           zcfz_report_
# 
def rename_file(prefix):
    for root, dirs, files in os.walk("data/a/stock"):
        for file in files:
            if file.startswith(prefix + "SH") and file.endswith(".csv"):
                new_name = prefix + file[len(prefix)+2:]
                os.rename(os.path.join(root, file), os.path.join(root, new_name))


# 把一个目录下的所有子目录中的XXX_????.csv文件移动到 XXX目录中，如果XXX目录不存在，就创建XXX目录。其中XXX是多个字母的组合。
def move_file_byprefix(directory):
    # Loop through all subdirectories
    for subdir, dirs, files in os.walk(directory):
        for file in files:
            # Check if file matches pattern
            if file.endswith('.csv'):
                # Extract XXX from file name
                xxx = file.split('_')[0]
                # Create XXX directory if it doesn't exist
                if not os.path.exists(os.path.join(directory, xxx)):
                    os.makedirs(os.path.join(directory, xxx))
                # Move file to XXX directory
                shutil.move(os.path.join(subdir, file), os.path.join(directory, xxx, file))

