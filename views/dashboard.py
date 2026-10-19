from datetime import date, datetime, timedelta
from html import escape

import streamlit as st

from database import operations as db
from database.db import get_users
from utils.auth import get_current_user, require_page_auth, user_has_role
from utils.helpers import format_lifecycle_status


def _task_state(task: dict) -> str:
    return task.get("lifecycle_status", "preparation")


def _assigned_to(task: dict, user: dict) -> bool:
    """Support the current display-name assignment and the foundation user-id assignment."""
    user_names = {
        value
        for value in (user.get("username"), user.get("display_name"))
        if value
    }
    return (
        task.get("lead_investigator_id") == user.get("id")
        or task.get("investigator_user_id") == user.get("id")
        or (
            bool(task.get("investigator_name"))
            and task["investigator_name"] in user_names
        )
    )


def _go(
    page: str,
    task_id: int | None = None,
    *,
    operation_id: int | None = None,
    open_task_editor: bool = False,
    open_task_workspace: bool = False,
    open_report_feedback: bool = False,
) -> None:
    if task_id is not None:
        st.session_state.active_task_id = task_id
    if operation_id is not None:
        st.session_state.selected_operation_id = operation_id
    if open_task_editor and task_id is not None:
        st.session_state.edit_task_id = task_id
    if open_task_workspace:
        st.session_state.show_task_workspace = True
    if open_report_feedback and task_id is not None:
        st.session_state.open_report_feedback_task_id = task_id
    st.session_state.nav = page
    st.rerun()


def _workflow_tasks() -> list[dict]:
    getter = getattr(db, "get_tasks_with_workflow", None)
    return getter() if callable(getter) else db.get_tasks()


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


def _render_investigator_dashboard(user: dict, tasks: list[dict]) -> None:
    assigned = [task for task in tasks if _assigned_to(task, user)]
    sections = (
        ("New Investigations", "preparation", "Begin", "Tasks", "in_progress"),
        ("Ongoing Investigations", "in_progress", "Open", "Tasks", None),
    )
    for heading, status, action, destination, transition_to in sections:
        queue = [task for task in assigned if _task_state(task) == status]
        with st.expander(f"{heading} · {len(queue)}"):
            if not queue:
                st.caption("No tasks in this queue.")
            for task in queue:
                with st.container(border=True):
                    left, right = st.columns((6, 1), vertical_alignment="center")
                    left.markdown(
                        f"**[{task.get('task_ref', 'NO-REF')}] {task['task_name']}**"
                        f" • {task.get('operation_name', 'Unknown operation')}"
                    )
                    if right.button(action, key=f"dashboard_{status}_{task['id']}"):
                        if transition_to:
                            try:
                                db.transition_task_lifecycle(
                                    task["id"],
                                    transition_to,
                                    actor_user_id=user["id"],
                                )
                            except ValueError as exc:
                                st.error(f"Unable to begin investigation: {exc}")
                                return
                        _go(
                            destination,
                            task["id"],
                            operation_id=task.get("operation_id"),
                            open_task_editor=transition_to == "in_progress",
                            open_task_workspace=True,
                        )

    completed = [task for task in assigned if _task_state(task) == "completed"]
    with st.expander(f"Completed Investigations · {len(completed)}"):
        if not completed:
            st.caption("No tasks in this queue.")
        for task in completed:
            with st.container(border=True):
                left, right = st.columns((6, 1), vertical_alignment="center")
                left.markdown(
                    f"**[{task.get('task_ref', 'NO-REF')}] {task['task_name']}**"
                    f" • {task.get('operation_name', 'Unknown operation')}"
                )
                if right.button("View Report", key=f"dashboard_completed_{task['id']}"):
                    _go("Generate Report", task["id"])

    responses = [
        version
        for version in db.get_submitted_report_versions()
        if version.get("response_required_by_user_id") == user["id"]
    ]
    with st.expander(f"Review Responses · {len(responses)}"):
        if not responses:
            st.caption("No tasks in this queue.")
        for version in responses:
            with st.container(border=True):
                left, right = st.columns((6, 1), vertical_alignment="center")
                left.markdown(f"**[{version.get('task_ref', 'NO-REF')}] {version['task_name']}**")
                if right.button("View", key=f"dashboard_review_response_{version['id']}"):
                    _go("Generate Report", version["task_id"], open_report_feedback=True)


def _render_manager_dashboard(user: dict, tasks: list[dict]) -> None:
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
        ("Preparation awaiting investigator start", "preparation", "Manage Tasks"),
        ("Returned to investigator", "rejected", "Manage Tasks"),
    )
    for title, status, destination in queues:
        queue = [task for task in tasks if _task_state(task) == status]
        with st.expander(f"{title} ({len(queue)})", expanded=False):
            if not queue:
                st.caption("No tasks in this queue.")
            for task in queue:
                with st.container(border=True):
                    left, right = st.columns((6, 1), vertical_alignment="center")
                    left.markdown(
                        f"**[{task.get('task_ref', 'NO-REF')}] {task['task_name']}**"
                        f" • {task.get('investigator_name') or 'Unassigned'}"
                    )
                    if right.button("Open", key=f"manager_queue_{status}_{task['id']}"):
                        _go(destination, task["id"], operation_id=task.get("operation_id"))

    st.subheader("Management Reporting")
    if st.button("Open Reporting View", use_container_width=True):
        _go("Management Summary")


def _render_administrator_dashboard() -> None:
    users = get_users()
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
    tasks = _workflow_tasks()
    if user_has_role(user, "manager"):
        _render_manager_dashboard(user, tasks)
    elif user_has_role(user, "administrator"):
        _render_administrator_dashboard()
    else:
        _render_investigator_dashboard(user, tasks)
