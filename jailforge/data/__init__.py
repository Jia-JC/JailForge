"""Dataset loading utilities."""

from __future__ import annotations

from pathlib import Path

from ..schema import Goal
from ..utils import read_jsonl, resolve_path


def load_goals(
    path: str | Path | None = None,
    max_goals: int | None = None,
    categories: list[str] | None = None,
) -> list[Goal]:
    """Load abstract red-team goals from a JSONL file.

    Each row must contain ``id``, ``behavior`` and ``category``. Missing
    optional fields fall back to safe defaults.
    """
    if path is None:
        path = "jailforge/data/seeds_zh.jsonl"
    resolved = resolve_path(path)
    if not resolved.exists():
        raise FileNotFoundError(f"goal dataset not found: {resolved}")
    goals: list[Goal] = []
    for row in read_jsonl(resolved):
        goal = Goal(
            id=str(row["id"]),
            behavior=str(row["behavior"]),
            category=str(row.get("category", "未分类")),
            source=str(row.get("source", "synthetic")),
            language=str(row.get("language", "zh")),
            notes=str(row.get("notes", "")),
        )
        if categories and goal.category not in categories:
            continue
        goals.append(goal)
    if max_goals is not None:
        goals = goals[: max(0, max_goals)]
    return goals


def load_benign(path: str | Path | None = None) -> list[str]:
    """Load benign prompts used to estimate the defense false-positive rate."""
    if path is None:
        path = "jailforge/data/benign_zh.jsonl"
    resolved = resolve_path(path)
    if not resolved.exists():
        raise FileNotFoundError(f"benign dataset not found: {resolved}")
    return [str(row["prompt"]) for row in read_jsonl(resolved) if row.get("prompt")]
