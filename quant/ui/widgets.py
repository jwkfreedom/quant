"""wx 控件封装：表格、图表面板、指标卡、后台任务。

这一层只做「把数据画出来」，所有取数逻辑都在 `quant.ui.viewmodels` 里。
"""

from __future__ import annotations

import logging
import threading
import traceback

import pandas as pd
import wx
import wx.grid

logger = logging.getLogger(__name__)

#: 表格最多显示的行数（避免大表卡顿；导出不受限制）
MAX_GRID_ROWS = 2000


class DataFrameGrid(wx.grid.Grid):
    """把 DataFrame 显示成表格。

    支持：
        - 点击列头排序（升序/降序/取消）
        - 双击某行触发 `on_row_activated(row_dict)`
        - 右键菜单 `on_context_menu(row_dict, event)`（默认提供「复制」）
        - 复制选中单元格 / 整行到剪贴板
    """

    def __init__(self, parent, *, sortable: bool = True):
        super().__init__(parent)
        self._df = pd.DataFrame()
        self._original = pd.DataFrame()
        self._view_columns: list[str] = []
        self._display_names = False
        self._sort_column: str | None = None
        self._sort_ascending = False
        self._sortable = sortable
        self.on_row_activated = None       # Callable[[dict], None]
        self.on_context_menu = None        # Callable[[dict, wx.Event], None]

        self.CreateGrid(0, 0)
        self.SetRowLabelSize(60)
        self.EnableEditing(False)
        # wx.grid 没有 SetAlternateRowColour，用默认底色代替（隔行变色仅在部分版本可用）
        self.SetDefaultCellBackgroundColour(wx.Colour(255, 255, 255))

        if sortable:
            self.Bind(wx.grid.EVT_GRID_LABEL_LEFT_CLICK, self._on_label_click)
        self.Bind(wx.grid.EVT_GRID_CELL_LEFT_DCLICK, self._on_double_click)
        self.Bind(wx.grid.EVT_GRID_CELL_RIGHT_CLICK, self._on_right_click)
        self.Bind(wx.grid.EVT_GRID_LABEL_RIGHT_CLICK, self._on_right_click)
        self.Bind(wx.EVT_KEY_DOWN, self._on_key)

    # ------------------------------------------------------------------
    @property
    def frame(self) -> pd.DataFrame:
        """当前显示的完整数据（未截断、未按展示名改名）。"""
        return self._df

    def SetDataFrame(self, df: pd.DataFrame, *, display_names: bool = False, max_rows: int = MAX_GRID_ROWS):
        """填充表格。列名可选中文展示。"""
        if df is None:
            df = pd.DataFrame()

        self._df = df.reset_index(drop=True)
        self._original = self._df.copy()
        self._display_names = display_names
        self._sort_column = None
        self._sort_ascending = False
        self._render(max_rows=max_rows)

    def _render(self, *, max_rows: int = MAX_GRID_ROWS):
        from quant.data import schema

        data = self._df
        view = data.head(max_rows).copy()
        if self._display_names:
            view = schema.rename_for_display(view)

        self.Freeze()
        try:
            if self.GetNumberRows():
                self.DeleteRows(0, self.GetNumberRows())
            if self.GetNumberCols():
                self.DeleteCols(0, self.GetNumberCols())

            if view.empty:
                self._view_columns = []
                self.AppendRows(0)
                self.AppendCols(0)
                return

            # 用字符串列，避免 numpy 类型在 grid 里显示成 object
            text = view.astype(object).where(pd.notnull(view), "").astype(str)
            self._view_columns = list(text.columns)

            self.AppendCols(len(text.columns))
            self.AppendRows(len(text))
            for index, column in enumerate(text.columns):
                self.SetColLabelValue(index, str(column))
            for row_index, row in enumerate(text.itertuples(index=False)):
                for col_index, value in enumerate(row):
                    self.SetCellValue(row_index, col_index, value)

            for index in range(len(text.columns)):
                width = max(80, min(220, len(str(text.columns[index])) * 14 + 40))
                self.SetColSize(index, width)
        finally:
            self.Thaw()

    # ------------------------------------------------------------------
    # 排序
    # ------------------------------------------------------------------
    def _on_label_click(self, event: wx.grid.GridEvent):
        col = event.GetCol()
        if col < 0:            # 点的是行号
            event.Skip()
            return
        if col >= len(self._view_columns):
            return

        column = self._view_columns[col]
        if column not in self._df.columns:
            return

        if self._sort_column != column:
            self._sort_column, self._sort_ascending = column, False
        elif not self._sort_ascending:
            self._sort_ascending = True
        else:                  # 第三次点击：取消排序
            self._sort_column, self._sort_ascending = None, False

        if self._sort_column:
            self._df = self._df.sort_values(
                self._sort_column, ascending=self._sort_ascending, kind="mergesort",
                na_position="last",
            ).reset_index(drop=True)
        else:
            self._df = self._original.copy()   # 取消排序时恢复原始顺序
        self._render()
        self._refresh_header_labels()

    def _refresh_header_labels(self):
        from quant.data import schema

        for index, column in enumerate(self._view_columns):
            source = column
            if self._display_names:
                for key, label in schema.DISPLAY_NAMES.items():
                    if label == column:
                        source = key
                        break
            if self._sort_column == source:
                self.SetColLabelValue(index, f"{column} {'▲' if self._sort_ascending else '▼'}")
            else:
                self.SetColLabelValue(index, str(column))

    # ------------------------------------------------------------------
    # 选择 / 复制 / 回调
    # ------------------------------------------------------------------
    def row_at(self, row: int):
        """返回第 row 行对应的原始数据（dict）。"""
        if row < 0 or row >= len(self._df):
            return None
        return self._df.iloc[row].to_dict()

    def selected_row(self):
        """当前光标所在行的原始数据。"""
        return self.row_at(self.GetGridCursorRow())

    def selected_rows(self) -> pd.DataFrame:
        """所有被选中的行的原始数据（没有选区时返回光标所在行）。"""
        tops = self.GetSelectionBlockTopLeft()
        bottoms = self.GetSelectionBlockBottomRight()

        if not tops:
            row = self.GetGridCursorRow()
            return self._df.iloc[[row]] if 0 <= row < len(self._df) else self._df.head(0)

        indexes: set[int] = set()
        for (top, _left), (bottom, _right) in zip(tops, bottoms):
            indexes.update(range(top, bottom + 1))
        ordered = sorted(i for i in indexes if 0 <= i < len(self._df))
        return self._df.iloc[ordered] if ordered else self._df.head(0)

    def copy_selection(self) -> int:
        """把选中区域复制成 TSV 到剪贴板，返回行数。"""
        top, left = self.GetSelectionBlockTopLeft()[0] if self.GetSelectionBlockTopLeft() else (
            self.GetGridCursorRow(), self.GetGridCursorCol())
        bottom, right = self.GetSelectionBlockBottomRight()[0] if self.GetSelectionBlockBottomRight() else (
            top, left)

        lines = ["\t".join(self.GetColLabelValue(c) for c in range(left, right + 1))]
        for r in range(top, bottom + 1):
            lines.append("\t".join(self.GetCellValue(r, c) for c in range(left, right + 1)))
        text = "\n".join(lines)

        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(text))
            wx.TheClipboard.Close()
        return bottom - top + 1

    def _on_double_click(self, event: wx.grid.GridEvent):
        row = self.row_at(event.GetRow())
        if row is not None and self.on_row_activated is not None:
            self.on_row_activated(row)

    def _on_right_click(self, event: wx.grid.GridEvent):
        row = self.row_at(event.GetRow()) if event.GetRow() >= 0 else None
        if row is None:
            return

        menu = ContextMenu(self, row)
        menu.add("复制选中区域", lambda _row: self.copy_selection())
        if self.on_context_menu is not None:
            self.on_context_menu(row, menu)
        menu.popup(event.GetPosition())

    def _on_key(self, event: wx.KeyEvent):
        if event.GetKeyCode() == ord("C") and event.ControlDown():
            self.copy_selection()
        else:
            event.Skip()


