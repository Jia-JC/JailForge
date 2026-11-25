# `results/` 运行产物

本目录保存批量评测、真实 pilot 和进化实验的输出。除本 README 外，运行产物默认被
`.gitignore` 排除（`trials.jsonl`、`trials.csv`、`cache.json` 等），避免把原始模型回答
提交到公开仓库。

| 子目录 | 中文作用 |
| --- | --- |
| `mock_pilot/` | 离线 Mock pilot：32 目标 × 12 攻击 × 4 防御 = 1536 trials |
| `real_pilot/` | 真实 DeepSeek `deepseek-flash` pilot：8 目标 × 5 攻击 × 4 防御 = 160 trials |
| `evolution/` | 进化攻击结果 JSON（固定实验 + 桌面版每次运行） |
| `batch_*/` | 桌面版每次批量评测生成的运行目录 |
| `logs/` | 桌面版本地 HTTP 服务的日志 |

## 一次运行的文件

| 文件 | 中文作用 |
| --- | --- |
| `summary.json` | 聚合指标：总体/方法/防御/类别 ASR、Wilson CI、防御下降、FPR |
| `report.md` | 自动生成的 Markdown 报告 |
| `config.yaml` | 本次运行配置（已移除密钥） |
| `trials.jsonl` | 逐条明细，便于二次分析（默认不入库） |
| `trials.csv` | 逐条明细，Excel 可直接打开（默认不入库） |
| `cache.json` | 响应缓存，保证重跑一致（默认不入库） |

## 重要提醒

- `mock_pilot/` 的 ASR 是合成数据，只验证流水线，不能评价真实模型。
- `real_pilot/` 的 0.0% 只代表 8 条目标的小样本结果，不能外推。
- 原始模型回答可能包含敏感内容；分享前先脱敏/截断。
