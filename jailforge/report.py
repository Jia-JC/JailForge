"""Markdown report rendering from a run summary."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .eval.metrics import format_summary_table
from .schema import Trial
from .utils import truncate


def _cell(value: Any) -> str:
    text = str(value).replace("|", "\\|").replace("\n", " ")
    return text


def _table(headers: list[str], rows: Iterable[Iterable[Any]]) -> str:
    lines = [
        "| " + " | ".join(_cell(h) for h in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_cell(cell) for cell in row) + " |")
    return "\n".join(lines)


def render_run_report(
    summary: dict[str, Any],
    config: dict[str, Any],
    trials: list[Trial],
    output_dir: str | Path,
) -> str:
    meta = summary.get("meta", {})
    provider = str(meta.get("provider", ""))
    model = str(meta.get("model", ""))
    run_cfg = config.get("run", {})
    lines: list[str] = []
    lines.append(f"# JailForge 评测报告：{run_cfg.get('name', 'run')}")
    lines.append("")
    lines.append(f"- 生成时间：{meta.get('timestamp', '')}")
    lines.append(f"- 目标模型：`{model}`（provider=`{provider}`）")
    lines.append(f"- 随机种子：{meta.get('seed', '')}")
    lines.append(f"- 目标数量：{meta.get('n_goals', '')}")
    lines.append(f"- 攻击方法：{', '.join(meta.get('methods', []))}")
    lines.append(f"- 防御配置：{', '.join(meta.get('defenses', []))}")
    lines.append(f"- 输出目录：`{output_dir}`")
    lines.append("")

    if provider == "mock":
        lines.append(
            "> ⚠️ **重要说明**：本次结果由离线 `MockLLM` 产生，只用于验证"
            "“攻击生成 → 防御 → 推理 → 评判 → 统计”的流水线是否连通。"
            "其中的 ASR 是合成数据，**不能**用来评价任何真实模型的安全水平。"
        )
        lines.append("")

    overall = summary.get("overall", {})
    ci = overall.get("asr_ci95", [0.0, 0.0])
    lines.append("## 1. 总体结果")
    lines.append("")
    lines.append(
        f"有效样本 **{overall.get('valid', 0)} / {overall.get('n', 0)}**，"
        f"总体 ASR **{overall.get('asr', 0) * 100:.1f}%** "
        f"(95% Wilson CI {ci[0] * 100:.1f}%–{ci[1] * 100:.1f}%)，"
        f"输入拦截 {overall.get('blocked', 0)} 条，"
        f"输出拦截 {overall.get('output_blocked', 0)} 条，"
        f"调用错误 {overall.get('errors', 0)} 条。"
    )
    lines.append("")
    lines.append("## 2. 攻击方法 × 防御配置")
    lines.append("")
    lines.append(format_summary_table(summary))
    lines.append("")

    lines.append("## 3. 防御收益")
    lines.append("")
    rows = []
    for defense, drop in summary.get("defense_drop", {}).items():
        stats = summary.get("by_defense", {}).get(defense, {})
        rows.append(
            [
                defense,
                f"{stats.get('asr', 0) * 100:.1f}%",
                f"{drop.get('absolute', 0) * 100:.1f} pp",
                f"{drop.get('relative', 0) * 100:.1f}%",
                f"{stats.get('block_rate', 0) * 100:.1f}%",
            ]
        )
    lines.append(_table(["防御", "ASR", "绝对下降", "相对下降", "输入拦截率"], rows))
    lines.append("")

    lines.append("## 4. 分类别 ASR（无防御基线）")
    lines.append("")
    rows = []
    for category, stats in summary.get("by_category", {}).items():
        rows.append(
            [category, stats.get("n", 0), f"{stats.get('asr', 0) * 100:.1f}%"]
        )
    lines.append(_table(["类别", "样本数", "ASR"], rows))
    lines.append("")

    fpr = summary.get("fpr", {})
    if fpr:
        lines.append("## 5. 良性样本误拦率（FPR）")
        lines.append("")
        rows = []
        for defense, stats in fpr.items():
            rows.append(
                [
                    defense,
                    stats.get("n", 0),
                    stats.get("blocked", 0),
                    f"{stats.get('fpr', 0) * 100:.1f}%",
                ]
            )
        lines.append(_table(["防御", "良性样本", "误拦", "FPR"], rows))
        lines.append("")

    lines.append("## 6. 样例（截断）")
    lines.append("")
    rows = []
    for trial in trials[:12]:
        rows.append(
            [
                trial.goal.id,
                trial.attack.method,
                trial.defense,
                "是" if trial.blocked else "否",
                "是" if trial.success else "否",
                f"{trial.judge.score:.2f}",
                truncate(trial.response.text, 80),
            ]
        )
    lines.append(
        _table(
            ["目标", "攻击", "防御", "输入拦截", "越狱成功", "评判分", "模型回答（截断）"],
            rows,
        )
    )
    lines.append("")

    lines.append("## 7. 复现")
    lines.append("")
    config_path = config.get("_meta", {}).get("config_path", "configs/mock_quick.yaml")
    lines.append("```bash")
    lines.append(f"python -m jailforge run --config {config_path}")
    lines.append("```")
    lines.append("")
    lines.append("## 8. 解释边界")
    lines.append("")
    lines.append(
        "- 规则评判器基于拒答词/配合词/风险词启发式，存在误判；接入真实模型时应同时报告 LLM judge 与人工抽检结果。"
    )
    lines.append(
        "- ASR 是“评判器判定为配合”的比例，不等于真实世界中造成了伤害；本数据集只含抽象目标，不含可操作细节。"
    )
    lines.append(
        "- 防御收益需要与良性样本误拦率一起看：过于激进的过滤会显著损害正常可用性。"
    )
    lines.append("")
    return "\n".join(lines)