class TextDialog(wx.Dialog):
    """只读长文本对话框（说明书 / 帮助）。

    带「复制全部」按钮，方便把说明贴到别处。
    """

    def __init__(self, parent, title: str, text: str, *, size=(960, 720)):
        super().__init__(parent, title=title, size=size,
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        root = wx.BoxSizer(wx.VERTICAL)

        self.text = wx.TextCtrl(
            self, value=text,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP | wx.TE_RICH2,
        )
        self.text.SetFont(wx.Font(wx.FontInfo(9).FaceName("Consolas")))
        self.text.SetInsertionPoint(0)
        root.Add(self.text, 1, wx.EXPAND | wx.ALL, 8)

        buttons = wx.BoxSizer(wx.HORIZONTAL)
        copy_button = wx.Button(self, label="复制全部")
        copy_button.Bind(wx.EVT_BUTTON, lambda _evt: self.on_copy())
        buttons.Add(copy_button, 0, wx.ALL, 4)
        buttons.AddStretchSpacer()
        close_button = wx.Button(self, wx.ID_CANCEL, label="关闭")
        buttons.Add(close_button, 0, wx.ALL, 4)
        root.Add(buttons, 0, wx.EXPAND | wx.ALL, 6)

        self.SetSizer(root)
        self.SetEscapeId(wx.ID_CANCEL)
        self.Centre()

    def on_copy(self):
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(self.text.GetValue()))
            wx.TheClipboard.Close()
            wx.MessageBox("说明已复制到剪贴板", "提示", wx.OK | wx.ICON_INFORMATION, self)


