"""A4 landscape PDF rendering for management reporting."""

from __future__ import annotations

import base64
from html import escape

from weasyprint import HTML

from reporting import management_charts as charts


def _image(figure) -> str:
    encoded = base64.b64encode(charts.png_bytes(figure)).decode("ascii")
    return f'<img class="chart" src="data:image/png;base64,{encoded}" alt="">'


def _table(rows: list[dict]) -> str:
    if not rows:
        return "<p>No data is available for this period.</p>"
    headers = list(rows[0])
    header_html = "".join(f"<th>{escape(header)}</th>" for header in headers)
    body_html = "".join(
        "<tr>"
        + "".join(f"<td>{escape(str(row.get(header, '')))}</td>" for header in headers)
        + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{header_html}</tr></thead><tbody>{body_html}</tbody></table>"


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
) -> bytes:
    """Render the approved printable subset; manager attention is never included."""
    contents = []
    sections = []
    if "throughput" in selected_sections:
        contents.append("Lifecycle Throughput")
        sections.append(
            _section(
                "Lifecycle Throughput",
                "Cases crossing each lifecycle gate in the selected period.",
                _image(charts.grouped_columns(
                    report["buckets"],
                    [
                        ("started", "Started", charts.LIFECYCLE_COLORS["started"]),
                        ("submitted", "Submitted", charts.LIFECYCLE_COLORS["submitted"]),
                        ("returned", "Returned", charts.LIFECYCLE_COLORS["returned"]),
                        ("completed", "Completed", charts.LIFECYCLE_COLORS["completed"]),
                    ],
                    title="Lifecycle Throughput",
                )),
            )
        )
    if "case_flow" in selected_sections:
        contents.append("Case Flow")
        sections.append(
            _section(
                "Case Flow",
                "Assignments and lifecycle movement across the selected period.",
                _image(charts.grouped_columns(
                    report["buckets"],
                    [
                        ("assigned", "Assigned", "#475569"),
                        ("started", "Started", charts.LIFECYCLE_COLORS["started"]),
                        ("submitted", "Submitted", charts.LIFECYCLE_COLORS["submitted"]),
                        ("returned", "Returned", charts.LIFECYCLE_COLORS["returned"]),
                        ("completed", "Completed", charts.LIFECYCLE_COLORS["completed"]),
                    ],
                    title="Case Flow",
                )),
            )
        )
    if "workload" in selected_sections:
        contents.append("Workload Balance")
        figure = charts.workload_trend(report["workload"][0]) if len(report["workload"]) == 1 else charts.workload_bars(report["workload"])
        sections.append(
            _section(
                "Workload Balance",
                "Average and peak concurrently active assigned cases.",
                _image(figure)
                + _table(
                    [
                        {
                            "Investigator": row["investigator"],
                            "Average active cases": row["average"],
                            "Peak active cases": row["peak"],
                        }
                        for row in report["workload"]
                    ]
                ),
            )
        )
    if "durations" in selected_sections:
        contents.append("Lifecycle Duration")
        sections.append(
            _section(
                "Lifecycle Duration",
                "Average and median elapsed calendar days between lifecycle gates.",
                _image(charts.duration_bars(report["durations"]))
                + _table(
                    [
                        {
                            "Interval": row["interval"],
                            "Average days": row["average_days"],
                            "Median days": row["median_days"],
                            "Cases": row["case_count"],
                        }
                        for row in report["durations"]
                    ]
                ),
            )
        )
    if "complexity" in selected_sections:
        contents.append("Case Complexity")
        label = "Average per case" if report["complexity"]["mode"] == "average" else "Total"
        sections.append(
            _section(
                "Case Complexity",
                "Subjects and findings included in cases active during the selected period.",
                _image(charts.complexity_columns(report["complexity"]))
                + _table(
                    [
                        {"Measure": "Subjects", label: report["complexity"]["subjects"]},
                        {"Measure": "Findings", label: report["complexity"]["findings"]},
                    ]
                ),
            )
        )
    if "personas" in selected_sections:
        contents.append("Covert Persona Usage")
        sections.append(
            _section(
                "Covert Persona Usage",
                "Distinct active investigations using each persona during the selected period.",
                _image(charts.persona_bars(report["persona_usage"]))
                + _table(
                    [
                        {"Persona": row["persona"], "Active investigations": row["active_investigations"]}
                        for row in report["persona_usage"]
                    ]
                ),
            )
        )
    if "difficult_cases" in selected_sections:
        contents.append("Difficult Cases")
        difficult_content = ""
        for title, key in (
            ("Highest subject counts", "subjects"),
            ("Highest finding counts", "findings"),
            ("Longest investigation durations", "durations"),
        ):
            difficult_content += f"<h3>{escape(title)}</h3>" + _table(
                [
                    {
                        "Case": row["case_ref"],
                        "Investigator": row["investigator"],
                        "Subjects": row["subjects"],
                        "Findings": row["findings"],
                        "Investigation duration (days)": row["investigation_duration"] or "—",
                    }
                    for row in report["difficult_cases"][key]
                ]
            )
        sections.append(_section("Difficult Cases", "Contextual complexity and duration outliers.", difficult_content))

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
      .contents {{ border: 1px solid #CBD5E1; padding: 8pt 12pt; margin-bottom: 14pt; }}
      .contents h2 {{ font-size: 11pt; }} .contents ul {{ margin: 4pt 0 0; padding-left: 16pt; }}
      .report-section {{ border: 1px solid #CBD5E1; padding: 10pt; margin: 0 0 12pt; break-inside: avoid; }}
      .subtitle {{ color: #475569; margin: 0 0 8pt; }}
      .chart {{ width: 100%; max-height: 140mm; object-fit: contain; }}
      table {{ width: 100%; border-collapse: collapse; margin-top: 8pt; font-size: 8.5pt; }}
      th {{ background: #E2E8F0; text-align: left; padding: 4pt; }}
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
