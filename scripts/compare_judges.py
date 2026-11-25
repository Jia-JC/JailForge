"""Compare the rule judge with the LLM judge on an existing real-model run.

The rule judge is cheap but can be fooled by English reasoning traces or by
responses that merely mention sensitive words. This script re-judges the stored
responses with :class:`RuleJudge` and reports ASR under both judges, so the
report can quantify the discrepancy without extra API calls.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from jailforge.judge.rule_judge import RuleJudge
from jailforge.schema import Goal


def _stats(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    n = len(rows)
    success = sum(1 for row in rows if row[key])
    return {"n": n, "success": success, "asr": round(success / n, 4) if n else 0.0}


def compare(run_dir: Path) -> dict[str, Any]:
    trials_path = run_dir / "trials.jsonl"
    if not trials_path.exists():
        raise FileNotFoundError(trials_path)
    rule = RuleJudge()
    rows: list[dict[str, Any]] = []
    for line in trials_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        goal = Goal(
            id=record["goal_id"],
            behavior=record["goal"],
            category=record["category"],
        )
        result = rule.judge(goal, record.get("prompt", ""), record.get("response", ""))
        rows.append(
            {
                **record,
                "rule_success": bool(result.success),
                "rule_score": result.score,
                "rule_rationale": result.rationale,
            }
        )

    def group(key: str) -> dict[str, Any]:
        buckets: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            buckets.setdefault(row[key], []).append(row)
        return {
            name: {
                "llm": _stats(bucket, "judge_success"),
                "rule": _stats(bucket, "rule_success"),
            }
            for name, bucket in buckets.items()
        }

    disagreements = [
        {
            "goal_id": row["goal_id"],
            "method": row["method"],
            "defense": row["defense"],
            "llm_success": row["judge_success"],
            "rule_success": row["rule_success"],
            "rule_score": row["rule_score"],
            "llm_rationale": row.get("judge_rationale", ""),
        }
        for row in rows
        if bool(row["judge_success"]) != bool(row["rule_success"])
    ]

    return {
        "run_dir": str(run_dir),
        "n": len(rows),
        "overall": {
            "llm": _stats(rows, "judge_success"),
            "rule": _stats(rows, "rule_success"),
        },
        "by_method": group("method"),
        "by_defense": group("defense"),
        "disagreements": disagreements[:20],
        "n_disagreements": len(disagreements),
    }


def to_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 规则评判 vs LLM 评判",
        "",
        f"- 运行目录：`{payload['run_dir']}`",
        f"- 样本数：{payload['n']}",
        f"- 一致 / 分歧：{payload['n'] - payload['n_disagreements']} / {payload['n_disagreements']}",
        "",
        "| 口径 | 成功数 | ASR |",
        "| --- | --- | --- |",
        f"| LLM judge | {payload['overall']['llm']['success']} | {payload['overall']['llm']['asr'] * 100:.1f}% |",
        f"| 规则 judge | {payload['overall']['rule']['success']} | {payload['overall']['rule']['asr'] * 100:.1f}% |",
        "",
        "## 按攻击方法",
        "",
        "| 方法 | n | LLM ASR | 规则 ASR |",
        "| --- | --- | --- | --- |",
    ]
    for name, stats in payload["by_method"].items():
        lines.append(
            f"| {name} | {stats['llm']['n']} | {stats['llm']['asr'] * 100:.1f}% | "
            f"{stats['rule']['asr'] * 100:.1f}% |"
        )
    lines.extend(
        [
            "",
            "## 按防御",
            "",
            "| 防御 | n | LLM ASR | 规则 ASR |",
            "| --- | --- | --- | --- |",
        ]
    )
    for name, stats in payload["by_defense"].items():
        lines.append(
            f"| {name} | {stats['llm']['n']} | {stats['llm']['asr'] * 100:.1f}% | "
            f"{stats['rule']['asr'] * 100:.1f}% |"
        )
    if payload["disagreements"]:
        lines.extend(
            [
                "",
                "## 分歧样例（前 20 条，不含回答正文）",
                "",
                "| 目标 | 方法 | 防御 | LLM | 规则 | 规则分 |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for row in payload["disagreements"]:
            lines.append(
                f"| {row['goal_id']} | {row['method']} | {row['defense']} | "
                f"{row['llm_success']} | {row['rule_success']} | {row['rule_score']:.2f} |"
            )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--md-out", type=Path)
    args = parser.parse_args()
    payload = compare(args.run_dir)
    json_path = args.json_out or args.run_dir / "judge_comparison.json"
    md_path = args.md_out or args.run_dir / "judge_comparison.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(to_markdown(payload), encoding="utf-8")
    print(to_markdown(payload))
    print(f"written: {json_path}")
    print(f"written: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
