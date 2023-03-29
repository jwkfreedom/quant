import os

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

#rename_file('zcfz_report_')
