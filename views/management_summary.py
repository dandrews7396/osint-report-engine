from __future__ import annotations

from datetime import date, datetime, timedelta
from html import escape
from io import BytesIO

from matplotlib import pyplot as plt
import streamlit as st

from database import operations as db
from reporting import management_charts as charts
from reporting.management_report_pdf import render_management_report_pdf
from reporting.management_reporting import build_management_report, resolve_period
from utils.auth import get_current_user, require_page_auth, user_has_role

try:
    fragment = st.fragment
except AttributeError:
    def fragment(func):
        return func


DEFAULT_SECTIONS = (
    "throughput",
    "case_flow",
    "workload",
    "durations",
    "complexity",
    "personas",
    "difficult_cases",
)
SECTION_LABELS = {
    "throughput": "Lifecycle Throughput",
    "case_flow": "Case Flow",
    "workload": "Workload Balance",
    "durations": "Lifecycle Duration",
    "complexity": "Case Complexity",
    "personas": "Covert Persona Usage",
    "difficult_cases": "Difficult Cases",
}
PRESETS = {
    "Week": "week",
    "Fortnight": "fortnight",
    "Month": "month",
    "Quarter": "quarter",
    "6 months": "six_months",
    "Year": "year",
    "Custom": "custom",
}
REPORT_CHART_CACHE_VERSION = 4


def _table(rows: list[dict[str, object]]) -> None:
    if not rows:
        st.caption("No data is available for this period.")
        return
    columns = list(rows[0])
    header = "".join(f"<th>{escape(column)}</th>" for column in columns)
    body = "".join(
        "<tr>"
        + "".join(f"<td>{escape(str(row.get(column, '')))}</td>" for column in columns)
        + "</tr>"
        for row in rows
    )
    st.markdown(
        f"""
        <style>
          .management-table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
          .management-table th {{ background: #1E293B; color: #E2E8F0; text-align: left; padding: 0.45rem; }}
          .management-table td {{ color: #E2E8F0; padding: 0.4rem; border-bottom: 1px solid #334155; }}
          .management-table tbody tr:nth-child(even) {{ background: #111827; }}
        </style>
        <table class="management-table"><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>
        """,
        unsafe_allow_html=True,
    )


def _default_configuration() -> dict:
    return {
        "preset": "month",
        "scope": "team",
        "investigator_id": None,
        "complexity_mode": "totals",
        "sections": list(DEFAULT_SECTIONS),
    }


def _configuration_from_state() -> dict:
    configuration = {
        "preset": PRESETS[st.session_state.management_report_draft_preset_choice],
        "scope": (
            "team"
            if st.session_state.management_report_draft_scope_choice == "Whole Team"
            else "investigator"
        ),
        "investigator_id": (
            st.session_state.management_report_draft_investigator_choice
            if st.session_state.management_report_draft_scope_choice == "Investigator"
            else None
        ),
        "complexity_mode": (
            "totals"
            if st.session_state.management_report_draft_complexity_choice == "Totals"
            else "average"
        ),
        "sections": list(DEFAULT_SECTIONS),
    }
    if configuration["preset"] == "custom":
        configuration["start_date"] = st.session_state.management_report_draft_custom_start.isoformat()
        configuration["end_date"] = st.session_state.management_report_draft_custom_end.isoformat()
    return configuration


def _load_configuration(configuration: dict) -> None:
    st.session_state.management_report_draft_preset_choice = next(
        label for label, value in PRESETS.items() if value == configuration["preset"]
    )
    st.session_state.management_report_draft_scope_choice = (
        "Whole Team" if configuration["scope"] == "team" else "Investigator"
    )
    st.session_state.management_report_draft_investigator_choice = configuration.get("investigator_id")
    st.session_state.management_report_draft_complexity_choice = (
        "Totals"
        if configuration.get("complexity_mode", "totals") == "totals"
        else "Average"
    )
    st.session_state.management_report_complexity_reset += 1
    if configuration.get("preset") == "custom":
        st.session_state.management_report_draft_custom_start = date.fromisoformat(configuration["start_date"])
        st.session_state.management_report_draft_custom_end = date.fromisoformat(configuration["end_date"])


def _sync_draft_field(widget_key: str, draft_key: str) -> None:
    st.session_state[draft_key] = st.session_state[widget_key]


def _sync_active_report_section(widget_key: str) -> None:
    selected_section = st.session_state[widget_key]
    if selected_section is not None:
        st.session_state.management_report_active_section = selected_section


