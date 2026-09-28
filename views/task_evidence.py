"""Shared access controls and read-only evidence browser for task evidence pages."""

from dataclasses import dataclass

import streamlit as st

from database import operations as db
from utils.auth import get_current_user, require_page_auth, user_has_role
from utils.helpers import format_lifecycle_status, restore_base64_images, sanitize_rich_html


@dataclass(frozen=True)
class TaskEvidenceAccess:
    can_mutate: bool
    message: str


def current_user_is_manager() -> bool:
    user = get_current_user()
    return bool(user and user.get("role") == "manager")


def task_evidence_access(task: dict) -> TaskEvidenceAccess:
    """Return the UI mutation permission supplied by the authorization data layer."""
    user = get_current_user()
    if not user:
        return TaskEvidenceAccess(False, "Sign in before viewing or changing task evidence.")
    if current_user_is_manager():
        return TaskEvidenceAccess(
            False,
            "Managers have read-only cross-task evidence access. Investigator evidence changes are unavailable.",
        )

    access_api = getattr(db, "get_task_evidence_access", None)
    if not callable(access_api):
        return TaskEvidenceAccess(
            False,
            "Evidence editing is unavailable until task-access integration is configured "
            "(database.get_task_evidence_access).",
        )

    access = access_api(user["username"], task["id"]) or {}
    assigned = bool(access.get("assigned", False))
    is_in_progress = bool(access.get("is_in_progress", False))
    state = format_lifecycle_status(access.get("task_state", access.get("state")))
    if not assigned:
        return TaskEvidenceAccess(
            False,
            f"Read-only: you are not assigned to this task (state: {state}).",
        )
    if not is_in_progress:
        return TaskEvidenceAccess(
            False,
            f"Evidence changes are gated while this task is {state}. "
            "Move it to In Progress before adding, editing, or deleting subjects and findings.",
        )
    return TaskEvidenceAccess(
        True,
        f"Evidence editing enabled for your assigned In Progress task (state: {state}).",
    )


def render_manager_evidence_browser() -> None:
    """Render a cross-task browser without any mutating controls."""
    require_page_auth()
    user = get_current_user()
    if not user_has_role(user, "manager"):
        st.error("Only managers can access the task evidence browser.")
        return
    st.title("Cross-Task Evidence Browser")
    st.info("Manager access is read-only. Subjects and findings cannot be changed from this view.")
    tasks = db.get_tasks()
    if not tasks:
        st.info("No active tasks are available to browse.")
        return

    choices = {
        f"[{task.get('task_ref', 'NO-REF')}] {task['task_name']} — {task.get('client_name', 'Unknown client')}": task
        for task in tasks
    }
    selected = st.selectbox("Browse task evidence", list(choices), key="manager_evidence_task")
    task = choices[selected]
    subjects = db.get_task_subjects(task["id"])
    findings = db.get_task_findings(task["id"])

    st.caption(f"{len(subjects)} subject(s) and {len(findings)} finding(s) in this task.")
    st.subheader("Subjects")
    if not subjects:
        st.info("No subjects recorded for this task.")
    for subject in subjects:
        with st.expander(
            f"#{subject['id']} [{subject['subject_type']}] {subject['display_name']} "
            f"({subject['relationship_to_task']})"
        ):
            if subject.get("notes"):
                st.write(f"**Internal notes:** {subject['notes']}")

    st.subheader("Findings")
    if not findings:
        st.info("No findings recorded for this task.")
    for finding in findings:
        with st.expander(
            f"[{finding.get('risk_level', 'Unspecified')}] {finding.get('title', 'Untitled')} "
            f"({finding.get('category', 'General')})"
        ):
            if finding.get("subject_name"):
                st.caption(f"Linked subject: {finding['subject_name']}")
            if finding.get("summary"):
                st.write(f"**Summary:** {finding['summary']}")
            if finding.get("source"):
                st.write(f"**Source:** {finding['source']}")
            details = finding.get("description", "")
            if details:
                st.markdown(
                    sanitize_rich_html(restore_base64_images(details)),
                    unsafe_allow_html=True,
                )
