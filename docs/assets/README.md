# `docs/assets/` 界面截图

由 Edge/Chrome 无头模式对本地桌面版 UI 截图生成，用于 README 展示。

| 文件 | 中文作用 |
| --- | --- |
| `ui-dashboard.png` | 概览页：Hero、能力统计、评测流水线、最近运行 |
| `ui-single.png` | 单条测试页：目标选择、攻击/防御下拉、结果区 |
| `ui-batch.png` | 批量评测页：目标数量、攻击/防御多选、预计生成次数 |
| `ui-evolve.png` | 进化攻击页：目标、防御、代数/种群滑杆 |
| `ui-about.png` | 关于与伦理页：能力、边界、局限、链接 |

重新生成（需要先启动 `JailForge.exe --no-browser`）：

```powershell
msedge --headless=new --window-size=1440,1050 `
  --screenshot=docs/assets/ui-dashboard.png `
  "http://127.0.0.1:17865/?page=dashboard"
```
