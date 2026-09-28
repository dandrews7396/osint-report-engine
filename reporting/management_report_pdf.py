"""A4 landscape PDF rendering for management reporting."""

from __future__ import annotations

import base64
from html import escape

from weasyprint import HTML

from reporting import management_charts as charts


def _image(figure) -> str:
    encoded = base64.b64encode(charts.png_bytes(figure)).decode("ascii")
    return f'<img class="chart" src="data:image/png;base64,{encoded}" alt="">'


def _table(rows: list[dict], *, header_tone: str = "teal") -> str:
    if not rows:
        return "<p>No data is available for this period.</p>"
    if header_tone not in {"neutral", "teal", "indigo"}:
        raise ValueError("Unsupported table header tone.")
    headers = list(rows[0])
    header_html = "".join(f"<th>{escape(header)}</th>" for header in headers)
    body_html = "".join(
        "<tr>"
        + "".join(f"<td>{escape(str(row.get(header, '')))}</td>" for header in headers)
        + "</tr>"
        for row in rows
    )
    return (
        f'<table class="table-header-{header_tone}">'
        f"<thead><tr>{header_html}</tr></thead><tbody>{body_html}</tbody></table>"
    )


def _section(title: str, subtitle: str, content: str) -> str:
    return (
        '<section class="report-section">'
        f"<h2>{escape(title)}</h2><p class=\"subtitle\">{escape(subtitle)}</p>{content}</section>"
    )


