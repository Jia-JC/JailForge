# `jailforge/models/` 模型适配层

把不同模型服务统一成 `generate(messages) -> str` 接口。

| 文件 | 中文作用 |
| --- | --- |
| `__init__.py` | 导出 `BaseLLM`、`MockLLM`、`OpenAICompatibleLLM`、`build_model`、`ModelError` |
| `base.py` | 抽象基类 `BaseLLM` 与统一的 `ModelError` |
| `mock.py` | 离线 Mock 模型：根据攻击强度、防御系统提示和种子决定“拒答/配合”，配合时只输出 `[SIMULATED-COMPLIANCE]` 占位符，绝不生成真实有害内容 |
| `openai_compatible.py` | 任意 OpenAI-compatible `/chat/completions` 适配器：DeepSeek、DashScope、OpenAI、vLLM、Ollama 等；含重试、超时、错误处理 |
| `registry.py` | 根据配置/环境变量构建模型；校验 API Key、base_url、model 是否齐全 |

## 说明

- Mock 的 ASR 是合成数据，只用于验证流水线，不能评价真实模型安全性。
- 真实模型只需在 `.env` 中填 `JAILFORGE_BASE_URL`、`JAILFORGE_MODEL`、`JAILFORGE_API_KEY`。
