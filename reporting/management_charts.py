"""Matplotlib chart builders for management reporting."""

from __future__ import annotations

from io import BytesIO
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


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


def _figure(width: float = 8.6, height: float = 4.2):
    figure, axis = plt.subplots(figsize=(width, height))
    figure.patch.set_facecolor(CHART_BACKGROUND)
    axis.set_facecolor(CHART_BACKGROUND)
    axis.spines[["top", "right"]].set_visible(False)
    axis.spines[["left", "bottom"]].set_color(CHART_MUTED_TEXT)
    axis.tick_params(colors=CHART_TEXT)
    axis.xaxis.label.set_color(CHART_TEXT)
    axis.yaxis.label.set_color(CHART_TEXT)
    axis.grid(axis="y", color=CHART_GRID, linewidth=0.8)
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
    ylabel: str = "Cases",
):
    figure, axis = _figure()
    labels = [row["label"] for row in rows]
    positions = list(range(len(rows)))
    width = 0.8 / max(len(fields), 1)
    for index, (field, label, color) in enumerate(fields):
        offset = (index - (len(fields) - 1) / 2) * width
        values = [row.get(field, 0) for row in rows]
        bars = axis.bar([position + offset for position in positions], values, width, label=label, color=color)
        axis.bar_label(bars, padding=2, fontsize=8, color=CHART_TEXT)
    axis.set_ylabel(ylabel)
    axis.set_xticks(positions, labels, rotation=30, ha="right")
    axis.legend(ncol=min(len(fields), 4), frameon=False, fontsize=8, labelcolor=CHART_TEXT)
    return _finish(figure)


def workload_bars(rows: list[dict]):
    figure, axis = _figure(height=max(3.2, len(rows) * 0.55 + 1.5))
    labels = [row["investigator"] for row in rows]
    positions = list(range(len(rows)))
    average = [row["average"] for row in rows]
    peak = [row["peak"] for row in rows]
    bars_average = axis.barh([position + 0.18 for position in positions], average, 0.35, label="Average", color="#475569")
    bars_peak = axis.barh([position - 0.18 for position in positions], peak, 0.35, label="Peak", color="#94A3B8")
    axis.bar_label(bars_average, padding=3, fontsize=8, color=CHART_TEXT)
    axis.bar_label(bars_peak, padding=3, fontsize=8, color=CHART_TEXT)
    axis.set_xlabel("Active cases")
    axis.set_yticks(positions, labels)
    axis.legend(frameon=False, fontsize=8, labelcolor=CHART_TEXT)
    return _finish(figure)


def workload_trend(row: dict):
    figure, axis = _figure()
    labels = [item["label"] for item in row["trend"]]
    average = [item["average"] for item in row["trend"]]
    peak = [item["peak"] for item in row["trend"]]
    positions = list(range(len(labels)))
    axis.plot(positions, average, marker="o", color="#475569", label="Average")
    axis.plot(positions, peak, marker="o", color="#94A3B8", label="Peak")
    axis.set_ylabel("Active cases")
    axis.set_xticks(positions, labels, rotation=30, ha="right")
    axis.legend(frameon=False, fontsize=8, labelcolor=CHART_TEXT)
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
    axis.set_ylabel("Average per case" if complexity["mode"] == "average" else "Total")
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
