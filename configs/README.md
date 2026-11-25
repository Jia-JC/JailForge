# `configs/` 运行配置

YAML 配置会与 `jailforge/config.py` 中的默认值深合并，并展开 `${VAR}` 环境变量。

| 文件 | 中文作用 |
| --- | --- |
| `mock_quick.yaml` | 离线 Mock 快速评测：32 目标、12 攻击、4 防御、规则 judge；桌面版后端也以此为基底 |
| `openai_compatible.yaml` | 真实模型 + 规则 judge：8 目标、5 攻击、4 防御，适合低成本快速跑通 |
| `real_pilot_llm.yaml` | 真实模型 + LLM judge：与 `openai_compatible.yaml` 相同的矩阵，但用 LLM 复核回答，ASR 更可信、API 成本约翻倍 |

## 常用覆盖

```bash
python -m jailforge run --config configs/mock_quick.yaml
python -m jailforge run --config configs/real_pilot_llm.yaml --max-goals 4
```

环境变量优先级高于 YAML：

```dotenv
JAILFORGE_BASE_URL=https://api.deepseek.com/v1
JAILFORGE_MODEL=deepseek-chat
JAILFORGE_API_KEY=sk-...
```
