"""Matplotlib chart builders for management reporting."""

from __future__ import annotations

from io import BytesIO
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator


LIFECYCLE_COLORS = {
    "started": "#2563EB",
    "submitted": "#C026D3",
    "returned": "#0F9D9A",
    "completed": "#16A34A",
}
NEUTRAL_COLORS = ("#475569", "#64748B", "#94A3B8", "#CBD5E1")
CHART_BACKGROUND = "#0E1117"
CHART_GRID = "#334155"
CHART_TEXT = "#E2E8F0"
CHART_MUTED_TEXT = "#94A3B8"
TREND_COLORS = ("#2563EB", "#C026D3", "#0F9D9A", "#16A34A", "#F59E0B", "#EC4899")
PRINT_BACKGROUND = "#FFFFFF"
PRINT_GRID = "#CBD5E1"
PRINT_TEXT = "#0F172A"
PRINT_MUTED_TEXT = "#475569"


def _style_colors(print_friendly: bool) -> tuple[str, str, str, str]:
    if print_friendly:
        return PRINT_BACKGROUND, PRINT_GRID, PRINT_TEXT, PRINT_MUTED_TEXT
    return CHART_BACKGROUND, CHART_GRID, CHART_TEXT, CHART_MUTED_TEXT


def _figure(width: float = 8.6, height: float = 4.2, *, print_friendly: bool = False):
    background, grid, text, muted_text = _style_colors(print_friendly)
    figure, axis = plt.subplots(figsize=(width, height))
    figure.patch.set_facecolor(background)
    axis.set_facecolor(background)
    axis.spines[["top", "right"]].set_visible(False)
    axis.spines[["left", "bottom"]].set_color(muted_text)
    axis.tick_params(colors=text)
    axis.xaxis.label.set_color(text)
    axis.yaxis.label.set_color(text)
    axis.grid(axis="y", color=grid, linewidth=0.8)
    axis.set_axisbelow(True)
    return figure, axis


def _finish(figure):
    figure.tight_layout()
    return figure


def grouped_columns(
    rows: list[dict],
    fields: list[tuple[str, str, str]],
    *,
    title: str | None = None,
    ylabel: str = "Tasks",
    print_friendly: bool = False,
):
    _, _, text, _ = _style_colors(print_friendly)
    figure, axis = _figure(print_friendly=print_friendly)
    labels = [row["label"] for row in rows]
    positions = list(range(len(rows)))
    width = 0.8 / max(len(fields), 1)
    maximum_value = 0
    for index, (field, label, color) in enumerate(fields):
        offset = (index - (len(fields) - 1) / 2) * width
        values = [row.get(field, 0) for row in rows]
        maximum_value = max(maximum_value, *values)
        bars = axis.bar([position + offset for position in positions], values, width, label=label, color=color)
        axis.bar_label(bars, padding=2, fontsize=8, color=text)
    axis.set_ylabel(ylabel)
    axis.set_ylim(0, maximum_value + 2)
    axis.yaxis.set_major_locator(MaxNLocator(integer=True))
    axis.set_xticks(positions, labels, rotation=30, ha="right")
    axis.legend(ncol=min(len(fields), 4), frameon=False, fontsize=8, labelcolor=text)
    return _finish(figure)


def workload_bars(rows: list[dict], *, print_friendly: bool = False):
    _, _, text, _ = _style_colors(print_friendly)
    figure, axis = _figure(height=max(3.2, len(rows) * 0.55 + 1.5), print_friendly=print_friendly)
    labels = [row["investigator"] for row in rows]
    positions = list(range(len(rows)))
    average = [row["average"] for row in rows]
    peak = [row["peak"] for row in rows]
    bars_average = axis.barh([position + 0.18 for position in positions], average, 0.35, label="Average", color="#475569")
    bars_peak = axis.barh([position - 0.18 for position in positions], peak, 0.35, label="Peak", color="#94A3B8")
    axis.bar_label(bars_average, padding=3, fontsize=8, color=text)
    axis.bar_label(bars_peak, padding=3, fontsize=8, color=text)
    axis.set_xlabel("Active tasks")
    axis.set_yticks(positions, labels)
    axis.legend(frameon=False, fontsize=8, labelcolor=text)
    return _finish(figure)


def workload_trend(row: dict, *, print_friendly: bool = False):
    _, _, text, _ = _style_colors(print_friendly)
    figure, axis = _figure(print_friendly=print_friendly)
    labels = [item["label"] for item in row["trend"]]
    average = [item["average"] for item in row["trend"]]
    peak = [item["peak"] for item in row["trend"]]
    positions = list(range(len(labels)))
    axis.plot(positions, average, marker="o", color="#475569", label="Average")
    axis.plot(positions, peak, marker="o", color="#94A3B8", label="Peak")
    axis.set_ylabel("Active tasks")
    axis.set_xticks(positions, labels, rotation=30, ha="right")
    axis.legend(frameon=False, fontsize=8, labelcolor=text)
    return _finish(figure)


