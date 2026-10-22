# UI 视觉规范（V2）

> 目标：把"系统默认灰控件"的观感，换成卡片化、扁平、统一的现代风格。
> 效果稿：`docs/ui_mockup.html`（浏览器直接打开）；可运行样张：`scripts/ui_style_demo.py`。
> 代码位置：配色与图表主题在 `quant/ui/theme.py`，自绘控件在 `quant/ui/components.py`。

## 1. 配色

| 用途 | 变量（theme.C） | 色值 |
| --- | --- | --- |
| 窗口底色 | `bg` | `#F5F6F8` |
| 卡片底 | `card` | `#FFFFFF` |
| 卡片描边 / 分隔线 | `border` / `divider` | `#E5E7EB` / `#F1F2F4` |
| 主文字 | `text` | `#111827` |
| 次要文字 | `text_secondary` | `#6B7280` |
| 最弱文字（占位/单位） | `text_muted` | `#9CA3AF` |
| 主色（按钮/选中/链接） | `primary` / `primary_hover` / `primary_light` | `#2563EB` / `#1D4ED8` / `#EFF4FF` |
| 涨 | `up` | `#D93F3F` |
| 跌 | `down` | `#2E9E5B` |
| 正常状态标签 | `ok` / `ok_bg` | `#047857` / `#ECFDF5` |
| 提醒状态标签 | `warn` / `warn_bg` | `#B45309` / `#FFFBEB` |
| 表头底色 | `table_header` | `#F9FAFB` |
| 表格网格线 | `table_line` | `#EEF0F3` |
| 表格选中行 | `table_selected` | `#EFF4FF` |
| 导航 hover | `nav_hover` | `#EFF1F5` |
| 状态栏 | `status_bg` | `#ECEFF3` |

A 股习惯红涨绿跌，不用国际配色。

## 2. 字体

| 层级 | 字体 | 字号 | 粗细 | 常量 |
| --- | --- | --- | --- | --- |
| 页面标题 | Microsoft YaHei UI | 16pt | Bold | `FONT_PAGE_TITLE` |
| 卡片标题 | Microsoft YaHei UI | 11pt | Bold | `FONT_CARD_TITLE` |
| 正文 / 控件 | Microsoft YaHei UI | 10pt | Normal | `FONT_BODY` |
| 表格 / 说明 / 标签 | Microsoft YaHei UI | 9pt | Normal | `FONT_SMALL` |
| 数字、价格、代码 | Consolas | 9pt | Normal | 同上 + `mono=True` |

数字统一等宽，列对齐才不会跳。

## 3. 尺寸

- 圆角：卡片 `RADIUS_CARD=10`，按钮 `RADIUS_BTN=6`，标签胶囊 = 高度/2。
- 间距：以 **8px** 为基准。卡片内边距 16（`PAD`），卡片间距 12（`GAP`），控件间距 8。
- 表格：表头行高 34，数据行高 30，行号列宽 58。
- 导航项：高 42，间隔 4，左右外边距 8，文字左边距 18。
- 侧边导航宽度 190。

## 4. 组件

| 组件 | 用法 |
| --- | --- |
| `Card(parent, title, subtitle)` | 白底圆角卡片；内容加到 `card.body`（控件父窗口要用 `card.body`），或用 `card.add(...)` / `card.add_spacer(n)` |
| `FlatButton(parent, label, primary=)` | 扁平按钮，`primary=True` 为蓝底白字主按钮；支持 hover / 按下 / 禁用态 |
| `Badge(parent, text, kind=)` | 圆角小标签，kind 取 `ok` / `warn` / `info` / `muted` |
| `SideNav(parent, items, on_select=)` | 左侧导航，选中项浅蓝底 + 左侧 3px 蓝竖条 |
| `PageHeader(parent, title, subtitle, badges, actions)` | 页面顶部标题条：大标题 + 状态标签 + 右侧按钮 |
| `make_notebook(parent)` | 扁平页签（agw.FlatNotebook），失败自动回退 `wx.Notebook` |
| `text_label` / `hint_label` / `style_input` / `style_checkbox` | 统一样式的 StaticText / 灰色小字 / 输入控件 / 复选框 |
| `DataFrameGrid.apply_theme()` | 表格统一外观（构造时自动调用） |

## 5. 图表主题

`theme.apply_matplotlib_theme()` 在导入 `charts.py` 时自动执行一次，设置：

- 中文字体（自动探测 Microsoft YaHei → SimHei → Noto Sans CJK SC）
- 白底、去掉上/右框线、网格线 `#EEF0F3`、坐标轴文字 `#6B7280`
- 标题加粗 11pt、图例无边框 8pt
- 主色环 `CHART_COLORS`（蓝/红/绿/橙/紫/青）

## 6. 表格的一个取舍

`wx.grid` 里**行属性会完全覆盖列属性**：一旦给某些行设了 `SetRowAttr`（隔行变色），
就再也无法对这些行用列属性做右对齐。

所以表格最终是「极浅网格线 + 30px 行高 + 数字列右对齐 + 选中浅蓝」，没有做斑马纹
—— 斑马纹与网格线本来就重复。

## 7. 换肤方式

改 `quant/ui/theme.py` 的 `C` 类即可全局生效（配色、字号、圆角、间距都在那里）。
若只是想让某处颜色不同，用 `theme.sign_colour(value)` 之类的小工具，不要就地写死色值。

## 8. 验证方式

本机没有显示器，界面靠三层手段验证：

1. `tests/test_wx_api.py`：AST 扫描所有 `wx.<Name>`，确保不存在拼错的类名。
2. `tests/test_ui_frame.py`：无头构造 `MainFrame` 与六个页面，断言控件与数据流转正常。
3. 自绘控件把绘制拆成 `_paint(gc, width, height)`，可用 `wx.MemoryDC` 直接渲染，
   无头也能确认绘制路径不抛异常。

真实观感仍需在本机运行 `.\\scripts\\run_ui.bat` 确认。
