"""DSH 沙箱兼容补丁 —— 仅在 DSH 会话中生效。

背景
----
在 DSH 文件沙箱下，用 0o700 模式创建的目录对当前进程不可写：

    os.mkdir(path, 0o700)  ->  之后向该目录写文件报 PermissionError [Errno 13]

而 Python 标准库的 tempfile.mkdtemp() 正是以 0o700 建目录，于是
pip 解包 wheel、ensurepip、tempfile.TemporaryDirectory 全部失败。

本模块把临时目录创建模式放宽为 0o777，并跳过 TemporaryDirectory 的 chmod。
未设置 DSH_SESSION_ID 时不做任何改动，因此不影响普通环境。

该文件由 scripts/bootstrap.ps1 复制到虚拟环境的 site-packages 下。
"""

from __future__ import annotations

import os

__all__: list[str] = []

if os.environ.get("DSH_SESSION_ID"):
    import tempfile

    def _mkdtemp(suffix=None, prefix=None, dir=None):
        prefix, suffix, dir, _output_type = tempfile._sanitize_params(prefix, suffix, dir)
        if dir is None:
            dir = tempfile.gettempdir()
        for _ in range(tempfile.TMP_MAX):
            name = os.path.join(dir, prefix + next(tempfile._get_candidate_names()) + suffix)
            try:
                os.mkdir(name, 0o777)
            except FileExistsError:
                continue
            return name
        raise FileExistsError("no usable temporary directory name found")

    tempfile.mkdtemp = _mkdtemp
    # chmod 在沙箱中会被拒绝，TemporaryDirectory 依赖它做权限收紧
    tempfile._resetperms = lambda path: None
