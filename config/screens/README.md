# config/screens —— 筛选方案

桌面界面「选股筛选」页保存的方案放在这里，一个方案一个 JSON：

```json
{
  "name": "低估值高ROE",
  "note": "",
  "specs": ["exclude_st", "pe:max=20", "pe_percentile:window_years=10,max=20", "roe:min=10"],
  "saved_at": "2026-10-14 10:30:00"
}
```

`specs` 就是命令行 `quant screen --filter ...` 的参数，可以直接复制使用：

```bat
quant screen --filter exclude_st --filter pe:max=20 --filter pe_percentile:window_years=10,max=20
```

目录位置可以用环境变量 `QUANT_SCREENS_DIR` 改到别处。
