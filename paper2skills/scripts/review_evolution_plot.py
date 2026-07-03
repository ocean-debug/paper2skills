"""Render review-loop evolution as a lightweight SVG run artifact."""

from __future__ import annotations

import html
from typing import Any

from common import now_utc
from constants import SCHEMA_VERSION


WIDTH = 760
HEIGHT = 300
PAD_LEFT = 56
PAD_RIGHT = 28
PAD_TOP = 34
PAD_BOTTOM = 52


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def ratio_points(iterations: list[dict[str, Any]]) -> list[tuple[float, float, dict[str, Any]]]:
    if not iterations:
        return []
    plot_w = WIDTH - PAD_LEFT - PAD_RIGHT
    plot_h = HEIGHT - PAD_TOP - PAD_BOTTOM
    count = max(len(iterations) - 1, 1)
    points = []
    for index, item in enumerate(iterations):
        ratio = clamp(float(item.get("score_ratio") or 0.0))
        x = PAD_LEFT + (plot_w * index / count)
        y = PAD_TOP + plot_h * (1.0 - ratio)
        points.append((x, y, item))
    return points


def severity_total(item: dict[str, Any]) -> int:
    counts = item.get("severity_counts") or {}
    return sum(int(value or 0) for value in counts.values())


def circle_color(item: dict[str, Any]) -> str:
    if item.get("passed"):
        return "#166534"
    if item.get("blocking"):
        return "#b91c1c"
    if item.get("patch_changed"):
        return "#1d4ed8"
    return "#6b7280"


def polyline(points: list[tuple[float, float, dict[str, Any]]]) -> str:
    if not points:
        return ""
    values = " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in points)
    return f'<polyline points="{values}" fill="none" stroke="#111827" stroke-width="2.4" />'


def axis_labels() -> str:
    lines = [
        f'<line x1="{PAD_LEFT}" y1="{PAD_TOP}" x2="{PAD_LEFT}" y2="{HEIGHT - PAD_BOTTOM}" stroke="#374151" stroke-width="1" />',
        f'<line x1="{PAD_LEFT}" y1="{HEIGHT - PAD_BOTTOM}" x2="{WIDTH - PAD_RIGHT}" y2="{HEIGHT - PAD_BOTTOM}" stroke="#374151" stroke-width="1" />',
    ]
    for ratio in (0.0, 0.5, 1.0):
        y = PAD_TOP + (HEIGHT - PAD_TOP - PAD_BOTTOM) * (1.0 - ratio)
        lines.append(f'<line x1="{PAD_LEFT}" y1="{y:.1f}" x2="{WIDTH - PAD_RIGHT}" y2="{y:.1f}" stroke="#e5e7eb" stroke-width="1" />')
        lines.append(f'<text x="{PAD_LEFT - 12}" y="{y + 4:.1f}" text-anchor="end" font-size="11" fill="#4b5563">{ratio:.1f}</text>')
    return "\n".join(lines)


def point_marks(points: list[tuple[float, float, dict[str, Any]]]) -> str:
    marks = []
    for x, y, item in points:
        iteration = html.escape(str(item.get("iteration")))
        label = html.escape(str(item.get("gate_reason") or item.get("patch_summary") or "review iteration"))
        score = html.escape(f"{float(item.get('score_ratio') or 0.0):.3f}")
        radius = 5 + min(severity_total(item), 10) * 0.45
        marks.append(
            "\n".join(
                [
                    f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{circle_color(item)}" opacity="0.92">',
                    f"<title>iteration {iteration}: score_ratio={score}; {label}</title>",
                    "</circle>",
                    f'<text x="{x:.1f}" y="{HEIGHT - PAD_BOTTOM + 20}" text-anchor="middle" font-size="11" fill="#4b5563">{iteration}</text>',
                ]
            )
        )
    return "\n".join(marks)


def legend() -> str:
    items = [
        ("#166534", "passed"),
        ("#b91c1c", "blocking"),
        ("#1d4ed8", "patched"),
        ("#6b7280", "no change"),
    ]
    rows = []
    x = PAD_LEFT
    y = HEIGHT - 16
    for color, label in items:
        rows.append(f'<circle cx="{x}" cy="{y - 4}" r="4" fill="{color}" />')
        rows.append(f'<text x="{x + 10}" y="{y}" font-size="11" fill="#374151">{label}</text>')
        x += 92
    return "\n".join(rows)


def render_review_evolution_svg(review_evolution: dict[str, Any]) -> str:
    iterations = review_evolution.get("iterations", [])
    points = ratio_points(iterations)
    title = html.escape(str(review_evolution.get("method_name") or review_evolution.get("package_name") or "review"))
    status = html.escape(str(review_evolution.get("status") or "unknown"))
    stop_reason = html.escape(str(review_evolution.get("stop_reason") or "unknown"))
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="Papert2Skills review evolution plot">',
            '<rect width="100%" height="100%" fill="#ffffff" />',
            f'<text x="{PAD_LEFT}" y="22" font-size="15" font-family="Arial, sans-serif" fill="#111827">{title} review evolution</text>',
            f'<text x="{WIDTH - PAD_RIGHT}" y="22" text-anchor="end" font-size="12" font-family="Arial, sans-serif" fill="#4b5563">status={status}; stop={stop_reason}</text>',
            '<g font-family="Arial, sans-serif">',
            axis_labels(),
            polyline(points),
            point_marks(points),
            legend(),
            f'<text x="{PAD_LEFT + (WIDTH - PAD_LEFT - PAD_RIGHT) / 2:.1f}" y="{HEIGHT - 24}" text-anchor="middle" font-size="11" fill="#4b5563">review iteration</text>',
            f'<text x="18" y="{PAD_TOP + (HEIGHT - PAD_TOP - PAD_BOTTOM) / 2:.1f}" transform="rotate(-90 18,{PAD_TOP + (HEIGHT - PAD_TOP - PAD_BOTTOM) / 2:.1f})" text-anchor="middle" font-size="11" fill="#4b5563">score ratio</text>',
            "</g>",
            "</svg>",
        ]
    )


def build_review_evolution_plot(
    request: dict[str, Any],
    review_evolution: dict[str, Any],
    svg_filename: str = "review_evolution_plot.svg",
) -> dict[str, Any]:
    iterations = review_evolution.get("iterations", [])
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_utc(),
        "package_name": request.get("package_name"),
        "method_name": request.get("method_name") or request.get("package_name"),
        "status": "pass" if iterations else "fail",
        "svg_path": svg_filename,
        "iteration_count": len(iterations),
        "review_status": review_evolution.get("status"),
        "stop_reason": review_evolution.get("stop_reason"),
        "final_score": review_evolution.get("final_score", {}),
        "plot_policy": [
            "The SVG is a run artifact for human review, not a public child-skill file.",
            "The plot is derived only from review_evolution.yaml and does not execute package code.",
            "Point color encodes pass/blocking/patch state; point size encodes total finding count.",
        ],
    }
