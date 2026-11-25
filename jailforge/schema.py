"""Typed records shared by the attack, defense, judge and evaluation layers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Goal:
    """One abstract harmful-behaviour probe.

    ``behavior`` is a request intent (for example "write a phishing script"),
    never an operational recipe. The dataset is a red-team probe set, not a
    corpus of harmful instructions.
    """

    id: str
    behavior: str
    category: str
    source: str = "synthetic"
    language: str = "zh"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AttackPrompt:
    goal_id: str
    method: str
    text: str
    family: str = "semantic"
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DefenseDecision:
    """Result of the pre-generation defense stages."""

    blocked: bool = False
    stage: str = "none"
    reason: str = ""
    prompt: str = ""
    system_prompt: str | None = None
    scores: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ModelResponse:
    text: str
    model: str
    latency_ms: float = 0.0
    error: str | None = None
    cached: bool = False

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class JudgeResult:
    success: bool
    score: float
    rationale: str
    judge: str = "rule"
    severity: int = 0
    confidence: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Trial:
    """One (goal, attack, defense, model) cell of the evaluation matrix."""

    goal: Goal
    attack: AttackPrompt
    defense: str
    decision: DefenseDecision
    response: ModelResponse
    judge: JudgeResult
    elapsed_ms: float = 0.0
    output_blocked: bool = False
    output_reason: str = ""

    @property
    def blocked(self) -> bool:
        return self.decision.blocked

    @property
    def valid(self) -> bool:
        return self.response.error is None and not self.blocked

    @property
    def success(self) -> bool:
        """A trial counts as a jailbreak only if it was not blocked at any
        stage and the judge marked the response as compliant with the goal."""
        return bool(self.valid and not self.output_blocked and self.judge.success)

    def to_record(self) -> dict[str, Any]:
        """Flat JSON-serialisable record, safe to write to JSONL/CSV."""
        return {
            "goal_id": self.goal.id,
            "goal": self.goal.behavior,
            "category": self.goal.category,
            "method": self.attack.method,
            "attack_family": self.attack.family,
            "defense": self.defense,
            "blocked": self.blocked,
            "block_stage": self.decision.stage,
            "block_reason": self.decision.reason,
            "output_blocked": self.output_blocked,
            "output_reason": self.output_reason,
            "prompt": self.attack.text,
            "response": self.response.text,
            "model": self.response.model,
            "error": self.response.error,
            "judge_success": self.judge.success,
            "judge_score": round(self.judge.score, 4),
            "judge_rationale": self.judge.rationale,
            "judge_name": self.judge.judge,
            "valid": self.valid,
            "success": self.success,
            "latency_ms": round(self.response.latency_ms, 2),
            "elapsed_ms": round(self.elapsed_ms, 2),
            "cached": self.response.cached,
        }
