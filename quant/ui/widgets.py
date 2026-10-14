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
    """把 DataFrame 显示成表格。"""

    def __init__(self, parent):
        super().__init__(parent)
        self._df = pd.DataFrame()
        self.CreateGrid(0, 0)
        self.SetRowLabelSize(60)
        self.EnableEditing(False)
        # wx.grid 没有 SetAlternateRowColour，用默认底色代替（隔行变色仅在部分版本可用）
        self.SetDefaultCellBackgroundColour(wx.Colour(255, 255, 255))

    @property
    def frame(self) -> pd.DataFrame:
        return self._df

    def SetDataFrame(self, df: pd.DataFrame, *, display_names: bool = False, max_rows: int = MAX_GRID_ROWS):
        """填充表格。列名可选中文展示。"""
        from quant.data import schema

        if df is None:
            df = pd.DataFrame()

        view = df.head(max_rows).copy()
        if display_names:
            view = schema.rename_for_display(view)

        self._df = df
        self.Freeze()
        try:
            if self.GetNumberRows():
                self.DeleteRows(0, self.GetNumberRows())
            if self.GetNumberCols():
                self.DeleteCols(0, self.GetNumberCols())

            if view.empty:
                self.AppendRows(0)
                self.AppendCols(0)
                return

            # 用字符串列，避免 numpy 类型在 grid 里显示成 object
            text = view.astype(object).where(pd.notnull(view), "").astype(str)

            self.AppendCols(len(text.columns))
            self.AppendRows(len(text))
            for index, column in enumerate(text.columns):
                self.SetColLabelValue(index, str(column))
            for row_index, row in enumerate(text.itertuples(index=False)):
                for col_index, value in enumerate(row):
                    self.SetCellValue(row_index, col_index, value)
            self.AutoSizeColumns(False)
            for index in range(len(text.columns)):
                width = max(80, min(200, self.GetColLabelValue(index).__len__() * 14 + 40))
                self.SetColSize(index, width)
        finally:
            self.Thaw()


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
        self.Layout()


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
                on_error(error)
            else:
                wx.MessageBox(f"{type(error).__name__}: {error}", "出错了",
                              wx.OK | wx.ICON_ERROR)
            return

        on_done(result)


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