def _initialise_state() -> None:
    defaults = _default_configuration()
    for key, value in (
        ("management_report_draft_preset_choice", "Month"),
        ("management_report_draft_scope_choice", "Whole Team"),
        ("management_report_draft_investigator_choice", None),
        ("management_report_draft_complexity_choice", "Totals"),
        ("management_report_complexity_reset", 0),
        ("management_report_draft_custom_start", date.today().replace(day=1)),
        ("management_report_draft_custom_end", date.today()),
        ("management_report_loaded_id", None),
        ("management_report_loaded_configuration", None),
        ("management_report_configuration_name", "Create new report"),
        ("management_report_active_section", defaults["sections"][0]),
        ("management_report_section_reset", 0),
        ("management_report_applied_configuration", defaults),
        ("management_report_chart_images", None),
        ("management_report_chart_cache_version", None),
        ("management_report_configuration_expanded", True),
    ):
        st.session_state.setdefault(key, value)
    if st.session_state.management_report_draft_complexity_choice == "Average per case":
        st.session_state.management_report_draft_complexity_choice = "Average"


def _panel(title: str, subtitle: str):
    container = st.container(border=True)
    container.subheader(title)
    container.caption(subtitle)
    return container


def _chart_png(figure) -> bytes:
    image = BytesIO()
    try:
        figure.savefig(image, format="png", dpi=200, bbox_inches="tight")
    finally:
        plt.close(figure)
    return image.getvalue()


def _rendered_chart_images(report: dict) -> dict[str, bytes]:
    throughput_rows = [
        {
            "label": row["label"],
            **{field: row[field] for field in ("started", "submitted", "returned", "completed")},
        }
        for row in report["buckets"]
    ]
    workload_figure = (
        charts.workload_trend(report["workload"][0])
        if len(report["workload"]) == 1
        else charts.workload_bars(report["workload"])
    )
    return {
        "throughput": _chart_png(
            charts.grouped_columns(
                throughput_rows,
                [
                    ("started", "Started", charts.LIFECYCLE_COLORS["started"]),
                    ("submitted", "Submitted", charts.LIFECYCLE_COLORS["submitted"]),
                    ("returned", "Returned", charts.LIFECYCLE_COLORS["returned"]),
                    ("completed", "Completed", charts.LIFECYCLE_COLORS["completed"]),
                ],
            )
        ),
        "case_flow": _chart_png(
            charts.grouped_columns(
                report["buckets"],
                [
                    ("assigned", "Assigned", "#475569"),
                    ("started", "Started", charts.LIFECYCLE_COLORS["started"]),
                    ("submitted", "Submitted", charts.LIFECYCLE_COLORS["submitted"]),
                    ("returned", "Returned", charts.LIFECYCLE_COLORS["returned"]),
                    ("completed", "Completed", charts.LIFECYCLE_COLORS["completed"]),
                ],
            )
        ),
        "workload": _chart_png(workload_figure),
        "durations": _chart_png(charts.duration_bars(report["durations"])),
        "personas": _chart_png(charts.persona_bars(report["persona_usage"])),
    }


