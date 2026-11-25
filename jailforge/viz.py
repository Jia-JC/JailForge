"""Tiny dependency-free SVG charts for the Gradio demo and reports."""

from __future__ import annotations

from html import escape
from typing import Any, Iterable


def _empty(message: str = "暂无数据") -> str:
    return f"<div style='padding:24px;color:#64748b'>{escape(message)}</div>"


def bar_chart_svg(
    labels: list[str],
    values: list[float],
    title: str = "",
    width: int = 760,
    height: int = 360,
    color: str = "#2563eb",
    y_max: float | None = None,
) -> str:
    if not labels:
        return _empty()
    left, right, top, bottom = 64, 24, 42, 96
    plot_w = width - left - right
    plot_h = height - top - bottom
    y_max = y_max if y_max is not None else max(1e-9, max(values) * 1.15)
    y_max = max(y_max, 0.05)
    n = len(labels)
    slot = plot_w / n
    bar_w = slot * 0.56

    parts = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' "
        f"viewBox='0 0 {width} {height}' font-family='ui-sans-serif,system-ui,-apple-system,Segoe UI,Microsoft YaHei,sans-serif'>",
        f"<rect width='{width}' height='{height}' fill='#ffffff'/>",
        f"<text x='{left}' y='24' font-size='15' font-weight='600' fill='#0f172a'>{escape(title)}</text>",
    ]
    for i in range(5):
        value = y_max * i / 4
        y = top + plot_h * (1 - i / 4)
        parts.append(
            f"<line x1='{left}' y1='{y:.1f}' x2='{left + plot_w}' y2='{y:.1f}' stroke='#e2e8f0' stroke-width='1'/>"
        )
        parts.append(
            f"<text x='{left - 8}' y='{y + 4:.1f}' font-size='11' fill='#64748b' text-anchor='end'>{value * 100:.0f}%</text>"
        )
    for index, (label, value) in enumerate(zip(labels, values)):
        value = max(0.0, min(1.0, float(value)))
        x = left + slot * index + (slot - bar_w) / 2
        bar_h = plot_h * (value / y_max)
        y = top + plot_h - bar_h
        parts.append(
            f"<rect x='{x:.1f}' y='{y:.1f}' width='{bar_w:.1f}' height='{max(0.0, bar_h):.1f}' rx='4' fill='{color}' opacity='0.88'/>"
        )
        parts.append(
            f"<text x='{x + bar_w / 2:.1f}' y='{max(top + 10, y - 6):.1f}' font-size='11' fill='#0f172a' text-anchor='middle'>{value * 100:.1f}%</text>"
        )
        short = label if len(label) <= 12 else label[:11] + "…"
        tx = x + bar_w / 2
        ty = top + plot_h + 18
        parts.append(
            f"<text x='{tx:.1f}' y='{ty:.1f}' font-size='11' fill='#334155' text-anchor='end' "
            f"transform='rotate(-28 {tx:.1f} {ty:.1f})'>{escape(short)}</text>"
        )
    parts.append(
        f"<line x1='{left}' y1='{top + plot_h}' x2='{left + plot_w}' y2='{top + plot_h}' stroke='#94a3b8' stroke-width='1'/>"
    )
    parts.append("</svg>")
    return "".join(parts)


def line_chart_svg(
    xs: list[float],
    ys: list[float],
    title: str = "",
    width: int = 760,
    height: int = 340,
    color: str = "#0d9488",
) -> str:
    if not xs or not ys:
        return _empty()
    left, right, top, bottom = 64, 24, 42, 56
    plot_w = width - left - right
    plot_h = height - top - bottom
    x_min, x_max = min(xs), max(xs)
    if x_max == x_min:
        x_max = x_min + 1
    y_max = max(0.1, max(ys) * 1.1)
    points = []
    for x, y in zip(xs, ys):
        px = left + plot_w * (x - x_min) / (x_max - x_min)
        py = top + plot_h * (1 - min(1.0, y / y_max))
        points.append((px, py))
    parts = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' "
        f"viewBox='0 0 {width} {height}' font-family='ui-sans-serif,system-ui,-apple-system,Segoe UI,Microsoft YaHei,sans-serif'>",
        f"<rect width='{width}' height='{height}' fill='#ffffff'/>",
        f"<text x='{left}' y='24' font-size='15' font-weight='600' fill='#0f172a'>{escape(title)}</text>",
    ]
    for i in range(5):
        y = top + plot_h * (1 - i / 4)
        parts.append(
            f"<line x1='{left}' y1='{y:.1f}' x2='{left + plot_w}' y2='{y:.1f}' stroke='#e2e8f0'/>"
        )
        parts.append(
            f"<text x='{left - 8}' y='{y + 4:.1f}' font-size='11' fill='#64748b' text-anchor='end'>{y_max * i / 4:.2f}</text>"
        )
    path = " ".join(
        ("M" if index == 0 else "L") + f"{x:.1f},{y:.1f}"
        for index, (x, y) in enumerate(points)
    )
    parts.append(f"<path d='{path}' fill='none' stroke='{color}' stroke-width='2.5' stroke-linejoin='round'/>")
    for x, y in points:
        parts.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='3.5' fill='{color}'/>")
    for index, (x, _) in enumerate(points):
        parts.append(
            f"<text x='{x:.1f}' y='{top + plot_h + 18:.1f}' font-size='10' fill='#64748b' text-anchor='middle'>{xs[index]:g}</text>"
        )
    parts.append("</svg>")
    return "".join(parts)


def summary_bar_chart(summary: dict[str, Any]) -> str:
    stats = summary.get("by_defense", {})
    labels = list(stats.keys())
    values = [stats[label].get("asr", 0.0) for label in labels]
    return bar_chart_svg(labels, values, title="各防御配置下的 ASR")


def method_bar_chart(summary: dict[str, Any]) -> str:
    stats = summary.get("by_method", {})
    labels = list(stats.keys())
    values = [stats[label].get("asr", 0.0) for label in labels]
    return bar_chart_svg(labels, values, title="各攻击方法的 ASR")


def evolution_chart(history: Iterable[dict[str, Any]]) -> str:
    rows = list(history)
    xs = [float(row.get("generation", index)) for index, row in enumerate(rows)]
    ys = [float(row.get("best_fitness", 0.0)) for row in rows]
    return line_chart_svg(xs, ys, title="进化攻击：每代最佳适应度")
