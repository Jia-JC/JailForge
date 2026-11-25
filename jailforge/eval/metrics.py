"""Evaluation metrics: ASR, Wilson intervals and defense drop."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Iterable

from ..schema import Trial


def wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion."""
    if n <= 0:
        return (0.0, 0.0)
    p = successes / n
    denominator = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    margin = (
        z
        * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
        / denominator
    )
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def group_stats(trials: Iterable[Trial]) -> dict[str, Any]:
    trials = list(trials)
    n = len(trials)
    errors = sum(1 for trial in trials if trial.response.error)
    blocked = sum(1 for trial in trials if trial.blocked)
    output_blocked = sum(1 for trial in trials if trial.output_blocked)
    successes = sum(1 for trial in trials if trial.success)
    valid = n - errors
    asr = successes / valid if valid else 0.0
    low, high = wilson_ci(successes, valid)
    latencies = [
        trial.response.latency_ms
        for trial in trials
        if trial.response.latency_ms and not trial.response.cached
    ]
    return {
        "n": n,
        "valid": valid,
        "success": successes,
        "asr": round(asr, 4),
        "asr_ci95": [round(low, 4), round(high, 4)],
        "blocked": blocked,
        "output_blocked": output_blocked,
        "errors": errors,
        "block_rate": round(blocked / n, 4) if n else 0.0,
        "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
    }


def summarize(
    trials: Iterable[Trial],
    fpr: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    trials = list(trials)
    by_method: dict[str, list[Trial]] = defaultdict(list)
    by_defense: dict[str, list[Trial]] = defaultdict(list)
    by_category: dict[str, list[Trial]] = defaultdict(list)
    for trial in trials:
        by_method[trial.attack.method].append(trial)
        by_defense[trial.defense].append(trial)
        by_category[trial.goal.category].append(trial)

    method_stats = {name: group_stats(group) for name, group in by_method.items()}
    defense_stats = {name: group_stats(group) for name, group in by_defense.items()}
    category_stats = {name: group_stats(group) for name, group in by_category.items()}

    matrix: dict[str, dict[str, float]] = {}
    for method in method_stats:
        matrix[method] = {}
        for defense in defense_stats:
            cell = [
                trial
                for trial in trials
                if trial.attack.method == method and trial.defense == defense
            ]
            matrix[method][defense] = group_stats(cell)["asr"]

    baseline = defense_stats.get("none", {}).get("asr", 0.0)
    defense_drop: dict[str, dict[str, float]] = {}
    for defense, stats in defense_stats.items():
        absolute = baseline - stats["asr"]
        relative = absolute / baseline if baseline > 0 else 0.0
        defense_drop[defense] = {
            "absolute": round(absolute, 4),
            "relative": round(relative, 4),
        }

    drop_by_method: dict[str, dict[str, float]] = {}
    for method, cells in matrix.items():
        base = cells.get("none", 0.0)
        drop_by_method[method] = {
            defense: round(base - asr, 4) for defense, asr in cells.items()
        }

    return {
        "overall": group_stats(trials),
        "by_method": method_stats,
        "by_defense": defense_stats,
        "by_category": category_stats,
        "matrix": matrix,
        "defense_drop": defense_drop,
        "defense_drop_by_method": drop_by_method,
        "fpr": fpr or {},
        "meta": meta or {},
    }


def format_summary_table(summary: dict[str, Any]) -> str:
    """Render the method x defense ASR matrix as a markdown table."""
    defenses = list(summary.get("by_defense", {}).keys())
    methods = list(summary.get("by_method", {}).keys())
    if not defenses or not methods:
        return "_没有可展示的结果。_"
    header = "| 攻击方法 | " + " | ".join(defenses) + " |"
    separator = "| --- | " + " | ".join("---" for _ in defenses) + " |"
    rows = [header, separator]
    for method in methods:
        cells = [f"{summary['matrix'][method].get(d, 0.0) * 100:.1f}%" for d in defenses]
        rows.append(f"| {method} | " + " | ".join(cells) + " |")
    overall = summary.get("overall", {})
    rows.append(
        f"| **总体 ASR** | "
        + " | ".join(
            f"{summary['by_defense'][d]['asr'] * 100:.1f}%" for d in defenses
        )
        + " |"
    )
    rows.append("")
    rows.append(
        f"有效样本 {overall.get('valid', 0)} / {overall.get('n', 0)}，"
        f"错误 {overall.get('errors', 0)}，总体 ASR {overall.get('asr', 0) * 100:.1f}% "
        f"(95% CI {overall.get('asr_ci95', [0, 0])[0] * 100:.1f}%–"
        f"{overall.get('asr_ci95', [0, 0])[1] * 100:.1f}%)。"
    )
    return "\n".join(rows)
