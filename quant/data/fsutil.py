"""文件系统维护工具。

原 utils/osutil.py，供数据目录迁移/改名使用。
路径由相对路径改为统一的 DATA_DIR。

注意：这些是一次性维护工具，不属于日常数据流，不要在新代码中依赖。
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

from quant.config import DATA_DIR

logger = logging.getLogger(__name__)

PRICE_DIR = DATA_DIR / "a" / "stock" / "price"
TEMP_DIR = DATA_DIR / "a" / "stock" / "temp"


def clear_price_a_files(type: str) -> None:
    """把 data/a/stock/price 下以 <type>.csv 结尾的文件移动到 temp 目录。

    参数 type 取 'pre' 或 'cur'。
    """
    end_filter = f"{type}.csv"
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    for file_name in os.listdir(PRICE_DIR):
        if file_name.endswith(end_filter):
            shutil.move(str(PRICE_DIR / file_name), str(TEMP_DIR / file_name))


def rename_fold(path: Path | None = None) -> None:
    """把 data/a 下形如 SZXXXXXX 的目录重命名为 XXXXXX。"""
    base = path or (DATA_DIR / "a")
    for folder_name in os.listdir(base):
        logger.info("%s", folder_name)
        if folder_name.startswith("SZ") and (base / folder_name).is_dir():
            os.rename(base / folder_name, base / folder_name[2:])


def rename_file(prefix: str) -> None:
    """把 XXXXXX_SZYYYYYY.csv 改名为 XXXXXX_YYYYYY.csv。

    prefix 例：xjll_report_ / lrb_report_ / zcfz_report_
    """
    for root, _dirs, files in os.walk(DATA_DIR / "a" / "stock"):
        for file in files:
            if file.startswith(prefix + "SH") and file.endswith(".csv"):
                new_name = prefix + file[len(prefix) + 2:]
                os.rename(os.path.join(root, file), os.path.join(root, new_name))


def move_file_byprefix(directory: Path | str) -> None:
    """把目录下所有子目录中的 XXX_????.csv 移动到 <directory>/XXX/ 下。"""
    directory = Path(directory)
    for subdir, _dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".csv"):
                xxx = file.split("_")[0]
                target = directory / xxx
                if not target.exists():
                    target.mkdir(parents=True, exist_ok=True)
                shutil.move(os.path.join(subdir, file), str(target / file))
