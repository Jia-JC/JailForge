# `results/mock_pilot/` 离线 Mock pilot

32 条目标 × 12 种攻击 × 4 种防御 = **1536 trials**，随机种子 42，离线 Mock 模型。

| 文件 | 中文作用 |
| --- | --- |
| `summary.json` | 聚合指标：总体 ASR 11.2%，none 23.7% / filter 17.7% / self_defense 3.4% / layered 0.0% |
| `report.md` | 自动生成的完整报告（含攻击×防御矩阵、防御收益、分类别 ASR、FPR、样例） |
| `config.yaml` | 本次运行配置 |
| `trials.jsonl` | 逐条明细（本地生成，默认不入库） |
| `trials.csv` | 逐条明细（本地生成，默认不入库） |

> Mock 的“配合”是 `[SIMULATED-COMPLIANCE]` 占位符，ASR 是合成数据，不能评价真实模型。
