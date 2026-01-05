import wx

class MyFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="wxPython 按钮与日期控件示例", size=(400, 300))

        # 创建面板
        panel = wx.Panel(self)

        # 添加日期控件
        self.date_picker = wx.DatePickerCtrl(panel, style=wx.DP_DEFAULT | wx.DP_SHOWCENTURY)

        # 添加按钮
        self.button = wx.Button(panel, label="获取日期")

        # 绑定按钮点击事件
        self.button.Bind(wx.EVT_BUTTON, self.on_button_click)

        # 布局
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.date_picker, 0, wx.ALL | wx.EXPAND, 10)
        sizer.Add(self.button, 0, wx.ALL | wx.CENTER, 10)

        panel.SetSizer(sizer)

    def on_button_click(self, event):
        # 获取日期控件中的值（返回的是 wx.DateTime 对象）
        date = self.date_picker.GetValue()
        # 转换为字符串显示
        date_str = date.FormatDate()
        wx.MessageBox(f"你选择的日期是: {date_str}", "提示")


if __name__ == "__main__":
    app = wx.App()
    frame = MyFrame()
    frame.Show()
    app.MainLoop()