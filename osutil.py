import os
import shutil

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

# move_file_byprefix('data/a/stock')
