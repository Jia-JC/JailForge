# `jailforge/eval/` 评测层

负责把一次运行的 trial 汇总成指标，并保存可复现的产物。

| 文件 | 中文作用 |
| --- | --- |
| `__init__.py` | 导出 `Runner`、`RunResult`、`summarize`、`wilson_ci`、`format_summary_table`、`ResponseCache` |
| `metrics.py` | Wilson 95% 置信区间、单组统计、按方法/防御/类别汇总、攻击×防御矩阵、防御绝对/相对下降、Markdown 表格 |
| `cache.py` | 响应缓存：按“模型 + 完整 messages”哈希保存回答，保证重跑一致并降低 API 成本 |
| `runner.py` | 批量评测运行器：遍历 goal × method × defense，执行防御、推理、输出过滤、评判，保存 `summary.json` / `trials.jsonl` / `trials.csv` / `report.md`，并测量良性 FPR |

## 产物

每次运行在 `results/<run_name>/` 下生成：

- `summary.json`：聚合指标
- `trials.jsonl`：逐条明细
- `trials.csv`：Excel 可打开的明细
- `report.md`：自动报告
- `config.yaml`：本次配置（已移除密钥）
