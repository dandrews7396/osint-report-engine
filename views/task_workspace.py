"""Selected-task workspace for task details and evidence navigation."""

import json
import re

import streamlit as st

from database import operations as db
from utils.auth import get_current_user, require_page_auth, user_has_role


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


def _tool_rows(value: str | None) -> list[dict[str, str]]:
    if not value:
        return [{"Name": "", "Description": ""}]
    try:
        rows = json.loads(value)
    except json.JSONDecodeError:
        return [{"Name": "", "Description": ""}]
    if not isinstance(rows, list):
        return [{"Name": "", "Description": ""}]
    return [
        {"Name": str(row.get("Name", "")), "Description": str(row.get("Description", ""))}
        for row in rows
        if isinstance(row, dict)
    ] or [{"Name": "", "Description": ""}]


def _save_task(task: dict, values: dict[str, str]) -> None:
    db.update_task(
        task["id"],
        values["task_ref"],
        values["task_name"],
        values["task_type"],
        task.get("start_date") or "",
        task.get("end_date") or "",
        task.get("report_date") or "",
        values["target_scope"],
        values["legitimate_interest_assessment"],
        values["executive_assessment"],
        values["key_findings_summary"],
        task.get("covert_persona_reference") or "",
        values["tools_and_sources_used"],
    )


def _render_manager_editor(task: dict, user: dict) -> None:
    investigators = db.get_investigators()
    people = {"Unassigned": None, **{person["name"]: person["user_id"] for person in investigators}}
    current = task.get("investigator_name") or "Unassigned"
    with st.form(f"manager_workspace_{task['id']}"):
        ref, name = st.columns(2)
        task_ref = ref.text_input("Task reference", value=task.get("task_ref") or "")
        task_name = name.text_input("Task title", value=task["task_name"])
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
        if st.form_submit_button("Save Task"):
            if not task_ref.strip() or not task_name.strip():
                st.error("Task reference and title are required.")
                return
            _save_task(
                task,
                {
                    "task_ref": task_ref.strip(),
                    "task_name": task_name.strip(),
                    "task_type": task_type,
                    "target_scope": scope,
                    "legitimate_interest_assessment": task.get("legitimate_interest") or "",
                    "executive_assessment": task.get("executive_summary") or "",
                    "key_findings_summary": task.get("key_findings_summary") or "",
                    "tools_and_sources_used": task.get("tools_used") or "",
                },
            )
            db.assign_task_lead_investigator(task["id"], people[investigator], actor_user_id=user["id"])
            st.rerun()


def _render_investigator_editor(task: dict) -> None:
    with st.form(f"investigator_workspace_{task['id']}"):
        st.subheader("Task Details")
        legal_authority = st.text_area(
            "Legal Authority",
            value=task.get("legitimate_interest") or "",
        )
        executive_summary = st.text_area(
            "Executive Summary",
            value=task.get("executive_summary") or "",
        )
        key_findings = st.text_area(
            "Key Findings and Recommendations",
            value=task.get("key_findings_summary") or "",
        )

        st.subheader("Covert Personas")
        allocated_personas = db.get_task_persona_references(task["id"])
        if allocated_personas:
            st.table(
                [
                    {
                        "Persona Reference": persona["persona_reference"],
                        "Allocated": persona["allocated_at"],
                    }
                    for persona in allocated_personas
                ]
            )
        else:
            st.caption("No persona references have been allocated to this task.")
        persona_references = st.text_input(
            "Add Persona References",
            help="Separate references with commas or spaces. Allocated references cannot be changed or removed.",
        )

        st.subheader("OSINT Tools and Platforms")
        edited_tools = st.data_editor(
            _tool_rows(task.get("tools_used")),
            column_config={
                "Name": st.column_config.TextColumn("Tool / Platform Name", required=True),
                "Description": st.column_config.TextColumn("Purpose / Usage Description", required=True),
            },
            num_rows="dynamic",
            use_container_width=True,
            key=f"tools_{task['id']}",
        )
        if st.form_submit_button("Save Task Details"):
            references = list(
                dict.fromkeys(
                    value.upper()
                    for value in re.split(r"[\s,]+", persona_references.strip())
                    if value
                )
            )
            if references:
                try:
                    db.add_task_persona_references(task["id"], references)
                except ValueError as exc:
                    st.error(str(exc))
                    return
            tools = [
                {"Name": row["Name"], "Description": row["Description"]}
                for row in edited_tools
                if row.get("Name") or row.get("Description")
            ]
            _save_task(
                task,
                {
                    "task_ref": task["task_ref"],
                    "task_name": task["task_name"],
                    "task_type": task.get("task_type") or TASK_TYPES[0],
                    "target_scope": task.get("target_scope") or "",
                    "legitimate_interest_assessment": legal_authority,
                    "executive_assessment": executive_summary,
                    "key_findings_summary": key_findings,
                    "tools_and_sources_used": json.dumps(tools),
                },
            )
            st.rerun()


def _navigate(page: str) -> None:
    st.session_state.nav = page
    st.rerun()


def show_task_workspace() -> None:
    require_page_auth()
    user = get_current_user()
    if not user:
        return
    task_id = st.session_state.get("active_task_id")
    tasks = db.get_tasks_with_workflow(user["username"], user["role"])
    task = next((item for item in tasks if item["id"] == task_id), None)
    if not task:
        st.error("The selected task is no longer available to you.")
        return

    manager = user_has_role(user, "manager")
    heading, back = st.columns((6, 1), vertical_alignment="center")
    heading.title(f"[{task['task_ref']}] {task['task_name']}")
    if back.button("Back", use_container_width=True):
        st.session_state.pop("show_task_workspace", None)
        st.session_state.nav = "Manage Tasks" if manager else "Tasks"
        st.rerun()
    st.caption(f"{task['client_name']} — {task['operation_name']}")

    if manager:
        _render_manager_editor(task, user)
        return

    st.subheader("Tasking Requirement")
    st.info(task.get("target_scope") or "No tasking requirement has been recorded.")
    _render_investigator_editor(task)
    st.subheader("Task Workspace")
    subjects, findings, report = st.columns(3)
    if subjects.button("Manage Subjects", use_container_width=True):
        _navigate("Manage Subjects")
    if findings.button("Task Findings", use_container_width=True):
        _navigate("Task Findings")
    if report.button("Generate Report", use_container_width=True):
        _navigate("Generate Report")
