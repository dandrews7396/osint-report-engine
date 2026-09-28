"""Task management grouped by Operation and lifecycle state."""

from datetime import datetime
from html import escape

import streamlit as st

from database import operations as db
from utils.auth import get_current_user, require_page_auth, user_has_role
from utils.helpers import format_lifecycle_status


TASK_TYPES = (
    "Enhanced Due Diligence",
    "Executive Threat Assessment",
    "Asset Tracing & Recovery",
    "Brand Protection & Anti-Counterfeiting",
    "Insider Threat Investigation",
    "Fraud & Financial Crime Investigation",
    "Person Profile",
    "Custom OSINT Investigation",
)
STATUS_ORDER = ("preparation", "in_progress", "submitted", "rejected", "completed")
STATUS_PILL_STYLES = {
    "preparation": ("Preparation", "#475569", "#e2e8f0"),
    "in_progress": ("In Progress", "#0f766e", "#ccfbf1"),
    "submitted": ("Submitted", "#a16207", "#fef3c7"),
    "rejected": ("Returned", "#b91c1c", "#fee2e2"),
    "completed": ("Completed", "#166534", "#dcfce7"),
}


def _age_label(task: dict) -> str:
    try:
        days = max(0, (datetime.now() - datetime.fromisoformat(task["created_at"])).days)
    except (KeyError, TypeError, ValueError):
        return "Unknown age"
    return f"{days} day{'s' if days != 1 else ''}"


def _activate_task(task_id: int) -> None:
    st.session_state.active_task_id = task_id
    st.session_state.pop("edit_subject_id", None)
    st.session_state.pop("edit_finding_id", None)
    st.session_state.show_task_workspace = True
    user = get_current_user() or {}
    st.session_state.nav = "Manage Tasks" if user_has_role(user, "manager") else "Tasks"
    st.rerun()


def _task_title(task: dict, *, manager: bool) -> str:
    details = f"[{task.get('task_ref', 'NO-REF')}] {task['task_name']} · {_age_label(task)}"
    if manager:
        return f"{details} · {task.get('investigator_name') or 'Unassigned'}"
    return details


def _render_manager_task(task: dict, user: dict) -> None:
    investigators = db.get_investigators()
    people = {"Unassigned": None, **{person["name"]: person["user_id"] for person in investigators}}
    current = task.get("investigator_name") or "Unassigned"
    with st.form(f"task_{task['id']}"):
        ref, name = st.columns(2)
        task_ref = ref.text_input("Task reference", value=task.get("task_ref") or "")
        task_name = name.text_input("Task name", value=task.get("task_name") or "")
        task_type = st.selectbox(
            "Task type",
            TASK_TYPES,
            index=TASK_TYPES.index(task["task_type"]) if task.get("task_type") in TASK_TYPES else 0,
        )
        scope = st.text_area("Tasking specification", value=task.get("target_scope") or "")
        investigator = st.selectbox(
            "Lead investigator",
            list(people),
            index=list(people).index(current) if current in people else 0,
        )
        if st.form_submit_button("Save task"):
            if not task_ref.strip() or not task_name.strip():
                st.error("Task reference and task name are required.")
                return
            db.update_task(
                task["id"], task_ref.strip(), task_name.strip(), task_type,
                task.get("start_date") or "", task.get("end_date") or "",
                task.get("report_date") or "", scope,
                task.get("legitimate_interest") or "",
                task.get("executive_summary") or "",
                task.get("key_findings_summary") or "",
                task.get("covert_persona_reference") or "",
                task.get("tools_used") or "",
            )
            db.assign_task_lead_investigator(
                task["id"], people[investigator], actor_user_id=user["id"]
            )
            st.rerun()


def _task_card(task: dict, user: dict, *, manager: bool) -> None:
    with st.container(border=True):
        details, action = st.columns((5, 2), vertical_alignment="center")
        status_label, background, foreground = STATUS_PILL_STYLES.get(
            task.get("lifecycle_status"),
            ("Unspecified", "#475569", "#e2e8f0"),
        )
        title = (
            f"<strong>[{escape(task.get('task_ref', 'NO-REF'))}] "
            f"{escape(task['task_name'])}</strong> "
            f"<span style=\"display: inline-block; margin-left: 0.4rem; padding: 0.1rem 0.45rem; "
            f"border-radius: 999px; background: {background}; color: {foreground}; "
            f"font-size: 0.75rem; font-weight: 600;\">{status_label}</span>"
        )
        if manager:
            title += f" <span style=\"color: #94a3b8;\">· {escape(task.get('investigator_name') or 'Unassigned')}</span>"
        details.markdown(title, unsafe_allow_html=True)
        if manager:
            if action.button("Manage", key=f"manage_{task['id']}", use_container_width=True):
                _activate_task(task["id"])
        elif action.button("Open", key=f"workspace_{task['id']}", use_container_width=True):
            _activate_task(task["id"])


