"""Attack strategy abstraction and registry helpers."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

from ..schema import AttackPrompt, Goal


@dataclass(frozen=True)
class AttackMethod:
    """A stateless prompt-transformation strategy.

    ``builder`` receives the abstract goal and a seeded RNG, and returns the
    final user prompt. Builders must never add operational harmful detail.
    """

    name: str
    family: str
    description: str
    builder: Callable[[Goal, random.Random], str]

    def generate(self, goal: Goal, rng: random.Random) -> AttackPrompt:
        text = self.builder(goal, rng)
        return AttackPrompt(
            goal_id=goal.id,
            method=self.name,
            text=text,
            family=self.family,
            meta={"description": self.description},
        )


def list_attacks(registry: dict[str, AttackMethod]) -> list[dict[str, str]]:
    return [
        {"name": m.name, "family": m.family, "description": m.description}
        for m in registry.values()
    ]


def get_attack(registry: dict[str, AttackMethod], name: str) -> AttackMethod:
    try:
        return registry[name]
    except KeyError as exc:
        available = ", ".join(sorted(registry))
        raise KeyError(f"unknown attack method '{name}'. Available: {available}") from exc