def show_text_dialog(parent, title: str, text: str) -> None:
    """便捷函数：弹出只读文本对话框。"""
    dialog = TextDialog(parent, title, text)
    try:
        dialog.ShowModal()
    finally:
        dialog.Destroy()


def relayout(*windows) -> None:
    """控件重建后强制重新布局与重绘。

    wx 不会在 sizer 内容变化后自动刷新已显示的区域，
    尤其是「面板套在 Notebook 页里」的情况，必须显式 Layout + Refresh。
    """
    for window in windows:
        if window is None:
            continue
        try:
            window.Layout()
            window.Refresh()
        except Exception:  # pragma: no cover - 窗口可能已销毁
            logger.debug("relayout 失败", exc_info=True)


class ContextMenu:
    """表格右键菜单：页面通过 `add(label, callback)` 注册菜单项。

    回调签名是 `callback(row_dict)`，其中 row_dict 是该行的原始数据。
    """

    def __init__(self, grid: "DataFrameGrid", row: dict):
        self._grid = grid
        self._row = row
        self._menu = wx.Menu()
        self._callbacks: dict[int, object] = {}

    def add(self, label: str, callback) -> int:
        item = self._menu.Append(wx.ID_ANY, label)
        self._callbacks[item.GetId()] = callback
        return item.GetId()

    def separator(self) -> None:
        self._menu.AppendSeparator()

    def popup(self, position) -> None:
        chosen = self._grid.GetPopupMenuSelectionFromUser(self._menu, position)
        callback = self._callbacks.get(chosen)
        self._menu.Destroy()
        if callback is not None:
            callback(self._row)


class FigurePanel(wx.Panel):
    """嵌入 matplotlib 图形的面板。"""

    def __init__(self, parent):
        super().__init__(parent)
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)
        self._canvas = None

    def set_figure(self, figure):
        """替换当前图形。"""
        if self._canvas is not None:
            self._sizer.Detach(self._canvas)
            self._canvas.Destroy()
            self._canvas = None

        if figure is None:
            self.Layout()
            return

        from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg

        self._canvas = FigureCanvasWxAgg(self, -1, figure)
        self._sizer.Add(self._canvas, 1, wx.EXPAND)
        self.Layout()
        parent = self.GetParent()
        if parent is not None:
            parent.Layout()
            parent.Refresh()
        self.Refresh()


