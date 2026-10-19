import csv
from datetime import date
from io import StringIO

from matplotlib import pyplot as plt

from reporting import management_charts as charts
from reporting.management_report_pdf import render_management_report_pdf
from reporting.management_reporting import build_management_report, management_statistics_csv


def _facts():
    return {
        "tasks": [
            {
                "id": 1,
                "task_ref": "UNASSIGNED-1",
                "task_name": "Unassigned preparation",
                "created_at": "2025-12-20T09:00:00",
                "updated_at": "2025-12-20T09:00:00",
                "lead_investigator_id": None,
            },
            {
                "id": 2,
                "task_ref": "ASSIGNED-1",
                "task_name": "Assigned preparation",
                "created_at": "2025-12-21T09:00:00",
                "updated_at": "2025-12-21T09:00:00",
                "lead_investigator_id": 10,
            },
            {
                "id": 3,
                "task_ref": "STARTED-1",
                "task_name": "Started investigation",
                "created_at": "2025-12-22T09:00:00",
                "updated_at": "2026-01-10T09:00:00",
                "lead_investigator_id": 10,
            },
        ],
        "events": [
            {
                "entity_id": "2",
                "event_type": "task.created_assigned",
                "actor_user_id": 10,
                "occurred_at": "2025-12-21T09:00:00",
                "details_json": "{}",
            },
            {
                "entity_id": "3",
                "event_type": "task.created_assigned",
                "actor_user_id": 10,
                "occurred_at": "2025-12-22T09:00:00",
                "details_json": "{}",
            },
            {
                "entity_id": "3",
                "event_type": "task.lifecycle_changed",
                "actor_user_id": 10,
                "occurred_at": "2026-01-10T09:00:00",
                "details_json": '{"status": "in_progress"}',
            },
        ],
        "investigators": [{"id": 10, "display_name": "Investigator One", "username": "invest1"}],
        "subjects": [],
        "findings": [],
        "personas": [],
    }


def test_readiness_backlog_summary_pdf_and_csv():
    report = build_management_report(
        _facts(),
        start=date(2026, 1, 1),
        end=date(2026, 3, 1),
        scope_investigator_id=None,
        complexity_mode="totals",
        today=date(2026, 2, 28),
    )

    assert report["assignment_flow"]["unassigned"] == 1
    assert report["assignment_flow"]["assigned_not_started"] == 1
    assert report["assignment_flow"]["preparation_backlog"] == 2
    assert all(row["unassigned"] == 1 for row in report["readiness_trend"])
    assert all(row["assigned_not_started"] == 1 for row in report["readiness_trend"])
    assert report["executive_summary"][1]["Value"] == "2 total (1 unassigned; 1 assigned but not started)"

    csv_rows = list(csv.DictReader(StringIO(management_statistics_csv(report, scope_label="Whole Team"))))
    assert csv_rows[0]["schema_version"] == "1.0"
    assert any(
        row["measure"] == "preparation_unassigned_end" and row["value"] == "1"
        for row in csv_rows
    )
    assert all("UNASSIGNED-1" not in ",".join(row.values()) for row in csv_rows)

    readiness_figure = charts.assignment_readiness(report["buckets"])
    readiness_axis = readiness_figure.axes[0]
    assert readiness_axis.get_ylim()[0] == 0
    assert all(value.is_integer() for value in readiness_axis.get_yticks())
    plt.close(readiness_figure)

    print_figure = charts.grouped_columns(
        report["buckets"],
        [("started", "Started", "#2563EB")],
        print_friendly=True,
    )
    assert print_figure.get_facecolor()[:3] == (1.0, 1.0, 1.0)
    plt.close(print_figure)

    pdf = render_management_report_pdf(
        report,
        scope_label="Whole Team",
        period_label="January to February 2026",
        selected_sections={"task_flow"},
        table_header_tones={"executive_summary": "teal", "task_flow": "indigo"},
    )
    assert pdf.startswith(b"%PDF")
