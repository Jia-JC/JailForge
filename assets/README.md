# `assets/` 图标与版本信息

| 文件 | 中文作用 |
| --- | --- |
| `icon.png` | 512×512 应用图标（PNG），用于文档、Release 页面、商店展示 |
| `icon.ico` | 多尺寸 Windows 图标（16/24/32/48/64/128/256），PyInstaller 打包时嵌入 EXE |
| `version_info.txt` | Windows 文件属性里的产品名、版本、版权等元数据，PyInstaller `--version-file` 使用 |
| `使用说明.txt` | 便携版 zip 内的中文使用说明，由 `scripts/build_exe.ps1` 复制进发布包 |

重新生成图标：

```bash
python scripts/make_icon.py
```
