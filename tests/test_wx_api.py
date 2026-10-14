"""静态检查 UI 源码里用到的 wx 属性名是否真的存在。

背景：开发环境没有显示，无法真正创建窗口；像 `wx.ListBook`（应为 `wx.Listbook`）
这类拼写错误只有在用户本机运行时才会暴露。这里用 AST 把源码里所有 `wx.<Name>`
取出来逐个核对，把这类问题挡在单测里。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

wx = pytest.importorskip("wx")
import wx.grid  # noqa: E402,F401  子模块需要显式导入，否则 hasattr(wx, "grid") 为假

UI_ROOT = Path(__file__).resolve().parent.parent / "quant" / "ui"

#: wx 模块里可能通过 from-import 注入、或运行期才存在的名字，做白名单
ALLOWED = set()


def _wx_attributes(path: Path) -> set[str]:
    """收集源码里所有 `wx.xxx` 形式的属性名。"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()

    class Visitor(ast.NodeVisitor):
        def visit_Attribute(self, node: ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "wx":
                found.add(node.attr)
            self.generic_visit(node)

    Visitor().visit(tree)
    return found


def _ui_files():
    return sorted(UI_ROOT.rglob("*.py"))


def test_ui_files_found():
    files = _ui_files()
    assert files, "没有找到 UI 源码，检查路径"


@pytest.mark.parametrize("path", _ui_files(), ids=lambda p: p.name)
def test_wx_attributes_exist(path: Path):
    """每个 wx.<Name> 都必须存在于 wx 模块上。"""
    missing = sorted(
        name for name in _wx_attributes(path)
        if name not in ALLOWED and not hasattr(wx, name)
    )
    assert not missing, f"{path.name} 使用了不存在的 wx 属性: {missing}"


def test_no_common_book_class_typos():
    """`wx.ListBook` / `wx.TreeBook` 这类大小写错误在 wxPython 中并不存在。"""
    for wrong in ("ListBook", "TreeBook", "ToolBook", "ChoiceBook"):
        assert not hasattr(wx, wrong), f"wx.{wrong} 竟然存在了，请复核本测试"
        assert hasattr(wx, wrong.replace("B", "b")), f"wx.{wrong.replace('B', 'b')} 不存在"
