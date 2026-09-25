from datetime import date, datetime, timedelta
from html import escape

import streamlit as st

from database import operations as db
from utils.auth import get_current_user, require_page_auth, user_has_role
from utils.helpers import format_lifecycle_status


def _case_state(case: dict) -> str:
    return case.get("lifecycle_status", "preparation")


def _assigned_to(case: dict, user: dict) -> bool:
    """Support the current display-name assignment and the foundation user-id assignment."""
    return (
        case.get("lead_investigator_id") == user.get("id")
        or case.get("investigator_user_id") == user.get("id")
        or case.get("investigator_name") in {user.get("username"), user.get("display_name")}
    )


def _go(
    page: str,
    case_id: int | None = None,
    *,
    open_case_editor: bool = False,
    open_report_feedback: bool = False,
) -> None:
    if case_id is not None:
        st.session_state.active_case_id = case_id
    if open_case_editor and case_id is not None:
        st.session_state.edit_case_id = case_id
    if open_report_feedback and case_id is not None:
        st.session_state.open_report_feedback_case_id = case_id
    st.session_state.nav = page
    st.rerun()


def _workflow_cases() -> list[dict]:
    getter = getattr(db, "get_cases_with_workflow", None)
    return getter() if callable(getter) else db.get_cases()


def _render_centered_metric(label: str, value: int) -> None:
    st.markdown(
        f"""
        <div style="text-align: center;">
            <div style="font-size: 0.875rem;">{escape(label)}</div>
            <div style="font-size: 2.25rem; font-weight: 600;">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _metric_timeframe_bounds(selection: str) -> tuple[str | None, str | None]:
    today = date.today()
    tomorrow = today + timedelta(days=1)
    this_month_start = today.replace(day=1)
    next_month_start = (this_month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    previous_month_end = this_month_start
    previous_month_start = (previous_month_end - timedelta(days=1)).replace(day=1)
    if selection == "All time":
        return None, None
    if selection == "Last calendar year":
        return f"{today.year - 1}-01-01", f"{today.year}-01-01"
    if selection == "This calendar year":
        return f"{today.year}-01-01", tomorrow.isoformat()
    if selection == "Last 6 months":
        return (today - timedelta(days=183)).isoformat(), tomorrow.isoformat()
    if selection == "Last month":
        return previous_month_start.isoformat(), previous_month_end.isoformat()
    return this_month_start.isoformat(), tomorrow.isoformat()


def _rolling_month_starts(months: int) -> list[date]:
    current_month = date.today().replace(day=1)
    starts = []
    for _ in range(months):
        starts.append(current_month)
        current_month = (current_month - timedelta(days=1)).replace(day=1)
    return starts


def _render_rolling_activity(user: dict) -> None:
    st.subheader("3 Month Lookback")
    activity_api = getattr(db, "get_management_lifecycle_activity_by_month", None)
    if not callable(activity_api):
        st.info("Rolling activity is unavailable until the monthly lifecycle activity API is integrated.")
        return
    month_starts = _rolling_month_starts(3)
    end_date = (month_starts[0].replace(day=28) + timedelta(days=4)).replace(day=1)
    activity = activity_api(
        month_starts[-1].isoformat(),
        end_date.isoformat(),
        actor_username=user["username"],
        actor_role=user["role"],
    )
    rows = "".join(
        "<tr>"
        f"<td style=\"text-align: center;\">{month.strftime('%b %Y')}</td>"
        f"<td style=\"text-align: center;\">{activity.get(month.strftime('%Y-%m'), {}).get('in_progress', 0)}</td>"
        f"<td style=\"text-align: center;\">{activity.get(month.strftime('%Y-%m'), {}).get('submitted', 0)}</td>"
        f"<td style=\"text-align: center;\">{activity.get(month.strftime('%Y-%m'), {}).get('rejected', 0)}</td>"
        f"<td style=\"text-align: center;\">{activity.get(month.strftime('%Y-%m'), {}).get('completed', 0)}</td>"
        "</tr>"
        for month in month_starts
    )
    st.markdown(
        """
        <div style="margin-bottom: 1rem;">
          <div style="border: 1px solid #334155; border-radius: 0.5rem; overflow: hidden;">
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 0;">
              <thead>
                <tr>
                  <th style="text-align: center; padding: 0.4rem;">Month</th>
                  <th style="text-align: center; padding: 0.4rem;">Started</th>
                  <th style="text-align: center; padding: 0.4rem;">Submitted</th>
                  <th style="text-align: center; padding: 0.4rem;">Returned</th>
                  <th style="text-align: center; padding: 0.4rem;">Completed</th>
                </tr>
              </thead>
              <tbody>
        """
        + rows
        + "</tbody></table></div></div>",
        unsafe_allow_html=True,
    )


def _render_investigator_dashboard(user: dict, cases: list[dict]) -> None:
    assigned = [case for case in cases if _assigned_to(case, user)]
    sections = (
        ("New Investigations", "preparation", "Begin", "Manage Cases", "in_progress"),
        ("Ongoing Investigations", "in_progress", "Open", "Manage Subjects", None),
    )
    for heading, status, action, destination, transition_to in sections:
        st.subheader(heading)
        queue = [case for case in assigned if _case_state(case) == status]
        if not queue:
            st.caption("No cases in this queue.")
            continue
        for case in queue:
            with st.container(border=True):
                left, right = st.columns((6, 1), vertical_alignment="center")
                left.markdown(
                    f"**[{case.get('case_ref', 'NO-REF')}] {case['case_name']}**"
                    f" • {case.get('client_name', 'Unknown client')} • {format_lifecycle_status(status)}"
                )
                if right.button(action, key=f"dashboard_{status}_{case['id']}"):
                    if transition_to:
                        try:
                            db.transition_case_lifecycle(
                                case["id"],
                                transition_to,
                                actor_user_id=user["id"],
                            )
                        except ValueError as exc:
                            st.error(f"Unable to begin investigation: {exc}")
                            return
                    _go(
                        destination,
                        case["id"],
                        open_case_editor=transition_to == "in_progress",
                    )

    st.subheader("Completed Investigations")
    completed = [case for case in assigned if _case_state(case) == "completed"]
    if not completed:
        st.caption("No cases in this queue.")
    for case in completed:
        with st.container(border=True):
            left, right = st.columns((6, 1), vertical_alignment="center")
            left.markdown(
                f"**[{case.get('case_ref', 'NO-REF')}] {case['case_name']}**"
                f" • {case.get('client_name', 'Unknown client')}"
            )
            if right.button("View Report", key=f"dashboard_completed_{case['id']}"):
                _go("Generate Report", case["id"])

    st.subheader("Review Responses")
    responses = [
        version
        for version in db.get_submitted_report_versions()
        if version.get("response_required_by_user_id") == user["id"]
    ]
    if not responses:
        st.caption("No cases in this queue.")
        return
    for version in responses:
        with st.container(border=True):
            left, right = st.columns((6, 1), vertical_alignment="center")
            left.markdown(f"**[{version.get('case_ref', 'NO-REF')}] {version['case_name']}**")
            if right.button("View", key=f"dashboard_review_response_{version['id']}"):
                _go("Generate Report", version["case_id"], open_report_feedback=True)


def _render_manager_dashboard(user: dict, cases: list[dict]) -> None:
    metric_heading, metric_selector = st.columns((5, 2), vertical_alignment="center")
    metric_heading.subheader("Operational Metrics")
    timeframe = metric_selector.selectbox(
        "Operational metric timeframe",
        ("This month", "Last month", "Last 6 months", "This calendar year", "Last calendar year", "All time"),
        index=5,
        key="manager_metric_timeframe",
        label_visibility="collapsed",
    )
    metric_api = getattr(db, "get_management_lifecycle_metrics", None)
    if not callable(metric_api):
        st.info("Operational status metrics are unavailable until the lifecycle metrics API is integrated.")
        return
    start_date, end_date = _metric_timeframe_bounds(timeframe)
    states = metric_api(
        start_date,
        end_date,
        actor_username=user["username"],
        actor_role=user["role"],
    )
    with st.container(border=True):
        columns = st.columns(4, vertical_alignment="center")
        with columns[0]:
            _render_centered_metric("Started", states["in_progress"])
        with columns[1]:
            _render_centered_metric("Submitted", states["submitted"])
        with columns[2]:
            _render_centered_metric("Returned", states["rejected"])
        with columns[3]:
            _render_centered_metric("Completed", states["completed"])

    _render_rolling_activity(user)

    st.subheader("Manager Queues")
    queues = (
        ("Reports awaiting review", "submitted", "Report Review"),
        ("Preparation awaiting investigator start", "preparation", "Manage Cases"),
        ("Returned to investigator", "rejected", "Manage Cases"),
    )
    for title, status, destination in queues:
        queue = [case for case in cases if _case_state(case) == status]
        with st.expander(f"{title} ({len(queue)})", expanded=False):
            if not queue:
                st.caption("No cases in this queue.")
            for case in queue:
                with st.container(border=True):
                    left, right = st.columns((6, 1), vertical_alignment="center")
                    left.markdown(
                        f"**[{case.get('case_ref', 'NO-REF')}] {case['case_name']}**"
                        f" • {case.get('investigator_name') or 'Unassigned'}"
                    )
                    if right.button("Open", key=f"manager_queue_{status}_{case['id']}"):
                        _go(destination, case["id"])

    st.subheader("Management Reporting")
    if st.button("Open Reporting View", use_container_width=True):
        _go("Management Summary")


def _render_administrator_dashboard() -> None:
    users = db.get_users()
    events = db.get_audit_events(limit=1000)
    cutoff = datetime.now() - timedelta(hours=24)

    recent_events = []
    for event in events:
        try:
            occurred_at = datetime.fromisoformat(event["occurred_at"])
        except (KeyError, TypeError, ValueError):
            continue
        if occurred_at >= cutoff:
            recent_events.append(event)

    active_users = [user for user in users if user.get("active")]
    locked_users = [
        user for user in users
        if user.get("lockout_until", 0) and float(user["lockout_until"]) > datetime.now().timestamp()
    ]
    failed_logins = sum(event.get("event_type") == "auth.login_failed" for event in recent_events)
    incomplete_profiles = sum(
        user.get("role") == "investigator"
        and (not (profile := db.get_investigator_profile(user["id"])) or profile.get("completion_status") != "complete")
        for user in users
    )

    st.subheader("Administration Overview")
    with st.container(border=True):
        metrics = st.columns(5, vertical_alignment="center")
        with metrics[0]:
            _render_centered_metric("Active Accounts", len(active_users))
        with metrics[1]:
            _render_centered_metric("Locked Accounts", len(locked_users))
        with metrics[2]:
            _render_centered_metric("Failed Logins (24h)", failed_logins)
        with metrics[3]:
            _render_centered_metric("Audit Events (24h)", len(recent_events))
        with metrics[4]:
            _render_centered_metric("Incomplete Investigator Profiles", incomplete_profiles)


def show_dashboard() -> None:
    require_page_auth()
    user = get_current_user()
    if not user:
        return
    st.title("Operational Dashboard")
    cases = _workflow_cases()
    if user_has_role(user, "manager"):
        _render_manager_dashboard(user, cases)
    elif user_has_role(user, "administrator"):
        _render_administrator_dashboard()
    else:
        _render_investigator_dashboard(user, cases)
