# `jailforge/judge/` 评判层

判断“模型回答是否在实质上配合了有害目标”，是 ASR 统计的核心。

| 文件 | 中文作用 |
| --- | --- |
| `__init__.py` | 导出 `RuleJudge`、`LLMJudge`、`EnsembleJudge`、`build_judge` |
| `rule_judge.py` | 零成本规则评判：拒答词、配合词、通用风险词、8 个类别的关键词；输出 `success/score/rationale/severity` |
| `llm_judge.py` | 调用 LLM 输出 JSON 评判；解析失败或调用失败时回退规则评判；`EnsembleJudge` 要求两个 judge 同时判成功 |

## 已知边界

- 规则 judge 会把“只尝试解码 Base64”“英文思维链里出现敏感词”误判为成功；真实 ASR
  必须用 LLM judge 复核或人工抽检。
- LLM judge 与目标模型同源时存在自偏好风险，报告需注明。