def render_management_report_pdf(
    report: dict,
    *,
    scope_label: str,
    period_label: str,
    selected_sections: set[str],
    table_header_tones: dict[str, str] | None = None,
) -> bytes:
    """Render the approved printable subset; manager attention is never included."""
    contents = []
    sections = []
    table_header_tones = table_header_tones or {}

    def table(rows: list[dict], section: str) -> str:
        return _table(rows, header_tone=table_header_tones.get(section, "teal"))

    contents.append("Executive Summary")
    sections.append(
        _section(
            "Executive Summary",
            "Aggregate management information for Senior Leadership and statistical reporting.",
            table(report["executive_summary"], "executive_summary"),
        )
    )
    if "throughput" in selected_sections:
        contents.append("Lifecycle Throughput")
        sections.append(
            _section(
                "Lifecycle Throughput",
                "Tasks crossing each lifecycle gate in the selected period.",
                _image(charts.grouped_columns(
                    report["buckets"],
                    [
                        ("started", "Started", charts.LIFECYCLE_COLORS["started"]),
                        ("submitted", "Submitted", charts.LIFECYCLE_COLORS["submitted"]),
                        ("returned", "Returned", charts.LIFECYCLE_COLORS["returned"]),
                        ("completed", "Completed", charts.LIFECYCLE_COLORS["completed"]),
                    ],
                    title="Lifecycle Throughput",
                    print_friendly=True,
                )),
            )
        )
    if "task_flow" in selected_sections:
        contents.append("Assignment and Start Readiness")
        sections.append(
            _section(
                "Assignment and Start Readiness",
                "Assignment activity and the period-end preparation backlog.",
                _image(charts.assignment_readiness(
                    report["buckets"],
                    print_friendly=True,
                ))
                + table(
                    [
                        {
                            "Measure": "Preparation backlog at period end",
                            "Tasks": report["assignment_flow"]["preparation_backlog"],
                        },
                        {
                            "Measure": "Unassigned at period end",
                            "Tasks": report["assignment_flow"]["unassigned"],
                        },
                        {
                            "Measure": "Assigned but not started at period end",
                            "Tasks": report["assignment_flow"]["assigned_not_started"],
                        },
                    ],
                    "task_flow",
                ),
            )
        )
    if "workload" in selected_sections:
        contents.append("Workload Distribution")
        trend_rows = [
            {
                "label": report["buckets"][index]["label"],
                **{row["investigator"]: row["trend"][index]["average"] for row in report["workload"]},
            }
            for index in range(len(report["buckets"]))
        ]
        sections.append(
            _section(
                "Workload Distribution",
                "Monthly average concurrent taskload by investigator.",
                _image(charts.trend_lines(
                    trend_rows,
                    [
                        (row["investigator"], row["investigator"], charts.TREND_COLORS[index % len(charts.TREND_COLORS)])
                        for index, row in enumerate(report["workload"])
                    ],
                    ylabel="Average active tasks",
                    print_friendly=True,
                ))
                + table(
                    [
                        {
                            "Investigator": row["investigator"],
                            "Distinct active tasks": row["distinct_active_tasks"],
                        }
                        for row in report["workload"]
                    ],
                    "workload",
                ),
            )
        )
    if "durations" in selected_sections:
        contents.append("Lifecycle Duration")
        sections.append(
            _section(
                "Lifecycle Duration",
                "Monthly median elapsed calendar days between lifecycle gates.",
                _image(charts.trend_lines(
                    report["duration_trend"],
                    [
                        ("Created to Started", "Created to Started", charts.LIFECYCLE_COLORS["started"]),
                        ("Started to Submitted", "Started to Submitted", charts.LIFECYCLE_COLORS["submitted"]),
                        ("Final Submission to Completed", "Final Submission to Completed", charts.LIFECYCLE_COLORS["completed"]),
                        ("Returned to Resubmitted", "Returned to Resubmitted", charts.LIFECYCLE_COLORS["returned"]),
                    ],
                    ylabel="Median days",
                    print_friendly=True,
                ))
                + table(
                    [
                        {
                            "Interval": row["interval"],
                            "Average days": f"{row['average_days']:.0f}",
                            "Median days": f"{row['median_days']:.0f}",
                            "Tasks": row["task_count"],
                        }
                        for row in report["durations"]
                    ],
                    "durations",
                ),
            )
        )
    if "complexity" in selected_sections:
        contents.append("Task Complexity")
        sections.extend(
            (
                _section(
                    "Task Complexity",
                    "Selected-period content volume across active tasks.",
                    table(
                        [
                            {"Measure": "Tasks active during the period", "Value": report["complexity"]["task_count"]},
                            {"Measure": "Distinct subjects", "Value": report["complexity"]["subjects_total"]},
                            {"Measure": "Distinct findings", "Value": report["complexity"]["findings_total"]},
                            {"Measure": "Subjects per active task", "Value": report["complexity"]["subjects_per_task"]},
                            {"Measure": "Findings per active task", "Value": report["complexity"]["findings_per_task"]},
                        ],
                        "complexity",
                    ),
                ),
                _section(
                    "Task Complexity Trend",
                    "Monthly subject and finding content per active task.",
                    _image(charts.complexity_trends(
                        report["complexity_trend"],
                        print_friendly=True,
                    )),
                ),
            )
        )
    if "personas" in selected_sections:
        contents.append("Covert Persona Exposure")
        sections.append(
            _section(
                "Covert Persona Exposure",
                "Month-end active task allocations by persona.",
                _image(charts.trend_lines(
                    report["persona_trend"],
                    [
                        (row["persona"], row["persona"], charts.TREND_COLORS[index % len(charts.TREND_COLORS)])
                        for index, row in enumerate(report["persona_usage"])
                    ],
                    ylabel="Month-end active exposure",
                    print_friendly=True,
                ))
                + table(
                    [
                        {
                            "Persona": row["persona"],
                            "Distinct active tasks": row["distinct_active_tasks"],
                            "Latest active exposure": row["latest_active_exposure"],
                        }
                        for row in report["persona_usage"]
                    ],
                    "personas",
                ),
            )
        )
    if "difficult_tasks" in selected_sections:
        contents.append("Difficult Tasks")
        difficult_content = table(
            [
                {
                    "Task": row["task_ref"],
                    "Investigator": row["investigator"],
                    "Investigation duration (days)": (
                        f"{row['investigation_duration']:.0f}"
                        + (" (ongoing)" if row["investigation_duration_status"] == "ongoing" else "")
                        if row["investigation_duration"] is not None
                        else "—"
                    ),
                    "Why included": "; ".join(row["reasons"]),
                }
                for row in report["difficult_tasks"]
            ],
            "difficult_tasks",
        )
        sections.append(
            _section(
                "Difficult Tasks",
                "Five tasks most frequently identified as complexity or duration outliers.",
                difficult_content,
            )
        )

    content_list = "".join(f"<li>{escape(item)}</li>" for item in contents)
    html = f"""<!doctype html>
    <html><head><meta charset="utf-8"><style>
      @page {{
        size: A4 landscape;
        margin: 16mm 13mm 16mm 13mm;
        @bottom-left {{ content: "Management Reporting | {escape(scope_label)} | {escape(period_label)}"; font-size: 8pt; color: #475569; }}
        @bottom-right {{ content: "Page " counter(page) " of " counter(pages); font-size: 8pt; color: #475569; }}
      }}
      body {{ font-family: Arial, sans-serif; color: #0F172A; font-size: 10pt; }}
      h1 {{ margin: 0; font-size: 22pt; }}
      h2 {{ margin: 0 0 3pt; font-size: 15pt; }}
      h3 {{ font-size: 11pt; margin: 12pt 0 4pt; }}
      .context {{ margin: 5pt 0 14pt; color: #334155; }}
      .contents {{ border: 1px solid #CBD5E1; border-radius: 7pt; padding: 8pt 12pt; margin-bottom: 14pt; }}
      .contents h2 {{ font-size: 11pt; }} .contents ul {{ margin: 4pt 0 0; padding-left: 16pt; }}
      .report-section {{ border: 1px solid #CBD5E1; border-radius: 7pt; overflow: hidden; padding: 10pt; margin: 0 0 12pt; break-inside: avoid; }}
      .subtitle {{ color: #475569; margin: 0 0 8pt; }}
      .chart {{ width: 100%; max-height: 90mm; object-fit: contain; box-sizing: border-box; border: 0.75pt solid #D7E0EA; border-radius: 6pt; }}
      table {{ width: 100%; border-collapse: separate; border-spacing: 0; border: 0.5pt solid #E2E8F0; border-radius: 5pt; margin-top: 8pt; overflow: hidden; font-size: 8.5pt; }}
      th {{ background: #E2E8F0; text-align: left; padding: 4pt; }}
      .table-header-teal th {{ background: #0F5D63; color: #FFFFFF; }}
      .table-header-indigo th {{ background: #344E73; color: #FFFFFF; }}
      td {{ padding: 3.5pt; border-bottom: 0.5pt solid #E2E8F0; }}
      tr:nth-child(even) {{ background: #F8FAFC; }}
    </style></head><body>
      <h1>Management Reporting</h1>
      <p class="context"><strong>Scope:</strong> {escape(scope_label)} &nbsp; <strong>Period:</strong> {escape(period_label)}
      &nbsp; <strong>Generated:</strong> {report["generated_at"]:%d %b %Y %H:%M}</p>
      <div class="contents"><h2>Contents</h2><ul>{content_list}</ul></div>
      {''.join(sections)}
    </body></html>"""
    return HTML(string=html).write_pdf()