class MetricCards(wx.Panel):
    """一行指标卡（标题 + 数值 + 可选颜色）。"""

    def __init__(self, parent, columns: int = 6):
        super().__init__(parent)
        self._columns = columns
        self._sizer = wx.FlexGridSizer(rows=0, cols=columns, vgap=6, hgap=10)
        self._sizer.AddGrowableCol(0, 1)
        self.SetSizer(self._sizer)
        self._labels: dict[str, wx.StaticText] = {}

    def set_metrics(self, items: list[tuple[str, str, str | None]]):
        """items: [(标题, 值, 颜色)]"""
        self._sizer.Clear(delete_windows=True)
        self._labels.clear()
        for title, value, colour in items:
            box = wx.Panel(self)
            inner = wx.BoxSizer(wx.VERTICAL)
            caption = wx.StaticText(box, label=title)
            caption.SetForegroundColour(wx.Colour(120, 120, 120))
            caption.SetFont(caption.GetFont().Smaller())
            number = wx.StaticText(box, label=str(value))
            font = number.GetFont()
            font.SetPointSize(font.GetPointSize() + 3)
            font.SetWeight(wx.FONTWEIGHT_BOLD)
            number.SetFont(font)
            if colour:
                number.SetForegroundColour(wx.Colour(colour))
            inner.Add(caption, 0)
            inner.Add(number, 0, wx.TOP, 2)
            box.SetSizer(inner)
            self._sizer.Add(box, 0, wx.ALL, 4)
            self._labels[title] = number

        # 子控件是重建的，父面板必须重新布局并重绘，否则界面上看不到变化
        self.Layout()
        parent = self.GetParent()
        if parent is not None:
            parent.Layout()
            parent.Refresh()
        self.Refresh()


class BusyRunner:
    """在后台线程跑任务，完成后回调主线程。"""

    def __init__(self, parent: wx.Window):
        self._parent = parent
        self._busy = False

    @property
    def busy(self) -> bool:
        return self._busy

    def run(self, func, on_done, on_error=None, busy_message: str = "处理中…"):
        if self._busy:
            wx.MessageBox("有任务正在执行，请稍候", "提示", wx.OK | wx.ICON_INFORMATION)
            return

        self._busy = True
        frame = wx.GetTopLevelParent(self._parent)
        if hasattr(frame, "set_status"):
            frame.set_status(busy_message)

        def worker():
            try:
                result = func()
            except Exception as exc:  # noqa: BLE001 - 需要把异常带回 UI
                logger.exception("后台任务失败")
                wx.CallAfter(self._finish, None, exc, on_done, on_error)
            else:
                wx.CallAfter(self._finish, result, None, on_done, on_error)

        threading.Thread(target=worker, daemon=True).start()

    def _finish(self, result, error, on_done, on_error):
        self._busy = False
        frame = wx.GetTopLevelParent(self._parent)
        if hasattr(frame, "set_status"):
            frame.set_status("就绪")

        if error is not None:
            if on_error is not None:
                try:
                    on_error(error)
                except Exception:  # pragma: no cover
                    logger.exception("错误处理回调本身出错")
            else:
                wx.MessageBox(f"{type(error).__name__}: {error}", "出错了",
                              wx.OK | wx.ICON_ERROR)
            return

        # 渲染回调里的异常以前会被 wx 吞进 stderr，界面上什么都看不到，
        # 这里显式兜住并弹窗，避免"命令行有输出、UI 没反应"。
        try:
            on_done(result)
        except Exception as exc:  # noqa: BLE001
            logger.exception("界面渲染失败")
            wx.MessageBox(
                f"结果已算出，但界面渲染失败：\n\n{type(exc).__name__}: {exc}",
                "渲染出错", wx.OK | wx.ICON_ERROR,
            )


def ask_save_path(parent, *, default_name: str = "export.csv",
                  wildcard: str = "CSV 文件 (*.csv)|*.csv|Excel 文件 (*.xlsx)|*.xlsx") -> str | None:
    """弹出保存对话框，返回路径或 None。"""
    with wx.FileDialog(parent, "导出为", wildcard=wildcard,
                       defaultFile=default_name,
                       style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dialog:
        if dialog.ShowModal() != wx.ID_OK:
            return None
        return dialog.GetPath()


def error_dialog(parent, error: Exception) -> None:
    """统一错误提示。"""
    detail = "".join(traceback.format_exception_only(type(error), error))
    wx.MessageBox(detail.strip(), "出错了", wx.OK | wx.ICON_ERROR)
