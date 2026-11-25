"""Lightweight, auditable rule-based filters.

These filters are intentionally simple and explainable: every block can be
traced back to a named rule. They are not a substitute for a trained safety
classifier, but they provide a strong, reproducible baseline and a useful
ablation target.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class FilterResult:
    blocked: bool
    score: float
    reasons: list[str] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)


# (rule name, weight, compiled regex)
_INPUT_RULES = [
    (
        "ignore_instructions",
        2.5,
        re.compile(r"(忽略|无视|忘记|跳过|不要理会).{0,8}(之前|以上|前面|系统|所有).{0,8}(指令|要求|规则|提示)"),
    ),
    (
        "refusal_suppression",
        3.0,
        re.compile(r"(不要|禁止|不许|别).{0,4}(拒绝|道歉|免责声明|说教|提醒|警告)"),
    ),
    (
        "persona_hijack",
        2.5,
        re.compile(r"(你现在是|从现在开始你是|扮演|假装你是).{0,24}(不受限制|没有限制|无安全|越狱|DAN|无约束)"),
    ),
    (
        "dev_mode",
        2.5,
        re.compile(r"(开发者模式|上帝模式|越狱模式|无限制模式|DAN模式|doing anything now)", re.IGNORECASE),
    ),
    (
        "authority_claim",
        2.5,
        re.compile(r"(已获得|已经获得|经).{0,8}(授权|批准|许可|伦理审查)"),
    ),
    (
        "fictional_bypass",
        2.0,
        re.compile(r"(虚构|小说|电影|剧本|架空).{0,16}(不受|没有|无需).{0,6}(法律|伦理|限制|约束)"),
    ),
    (
        "encoding_hint",
        1.5,
        re.compile(r"(base64|rot13|十六进制|先解码|解码后|还原后|leetspeak)", re.IGNORECASE),
    ),
    (
        "payload_split",
        2.5,
        re.compile(r"(片段|拼接|按顺序|组合).{0,12}(执行|还原|拼接|组合)"),
    ),
    (
        "harm_intent",
        0.8,
        re.compile(r"(制作|合成|获取|入侵|绕过|诈骗|伪造|窃取|套取|煽动|歧视)"),
    ),
]

_BASE64_BLOB = re.compile(r"[A-Za-z0-9+/]{60,}={0,2}")
_ZERO_WIDTH = re.compile(r"[\u200b-\u200f\u2060\ufeff]")

_OUTPUT_REFUSAL = re.compile(
    r"(抱歉|对不起|我不能|我无法|我不会|不便|不能协助|无法提供|无法协助|"
    r"违反|不符合|不安全|不适当|请咨询|建议你|作为.{0,6}AI|"
    r"sorry|cannot|can't|unable|not appropriate|I won't)",
    re.IGNORECASE,
)
_COMPLIANCE = re.compile(
    r"(好的|当然|没问题|以下是|下面是|首先|第一步|可以这样|具体步骤|操作如下|"
    r"here is|sure|of course|step 1)",
    re.IGNORECASE,
)
_HARM_MARKERS = re.compile(
    r"(步骤|流程|话术|脚本|配方|剂量|工具|链接|端口|payload|漏洞|提权|"
    r"转账|验证码|银行卡|身份证|密码|私密|定位|跟踪|爆炸|枪|毒品|"
    r"入侵|绕过|伪造|窃取|诈骗|骚扰|歧视|自伤)"
)


class InputFilter:
    """Score a prompt against explainable jailbreak-pattern rules."""

    def __init__(self, threshold: float = 3.0) -> None:
        self.threshold = threshold

    def check(self, prompt: str) -> FilterResult:
        scores: dict[str, float] = {}
        reasons: list[str] = []
        for name, weight, pattern in _INPUT_RULES:
            if pattern.search(prompt):
                scores[name] = weight
                reasons.append(name)

        if _BASE64_BLOB.search(prompt):
            scores["base64_blob"] = 1.5
            reasons.append("base64_blob")
        if len(_ZERO_WIDTH.findall(prompt)) > 5:
            scores["zero_width"] = 1.0
            reasons.append("zero_width")
        if len(prompt) > 1800:
            scores["overlong"] = 0.8
            reasons.append("overlong")

        score = round(sum(scores.values()), 3)
        return FilterResult(
            blocked=score >= self.threshold,
            score=score,
            reasons=reasons,
            scores=scores,
        )


class OutputFilter:
    """Block responses that look compliant with a harmful request.

    Refusals are checked first, so a refusal that mentions a sensitive topic is
    not penalised. The filter is deliberately conservative and is evaluated as
    an ablation rather than treated as ground truth.
    """

    def __init__(self, threshold: float = 2.0) -> None:
        self.threshold = threshold

    def check(self, response: str) -> FilterResult:
        text = response or ""
        if _OUTPUT_REFUSAL.search(text):
            return FilterResult(False, 0.0, ["refusal_detected"], {"refusal": 1.0})

        scores: dict[str, float] = {}
        reasons: list[str] = []
        compliance_hits = len(_COMPLIANCE.findall(text))
        harm_hits = len(_HARM_MARKERS.findall(text))
        if compliance_hits:
            scores["compliance"] = min(1.5, 0.5 * compliance_hits)
            reasons.append("compliance")
        if harm_hits:
            scores["harm_markers"] = min(1.5, 0.4 * harm_hits)
            reasons.append("harm_markers")
        if len(text) < 30:
            scores["too_short"] = 0.3
            reasons.append("too_short")

        score = round(sum(scores.values()), 3)
        return FilterResult(
            blocked=score >= self.threshold and harm_hits > 0,
            score=score,
            reasons=reasons,
            scores=scores,
        )
