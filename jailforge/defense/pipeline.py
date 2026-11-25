"""Composable defense pipeline with named profiles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..schema import DefenseDecision
from .filters import InputFilter, OutputFilter
from .prompts import build_system_prompt, spotlight

DEFENSE_PROFILES: dict[str, dict[str, str]] = {
    "none": {
        "label": "无防御",
        "description": "不添加系统提示、不做过滤，作为攻击成功率上界基线。",
    },
    "filter": {
        "label": "输入过滤",
        "description": "仅用可解释规则检测可疑 prompt，命中即拦截。",
    },
    "self_defense": {
        "label": "自卫提示",
        "description": "注入安全系统提示，但不做输入/输出过滤。",
    },
    "layered": {
        "label": "分层防御",
        "description": "输入过滤 + 自卫提示 + 输出过滤，默认配置。",
    },
    "strict": {
        "label": "严格防御",
        "description": "分层防御 + spotlighting + 更低拦截阈值，牺牲可用性换鲁棒性。",
    },
}


@dataclass
class PostDecision:
    blocked: bool
    reason: str = ""
    stage: str = ""


class DefensePipeline:
    def __init__(
        self,
        profile: str = "layered",
        config: dict[str, Any] | None = None,
    ) -> None:
        if profile not in DEFENSE_PROFILES:
            available = ", ".join(DEFENSE_PROFILES)
            raise ValueError(f"unknown defense profile '{profile}'. Available: {available}")
        self.profile = profile
        self.config = config or {}
        threshold = float(self.config.get("filter_threshold", 3.0))
        if profile == "strict":
            threshold = min(threshold, 2.0)
        self.input_filter = InputFilter(threshold=threshold)
        self.output_filter = OutputFilter(
            threshold=float(self.config.get("output_threshold", 2.0))
        )
        self.spotlight_enabled = bool(self.config.get("spotlight", True))

    def pre(self, prompt: str, base_system: str | None = None) -> DefenseDecision:
        if self.profile == "none":
            return DefenseDecision(prompt=prompt, system_prompt=base_system, stage="none")

        scores: dict[str, float] = {}
        if self.profile in {"filter", "layered", "strict"}:
            result = self.input_filter.check(prompt)
            scores.update(result.scores)
            if result.blocked:
                return DefenseDecision(
                    blocked=True,
                    stage="input_filter",
                    reason=", ".join(result.reasons),
                    prompt=prompt,
                    system_prompt=base_system,
                    scores=scores,
                )

        system_prompt = build_system_prompt(self.profile, base_system)
        if self.profile in {"layered", "strict"} and self.spotlight_enabled:
            prompt = spotlight(prompt)

        return DefenseDecision(
            prompt=prompt,
            system_prompt=system_prompt,
            stage=self.profile,
            scores=scores,
        )

    def post(self, response: str) -> PostDecision:
        if self.profile not in {"layered", "strict"}:
            return PostDecision(blocked=False)
        result = self.output_filter.check(response)
        if result.blocked:
            return PostDecision(
                blocked=True,
                reason=", ".join(result.reasons),
                stage="output_filter",
            )
        return PostDecision(blocked=False, stage="output_filter")

    @property
    def uses_output_filter(self) -> bool:
        return self.profile in {"layered", "strict"}


def build_defense(name: str, config: dict[str, Any] | None = None) -> DefensePipeline:
    return DefensePipeline(profile=name, config=config)