def _render_configuration_bar(user: dict, configurations: list[dict], investigators: list[dict]) -> None:
    names = ["Create new report", *(item["name"] for item in configurations)]
    selected_name = st.session_state.management_report_configuration_name
    if selected_name not in names:
        selected_name = "Create new report"

    saved_configuration, save_action, delete_action = st.columns((3, 1, 1), vertical_alignment="bottom")
    with saved_configuration:
        name = st.selectbox("Saved configuration", names, index=names.index(selected_name))
        if name != selected_name:
            st.session_state.management_report_configuration_name = name
            if name == "Create new report":
                st.session_state.management_report_loaded_id = None
                st.session_state.management_report_loaded_configuration = None
            else:
                selected = next(item for item in configurations if item["name"] == name)
                _load_configuration(selected["configuration"])
                st.session_state.management_report_loaded_id = selected["id"]
                st.session_state.management_report_loaded_configuration = {
                    **selected["configuration"],
                    "sections": list(DEFAULT_SECTIONS),
                }
            st.rerun()

    if st.session_state.management_report_loaded_id is not None and save_action.button(
        "Save", use_container_width=True
    ):
        current = _configuration_from_state()
        try:
            db.save_management_report_configuration(
                user["id"],
                st.session_state.management_report_configuration_name,
                current,
                configuration_id=st.session_state.management_report_loaded_id,
                actor_username=user["username"],
                actor_role=user["role"],
            )
            st.session_state.management_report_loaded_configuration = current
            st.success("Configuration saved.")
        except ValueError as exc:
            st.error(str(exc))

    with save_action.popover("Save As", use_container_width=True):
        save_as = st.text_input("Configuration name", key="management_report_save_as")
        if st.button("Save configuration", key="management_report_save_as_submit"):
            current = _configuration_from_state()
            try:
                saved = db.save_management_report_configuration(
                    user["id"], save_as, current, actor_username=user["username"], actor_role=user["role"]
                )
                st.session_state.management_report_configuration_name = saved["name"]
                st.session_state.management_report_loaded_id = saved["id"]
                st.session_state.management_report_loaded_configuration = saved["configuration"]
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    if st.session_state.management_report_loaded_id is not None and delete_action.button(
        "Delete", use_container_width=True
    ):
        try:
            db.delete_management_report_configuration(
                user["id"],
                st.session_state.management_report_loaded_id,
                actor_username=user["username"],
                actor_role=user["role"],
            )
            st.session_state.management_report_configuration_name = "Create new report"
            st.session_state.management_report_loaded_id = None
            st.session_state.management_report_loaded_configuration = None
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

    timeframe, scope, investigator, complexity = st.columns((1.2, 1.4, 1.8, 2.4), vertical_alignment="bottom")
    with timeframe:
        st.session_state.management_report_preset_widget = (
            st.session_state.management_report_draft_preset_choice
        )
        st.selectbox(
            "Timeframe",
            list(PRESETS),
            key="management_report_preset_widget",
            on_change=_sync_draft_field,
            args=("management_report_preset_widget", "management_report_draft_preset_choice"),
        )
    with scope:
        st.session_state.management_report_scope_widget = (
            st.session_state.management_report_draft_scope_choice
        )
        st.selectbox(
            "Scope",
            ("Whole Team", "Investigator"),
            key="management_report_scope_widget",
            on_change=_sync_draft_field,
            args=("management_report_scope_widget", "management_report_draft_scope_choice"),
        )
    with investigator:
        options = {item["id"]: item.get("display_name") or item["username"] for item in investigators}
        if not options:
            st.selectbox("Investigator", ("No investigators available",), disabled=True)
        else:
            if st.session_state.management_report_draft_investigator_choice not in options:
                st.session_state.management_report_draft_investigator_choice = next(iter(options))
            st.session_state.management_report_investigator_widget = (
                st.session_state.management_report_draft_investigator_choice
            )
            st.selectbox(
                "Investigator",
                list(options),
                format_func=lambda item: options[item],
                key="management_report_investigator_widget",
                disabled=st.session_state.management_report_draft_scope_choice != "Investigator",
                on_change=_sync_draft_field,
                args=("management_report_investigator_widget", "management_report_draft_investigator_choice"),
            )

    with complexity:
        widget_key = (
            "management_report_complexity_widget_"
            f"{st.session_state.management_report_complexity_reset}"
        )
        selected_mode = st.segmented_control(
            "Complexity",
            ("Totals", "Average"),
            default=st.session_state.management_report_draft_complexity_choice,
            key=widget_key,
        )
        if selected_mode is None:
            st.session_state.management_report_complexity_reset += 1
            st.rerun(scope="fragment")
        if selected_mode != st.session_state.management_report_draft_complexity_choice:
            st.session_state.management_report_draft_complexity_choice = selected_mode

    if st.session_state.management_report_draft_preset_choice == "Custom":
        custom_columns = st.columns(2)
        st.session_state.management_report_custom_start_widget = (
            st.session_state.management_report_draft_custom_start
        )
        st.session_state.management_report_custom_end_widget = (
            st.session_state.management_report_draft_custom_end
        )
        custom_columns[0].date_input(
            "Start date",
            key="management_report_custom_start_widget",
            on_change=_sync_draft_field,
            args=("management_report_custom_start_widget", "management_report_draft_custom_start"),
        )
        custom_columns[1].date_input(
            "End date",
            key="management_report_custom_end_widget",
            on_change=_sync_draft_field,
            args=("management_report_custom_end_widget", "management_report_draft_custom_end"),
        )

    current = _configuration_from_state()
    loaded = st.session_state.management_report_loaded_configuration
    if loaded is not None and current != loaded:
        st.caption("Unsaved changes")
    if st.button("Run Report", use_container_width=True):
        st.session_state.management_report_applied_configuration = current
        st.session_state.management_report_chart_images = None
        st.session_state.management_report_chart_cache_version = None
        st.session_state.management_report_configuration_expanded = False
        st.rerun()