def _create_task(operations: list[dict], user: dict, *, manager: bool) -> None:
    st.subheader("Create New Task")
    choices = {
        f"{operation['operation_name']} — {operation['client_name']}": operation
        for operation in operations
    }
    with st.form("create_task", clear_on_submit=True):
        selected_operation = st.selectbox("Operation", list(choices))
        operation = choices[selected_operation]
        ref, name = st.columns(2)
        task_ref = ref.text_input("Task reference")
        task_name = name.text_input("Task name")
        task_type = st.selectbox("Task type", TASK_TYPES)
        scope = st.text_area("Tasking specification")
        create, cancel = st.columns(2)
        if create.form_submit_button("Create task", use_container_width=True):
            try:
                if manager:
                    task_id = db.add_task(
                        task_ref.strip(), task_name.strip(), operation["id"],
                        task_type=task_type, target_scope=scope,
                    )
                    db.log_audit_event(
                        user["id"], "task.created", "task", task_id,
                        {"operation_id": operation["id"]},
                    )
                else:
                    task_id = db.create_assigned_task(
                        task_ref, task_name, operation["id"],
                        actor_user_id=user["id"], task_type=task_type,
                    )
                    if scope.strip():
                        db.update_task(
                            task_id, task_ref.strip(), task_name.strip(), task_type,
                            "", "", "", scope, "", "", "", "", "",
                        )
            except (PermissionError, ValueError) as exc:
                st.error(f"Unable to create task: {exc}")
            else:
                if not manager:
                    st.session_state.active_task_id = task_id
                st.session_state.pop("show_create_task", None)
                st.rerun()
        if cancel.form_submit_button("Cancel", use_container_width=True):
            st.session_state.pop("show_create_task", None)
            st.rerun()


def show_manage_tasks() -> None:
    require_page_auth()
    user = get_current_user()
    if not user:
        return
    if user_has_role(user, "administrator"):
        st.error("Administrators do not have access to operational work.")
        return

    manager = user_has_role(user, "manager")
    tasks = db.get_tasks_with_workflow(user["username"], user["role"])
    if not manager:
        tasks = [task for task in tasks if task.get("lifecycle_status") != "completed"]

    operations = {operation["id"]: operation for operation in db.get_operations()}
    grouped_tasks: dict[int, dict[str, list[dict]]] = (
        {operation_id: {} for operation_id in operations} if manager else {}
    )
    for task in tasks:
        if task["operation_id"] in operations:
            grouped_tasks.setdefault(task["operation_id"], {}).setdefault(
                task.get("lifecycle_status") or "preparation", []
            ).append(task)

    st.title("Manage Tasks" if manager else "Tasks")
    if not manager:
        st.caption("Only Tasks assigned to you are shown.")
    if not grouped_tasks:
        st.info("No tasks are available.")
        return

    accessible_operations = []
    for operation_id, status_groups in grouped_tasks.items():
        operation = operations[operation_id]
        if operation["operation_status"] == "open":
            accessible_operations.append(operation)
        task_count = sum(len(items) for items in status_groups.values())
        with st.expander(
            f"{operation['operation_name']} · "
            f"{operation['operation_status'].replace('_', ' ').title()} · "
            f"{task_count} Task{'s' if task_count != 1 else ''}",
            expanded=False,
        ):
            st.caption(
                f"{operation['client_name']} · "
                f"{operation.get('client_contact_email') or 'No contact email'}"
            )
            if operation.get("description"):
                st.write(operation["description"])

            for status in STATUS_ORDER:
                for task in sorted(
                    status_groups.get(status, []),
                    key=lambda item: item.get("created_at") or "",
                ):
                    _task_card(task, user, manager=manager)

    if accessible_operations:
        st.divider()
        if st.session_state.get("show_create_task"):
            _create_task(accessible_operations, user, manager=manager)
        elif st.button("Create New Task", use_container_width=True):
            st.session_state.show_create_task = True
            st.rerun()
