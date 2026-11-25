# 运行产物说明

本目录存放评测输出。默认被 `.gitignore` 排除，只有本说明文件入库。

一次运行会生成：

| 文件 | 内容 |
| --- | --- |
| `summary.json` | 聚合指标：总体/方法/防御/类别 ASR、CI、防御下降、FPR |
| `trials.jsonl` | 逐条明细，便于二次分析 |
| `trials.csv` | 逐条明细（Excel 可直接打开） |
| `report.md` | 自动生成的 Markdown 报告 |
| `config.yaml` | 本次运行配置（已移除密钥） |
| `cache.json` | 响应缓存，保证重跑一致 |

## 重要提醒

- `mock_pilot/` 由离线 `MockLLM` 生成，**ASR 是合成数据**，只用于验证流水线。
- `real_pilot/` 包含 DeepSeek `deepseek-flash` 的真实结果：160 trials，LLM judge ASR 0.0%
  （0/160，95% CI 0.0%–2.3%）；`judge_comparison.md` 记录了规则/LLM 评判差异。
- 真实 pilot 出现天花板效应：无防御基线也是 0.0%，暂未测出防御差异；不要把它解读为
  “模型绝对安全”。
- 原始模型回答可能包含敏感内容，默认不提交到公开仓库；如需分享，先脱敏/截断。
- 提交前检查 `git status`，确保没有把 `.env`、`cache.json`、原始日志带入。
