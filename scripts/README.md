# `scripts/` 工具脚本

| 文件 | 中文作用 |
| --- | --- |
| `github_upload.py` | 通过 GitHub REST API 创建仓库、上传项目树、上传课程报告、创建 PR（适用于 `github.com` 被墙但 `api.github.com` 可用的网络） |
| `compare_judges.py` | 对已有运行结果重新用规则 judge 打分，输出“规则 vs LLM”ASR 对比，定位误判 |
| `recompute_real.py` | 修复真实 pilot 中 3 条 LLM judge fallback，重算 `summary.json` 并重生成 `report.md` |
| `make_icon.py` | 用 Pillow 生成 `assets/icon.png` 与多尺寸 `assets/icon.ico` |
| `build_exe.ps1` | 一键构建单文件 EXE + 便携版 zip + SHA256（需要 PyInstaller） |

## 注意

- `github_upload.py` 从 `.secrets/github_token.txt` 或 `GITHUB_TOKEN` 读取 Token，绝不打印。
- `recompute_real.py` 不会调用任何 API，只修正已保存的结果。
- 构建脚本会把产物写到 `dist/`、`dist-portable/`、`release/`，这些目录已在 `.gitignore` 中。