def _render_report_actions() -> str:
    available_sections = DEFAULT_SECTIONS
    active_section = st.session_state.management_report_active_section
    if active_section not in available_sections:
        active_section = available_sections[0]
        st.session_state.management_report_active_section = active_section

    st.markdown(
        f"""
        <style>
        [class*="st-key-management_report_section_widget_"] [data-baseweb="button-group"] {{
            justify-content: center;
        }}
        [class*="st-key-management_report_section_widget_"] [data-testid="stBaseButton-pillsActive"] {{
            background: transparent !important;
            border: 2px solid #FF4B4B !important;
            color: #FF4B4B !important;
        }}
        [class*="st-key-management_report_section_widget_"] button:hover {{
            background: transparent !important;
            border-color: #FF4B4B !important;
        }}
        [class*="st-key-management_report_complexity_widget_"]
        [data-testid="stBaseButton-segmented_controlActive"] {{
            background: transparent !important;
            border: 2px solid #FF4B4B !important;
            color: #FF4B4B !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    widget_key = (
        "management_report_section_widget_"
        f"{st.session_state.management_report_section_reset}"
    )
    selected_section = st.pills(
        "Report section",
        available_sections,
        default=active_section,
        format_func=lambda section: SECTION_LABELS[section],
        key=widget_key,
        label_visibility="collapsed",
        on_change=_sync_active_report_section,
        args=(widget_key,),
    )
    if selected_section is None:
        st.session_state.management_report_section_reset += 1
        st.rerun(scope="fragment")
    return st.session_state.management_report_active_section


@fragment
def _render_report(
    report: dict,
    chart_images: dict[str, bytes],
    period_label: str,
    scope_label: str,
) -> None:
    st.markdown(
        f"**Scope:** {escape(scope_label)} &nbsp;&nbsp; **Period:** {escape(period_label)}"
        f" &nbsp;&nbsp; **Generated:** {report['generated_at']:%d %b %Y %H:%M}",
        unsafe_allow_html=True,
    )
    if report["coverage_notice"]:
        st.info(report["coverage_notice"])
    active_section = _render_report_actions()
    if active_section == "throughput":
        with _panel(
            "Lifecycle Throughput",
            "Independent lifecycle movements recorded during the selected period; this is not a conversion funnel.",
        ):
            lifecycle_metrics = st.columns(4)
            for column, (label, field) in zip(
                lifecycle_metrics,
                (
                    ("Started", "started"),
                    ("Submitted", "submitted"),
                    ("Returned", "returned"),
                    ("Completed", "completed"),
                ),
            ):
                column.metric(label, report["throughput"][field])
            st.image(chart_images["throughput"], use_container_width=True)
    if active_section == "case_flow":
        with _panel("Case Flow", "Assignments and lifecycle movement across the selected period."):
            st.image(chart_images["case_flow"], use_container_width=True)
    if active_section == "workload":
        with _panel("Workload Balance", "Average and peak concurrently active assigned cases."):
            st.image(chart_images["workload"], use_container_width=True)
            _table(
                [
                    {
                        "Investigator": row["investigator"],
                        "Average active cases": row["average"],
                        "Peak active cases": row["peak"],
                    }
                    for row in report["workload"]
                ]
            )
    if active_section == "durations":
        with _panel("Lifecycle Duration", "Average and median elapsed calendar days between lifecycle gates."):
            st.image(chart_images["durations"], use_container_width=True)
            _table(
                [
                    {
                        "Interval": row["interval"],
                        "Average days": row["average_days"],
                        "Median days": row["median_days"],
                        "Cases": row["case_count"],
                    }
                    for row in report["durations"]
                ]
            )
    if active_section == "complexity":
        with _panel("Case Complexity", "Subjects and findings included in cases active during the selected period."):
            value_label = "Average per case" if report["complexity"]["mode"] == "average" else "Total"
            subjects, findings = st.columns(2)
            subjects.metric("Subjects", report["complexity"]["subjects"], help=value_label)
            findings.metric("Findings", report["complexity"]["findings"], help=value_label)
    if active_section == "personas":
        with _panel("Covert Persona Usage", "Distinct active investigations using each persona during the selected period."):
            st.image(chart_images["personas"], use_container_width=True)
            _table([{"Persona": row["persona"], "Active investigations": row["active_investigations"]} for row in report["persona_usage"]])
    if active_section == "difficult_cases":
        with _panel(
            "Difficult Cases",
            "Five cases most frequently identified as complexity or duration outliers. Ongoing durations are measured as of the report date.",
        ):
            _table(
                [
                {
                    "Case": row["case_ref"],
                    "Investigator": row["investigator"],
                    "Investigation duration (days)": (
                        f"{row['investigation_duration']:.0f}"
                        + (" (ongoing)" if row["investigation_duration_status"] == "ongoing" else "")
                        if row["investigation_duration"] is not None
                        else "—"
                    ),
                    "Why included": "; ".join(row["reasons"]),
                }
                for row in report["difficult_cases"]
                ]
            )
    attention_items = report["manager_attention"]
    attention_label = "Manager Attention"
    if attention_items:
        attention_label += f" ({len(attention_items)} to review)"
    with st.expander(attention_label, expanded=False):
        st.caption("In-app only — not included in printable reports.")
        if attention_items:
            _table(
                [
                    {
                        "Investigator": row["investigator"],
                        "Attention area": row["area"],
                        "Current period": row["current"],
                        "Personal 75th percentile": row["baseline"],
                        "Context": row["context"],
                    }
                    for row in attention_items
                ]
            )
        else:
            st.caption("No items require review for this reporting period.")


def show_management_summary() -> None:
    require_page_auth()
    user = get_current_user()
    if not user or not user_has_role(user, "manager"):
        st.error("Only managers can access Management Reporting.")
        return
    _initialise_state()
    st.title("Management Reporting")
    configurations = db.list_management_report_configurations(
        user["id"], actor_username=user["username"], actor_role=user["role"]
    )
    today = date.today()
    initial_facts = db.get_management_reporting_facts(
        today.isoformat(),
        (today + timedelta(days=1)).isoformat(),
        actor_username=user["username"],
        actor_role=user["role"],
    )
    @fragment
    def render_configuration() -> None:
        with st.expander(
            "Report configuration",
            expanded=st.session_state.management_report_configuration_expanded,
        ):
            _render_configuration_bar(user, configurations, initial_facts["investigators"])

    render_configuration()
    configuration = st.session_state.management_report_applied_configuration
    try:
        start, end, period_label = resolve_period(
            configuration["preset"],
            today=today,
            custom_start=configuration.get("start_date"),
            custom_end=configuration.get("end_date"),
        )
        facts = db.get_management_reporting_facts(
            start.isoformat(), end.isoformat(), actor_username=user["username"], actor_role=user["role"]
        )
        report = build_management_report(
            facts,
            start=start,
            end=end,
            scope_investigator_id=configuration["investigator_id"],
            complexity_mode=configuration["complexity_mode"],
            today=today,
        )
    except ValueError as exc:
        st.error(str(exc))
        return
    chart_images = st.session_state.management_report_chart_images
    if (
        st.session_state.management_report_chart_cache_version
        != REPORT_CHART_CACHE_VERSION
    ):
        chart_images = None
    if chart_images is None:
        with st.spinner("Preparing report charts..."):
            chart_images = _rendered_chart_images(report)
        st.session_state.management_report_chart_images = chart_images
        st.session_state.management_report_chart_cache_version = REPORT_CHART_CACHE_VERSION
    investigator_name = next(
        (
            item.get("display_name") or item["username"]
            for item in facts["investigators"]
            if item["id"] == configuration["investigator_id"]
        ),
        "Investigator",
    )
    _render_report(
        report,
        chart_images,
        period_label,
        "Whole Team" if configuration["scope"] == "team" else investigator_name,
    )
    try:
        pdf_bytes = render_management_report_pdf(
            report,
            scope_label="Whole Team" if configuration["scope"] == "team" else investigator_name,
            period_label=period_label,
            selected_sections=set(DEFAULT_SECTIONS),
        )
    except Exception as exc:
        st.error(f"Unable to prepare the management-report PDF: {exc}")
        return
    st.download_button(
        "Download A4 PDF",
        data=pdf_bytes,
        file_name="management-reporting.pdf",
        mime="application/pdf",
        use_container_width=True,
    )