def trend_lines(
    rows: list[dict],
    fields: list[tuple[str, str, str]],
    *,
    ylabel: str,
    print_friendly: bool = False,
    integer_y: bool = False,
    non_negative: bool = False,
):
    _, _, text, _ = _style_colors(print_friendly)
    figure, axis = _figure(print_friendly=print_friendly)
    positions = list(range(len(rows)))
    labels = [row["label"] for row in rows]
    for field, label, color in fields:
        values = [row.get(field) for row in rows]
        axis.plot(positions, values, marker="o", linewidth=2, color=color, label=label)
    axis.set_ylabel(ylabel)
    if non_negative:
        maximum = max(
            (value for row in rows for field, _, _ in fields if (value := row.get(field)) is not None),
            default=0,
        )
        axis.set_ylim(0, maximum + 2)
    if integer_y:
        axis.yaxis.set_major_locator(MaxNLocator(integer=True))
    axis.set_xticks(positions, labels, rotation=30, ha="right")
    axis.legend(frameon=False, fontsize=8, labelcolor=text, ncol=min(len(fields), 3))
    return _finish(figure)


def assignment_readiness(rows: list[dict], *, print_friendly: bool = False):
    _, _, text, _ = _style_colors(print_friendly)
    figure, axis = _figure(print_friendly=print_friendly)
    labels = [row["label"] for row in rows]
    positions = list(range(len(rows)))
    event_fields = (
        ("new_assignments", "New assignments", "#475569"),
        ("reassignments", "Reassignments", "#F59E0B"),
        ("started", "Started", LIFECYCLE_COLORS["started"]),
    )
    width = 0.18
    maximum = 0
    for index, (field, label, color) in enumerate(event_fields):
        offset = (index - 1) * width
        values = [row.get(field, 0) for row in rows]
        maximum = max(maximum, *values)
        axis.bar([position + offset for position in positions], values, width, label=label, color=color)
    for field, label, color in (
        ("unassigned", "Unassigned", "#DC2626"),
        ("assigned_not_started", "Assigned, not started", "#F59E0B"),
    ):
        values = [row.get(field, 0) for row in rows]
        maximum = max(maximum, *values)
        axis.plot(positions, values, marker="o", linewidth=2, color=color, label=label)
    axis.set_ylabel("Tasks")
    axis.set_ylim(0, maximum + 2)
    axis.yaxis.set_major_locator(MaxNLocator(integer=True))
    axis.set_xticks(positions, labels, rotation=30, ha="right")
    axis.legend(ncol=3, frameon=False, fontsize=8, labelcolor=text)
    return _finish(figure)


def complexity_trends(rows: list[dict], *, print_friendly: bool = False):
    background, grid, text, muted_text = _style_colors(print_friendly)
    figure, axes = plt.subplots(2, 1, figsize=(8.6, 5.5), sharex=True)
    figure.patch.set_facecolor(background)
    positions = list(range(len(rows)))
    labels = [row["label"] for row in rows]
    for axis, field, label, color in (
        (axes[0], "subjects_per_task", "Subjects per active task", "#2563EB"),
        (axes[1], "findings_per_task", "Findings per active task", "#C026D3"),
    ):
        axis.set_facecolor(background)
        axis.spines[["top", "right"]].set_visible(False)
        axis.spines[["left", "bottom"]].set_color(muted_text)
        axis.tick_params(colors=text)
        axis.grid(axis="y", color=grid, linewidth=0.8)
        axis.set_axisbelow(True)
        axis.plot(
            positions,
            [row.get(field) for row in rows],
            marker="o",
            linewidth=2,
            color=color,
        )
        axis.set_ylabel(label, color=text)
    axes[1].set_xticks(positions, labels, rotation=30, ha="right")
    return _finish(figure)


def duration_bars(rows: list[dict]):
    figure, axis = _figure(height=max(3.2, len(rows) * 0.7 + 1.5))
    labels = [row["interval"] for row in rows]
    positions = list(range(len(rows)))
    averages = [row["average_days"] for row in rows]
    medians = [row["median_days"] for row in rows]
    bars_average = axis.barh([position + 0.18 for position in positions], averages, 0.35, label="Average", color="#475569")
    bars_median = axis.barh([position - 0.18 for position in positions], medians, 0.35, label="Median", color="#94A3B8")
    axis.bar_label(bars_average, fmt="%.1f", padding=3, fontsize=8, color=CHART_TEXT)
    axis.bar_label(bars_median, fmt="%.1f", padding=3, fontsize=8, color=CHART_TEXT)
    axis.set_xlabel("Days")
    axis.set_yticks(positions, labels)
    axis.legend(frameon=False, fontsize=8, labelcolor=CHART_TEXT)
    return _finish(figure)


def complexity_columns(complexity: dict):
    figure, axis = _figure(width=5.5)
    labels = ["Subjects", "Findings"]
    values = [complexity["subjects"], complexity["findings"]]
    bars = axis.bar(labels, values, color=NEUTRAL_COLORS[:2])
    axis.bar_label(bars, padding=3, fontsize=9, color=CHART_TEXT)
    axis.set_ylabel("Average per task" if complexity["mode"] == "average" else "Total")
    return _finish(figure)


def persona_bars(rows: list[dict]):
    figure, axis = _figure(height=max(3.2, len(rows) * 0.45 + 1.5))
    labels = [row["persona"] for row in rows]
    values = [row["active_investigations"] for row in rows]
    bars = axis.barh(range(len(rows)), values, color="#475569")
    axis.bar_label(bars, padding=3, fontsize=8, color=CHART_TEXT)
    axis.set_xlabel("Distinct active investigations")
    axis.set_yticks(range(len(rows)), labels)
    return _finish(figure)


def png_bytes(figure) -> bytes:
    output = BytesIO()
    figure.savefig(output, format="png", dpi=180, bbox_inches="tight")
    plt.close(figure)
    return output.getvalue()
