import json
import re
from datetime import datetime

import streamlit as st

from database import operations as db
from utils.auth import get_current_user, require_page_auth, user_has_role
from utils.helpers import format_lifecycle_status


CASE_TYPES = (
    "Enhanced Due Diligence", "Executive Threat Assessment", "Asset Tracing & Recovery",
    "Brand Protection & Anti-Counterfeiting", "Insider Threat Investigation",
    "Fraud & Financial Crime Investigation", "Person Profile", "Custom OSINT Investigation",
)


def _state(case: dict) -> str:
    return case.get("lifecycle_status", "preparation")


def _assigned(case: dict, user: dict) -> bool:
    return (
        case.get("lead_investigator_id") == user.get("id")
        or case.get("investigator_name") in {user.get("username"), user.get("display_name")}
    )


def _workflow_cases() -> list[dict]:
    """Prefer the actor-aware workflow projection while retaining legacy read compatibility."""
    getter = getattr(db, "get_cases_with_workflow", None)
    return getter() if callable(getter) else db.get_cases()


def _case_age_days(case: dict) -> int | None:
    try:
        return max(0, (datetime.now() - datetime.fromisoformat(case["created_at"])).days)
    except (KeyError, TypeError, ValueError):
        return None


def _case_created_sort_key(case: dict) -> str:
    return case.get("created_at") or "9999-12-31T23:59:59"


def _save_case(case: dict, values: dict) -> None:
    db.update_case(
        case_id=case["id"],
        case_ref=values["ref"],
        case_name=values["name"],
        case_type=values["type"],
        start_date=case.get("start_date") or "",
        end_date=case.get("end_date") or "",
        report_date=case.get("report_date") or "",
        target_scope=values["scope"],
        legitimate_interest_assessment=values["interest"],
        executive_assessment=values["executive"],
        key_findings_summary=values["findings"],
        covert_persona_reference=values["persona"],
        tools_and_sources_used=values["tools"],
    )


def _tool_rows(value: str | None) -> list[dict[str, str]]:
    if not value:
        return [{"Name": "", "Description": ""}]
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return [{"Name": "", "Description": ""}]
    if not isinstance(decoded, list):
        return [{"Name": "", "Description": ""}]
    rows = [
        {
            "Name": str(item.get("Name", "")),
            "Description": str(item.get("Description", "")),
        }
        for item in decoded
        if isinstance(item, dict)
    ]
    return rows or [{"Name": "", "Description": ""}]


def _parse_persona_references(value: str) -> list[str]:
    return list(dict.fromkeys(
        reference.upper()
        for reference in re.split(r"[\s,]+", value.strip())
        if reference
    ))


def _manager_case_form(case: dict, investigators: list[dict], user: dict) -> None:
    investigator_names = ["Unassigned"] + [person["name"] for person in investigators]
    current = case.get("investigator_name") or "Unassigned"
    index = investigator_names.index(current) if current in investigator_names else 0

    with st.form(f"manager_case_{case['id']}"):
        st.markdown("### Case Details")
        first, second = st.columns(2)
        ref = first.text_input("Case reference", value=case.get("case_ref") or "")
        name = second.text_input("Operation Name", value=case["case_name"])
        case_type = st.selectbox(
            "Case type",
            CASE_TYPES,
            index=CASE_TYPES.index(case["case_type"]) if case.get("case_type") in CASE_TYPES else 0,
        )

        st.markdown("### Tasking & Assignment")
        scope = st.text_area("Tasking specification", value=case.get("target_scope") or "", height=100)
        selected_name = st.selectbox("Lead investigator", investigator_names, index=index)

        if st.form_submit_button("Save Case Details"):
            investigator = next((person for person in investigators if person["name"] == selected_name), {})
            _save_case(
                case,
                {
                    "ref": ref,
                    "name": name,
                    "type": case_type,
                    "scope": scope,
                    "interest": case.get("legitimate_interest") or "",
                    "executive": case.get("executive_summary") or "",
                    "findings": case.get("key_findings_summary") or "",
                    "persona": case.get("covert_persona_reference") or "",
                    "tools": case.get("tools_used") or "[]",
                },
            )
            assign = getattr(db, "assign_case_lead_investigator", None)
            if callable(assign):
                assign(case["id"], investigator.get("user_id"), actor_user_id=user["id"])
            st.session_state.pop("edit_case_id", None)
            st.rerun()


def _investigator_case_form(case: dict) -> None:
    """Investigators maintain deployment information, case summaries, and operational tooling."""
    with st.form(f"investigator_narrative_{case['id']}"):
        st.markdown("### Deployment Information")
        interest = st.text_area("Legal Authority", value=case.get("legitimate_interest") or "", height=100)
        allocated_personas = db.get_case_persona_references(case["id"])
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
            st.caption("No persona references have been allocated to this case.")
        persona_references = st.text_input(
            "Add Persona References",
            help="Separate references with commas or spaces. Allocated references cannot be changed or removed.",
        )

        st.markdown("### Case Summary")
        executive = st.text_area("Executive Summary", value=case.get("executive_summary") or "", height=120)
        findings = st.text_area(
            "Key Findings and Recommendations",
            value=case.get("key_findings_summary") or "",
            height=120,
        )

        st.markdown("#### OSINT Tools & Platforms Utilised")
        edited_tools = st.data_editor(
            _tool_rows(case.get("tools_used")),
            column_config={
                "Name": st.column_config.TextColumn("Tool / Platform Name", width="medium", required=True),
                "Description": st.column_config.TextColumn("Purpose / Usage Description", width="large", required=True),
            },
            num_rows="dynamic",
            use_container_width=True,
            key=f"tools_{case['id']}",
        )

        if st.form_submit_button("Save Case Summary"):
            new_persona_references = _parse_persona_references(persona_references)
            if new_persona_references:
                try:
                    db.add_case_persona_references(case["id"], new_persona_references)
                except ValueError as exc:
                    st.error(str(exc))
                    return
            tools = [
                {"Name": row["Name"], "Description": row["Description"]}
                for row in edited_tools
                if row.get("Name") or row.get("Description")
            ]
            _save_case(
                case,
                {
                    "ref": case["case_ref"],
                    "name": case["case_name"],
                    "type": case.get("case_type", CASE_TYPES[0]),
                    "scope": case.get("target_scope") or "",
                    "interest": interest,
                    "executive": executive,
                    "findings": findings,
                    "persona": case.get("covert_persona_reference") or "",
                    "tools": json.dumps(tools),
                },
            )
            st.session_state.pop("edit_case_id", None)
            st.rerun()


def _render_case_details(case: dict) -> None:
    st.caption(f"Type: {case.get('case_type', 'Unspecified')}")
    st.write(f"**Lead investigator:** {case.get('investigator_name') or 'Unassigned'}")
    if case.get("investigation_started_at"):
        st.write(f"**Investigation started:** {case['investigation_started_at']}")
    if case.get("target_scope"):
        st.write(f"**Tasking:** {case['target_scope']}")


def _set_active_case(case_id: int) -> None:
    st.session_state.active_case_id = case_id
    st.session_state.pop("edit_subject_id", None)
    st.session_state.pop("edit_finding_id", None)
    st.session_state.nav = "Manage Subjects"
    st.rerun()


def show_manage_cases() -> None:
    require_page_auth()
    user = get_current_user()
    if not user:
        return
    if user_has_role(user, "administrator"):
        st.error("Administrators do not have access to operational case work.")
        return

    manager = user_has_role(user, "manager")
    st.title("Case Management")
    cases = _workflow_cases()
    visible = (
        cases
        if manager
        else [
            case
            for case in cases
            if _assigned(case, user) and _state(case) != "completed"
        ]
    )
    if not manager:
        st.info("Only cases assigned to you are shown. Manager-controlled fields are read-only.")

    investigators = db.get_investigators() if manager else []
    edit_case_id = st.session_state.get("edit_case_id")
    if not manager and any(
        case["id"] == edit_case_id and _state(case) == "completed"
        for case in cases
    ):
        st.session_state.pop("edit_case_id", None)
        edit_case_id = None
    grouped_cases: dict[str, dict[str, list[dict]]] = {}
    for case in visible:
        client_name = case.get("client_name") or "Unknown Client"
        grouped_cases.setdefault(client_name, {}).setdefault(_state(case), []).append(case)

    status_order = ("preparation", "in_progress", "submitted", "rejected", "completed")
    editing_case = next(
        (
            case
            for cases_for_client in grouped_cases.values()
            for cases_for_status in cases_for_client.values()
            for case in cases_for_status
            if case["id"] == edit_case_id
        ),
        None,
    )
    editing_client_name = editing_case.get("client_name") if editing_case else None
    editing_status = _state(editing_case) if editing_case else None
    for client_name in sorted(
        grouped_cases,
        key=lambda name: name == editing_client_name,
    ):
        st.subheader(client_name)
        status_groups = grouped_cases[client_name]
        for status in sorted(
            status_order,
            key=lambda state: state == editing_status,
        ):
            cases_for_status = status_groups.get(status, [])
            if not cases_for_status:
                continue
            st.markdown(f"##### {format_lifecycle_status(status)} ({len(cases_for_status)})")
            for case in sorted(
                cases_for_status,
                key=lambda case: (case["id"] == edit_case_id, _case_created_sort_key(case)),
            ):
                age_days = _case_age_days(case)
                age_label = f"{age_days} day{'s' if age_days != 1 else ''}" if age_days is not None else "Unknown age"
                active_marker = " (Active)" if st.session_state.get("active_case_id") == case["id"] else ""
                title = (
                    f"[{case.get('case_ref', 'NO-REF')}] {case['case_name']} "
                    f"(Client: {client_name}) — {format_lifecycle_status(status)} • {age_label}{active_marker}"
                )
                is_editing = edit_case_id == case["id"]
                if is_editing:
                    st.markdown(f"#### {title}")
                    st.caption("Editing is locked open until you save or cancel.")
                    item_container = st.container()
                else:
                    item_container = st.expander(title, expanded=False)
                with item_container:
                    if is_editing:
                        if manager:
                            _manager_case_form(case, investigators, user)
                        else:
                            _investigator_case_form(case)
                        if st.button("Cancel Edit", key=f"cancel_case_{case['id']}"):
                            st.session_state.pop("edit_case_id", None)
                            st.rerun()
                        continue

                    _render_case_details(case)
                    if not manager and _state(case) in {"preparation", "rejected"}:
                        action = "Start assigned investigation" if _state(case) == "preparation" else "Resume investigation"
                        if st.button(action, key=f"start_{case['id']}", type="primary"):
                            try:
                                db.transition_case_lifecycle(case["id"], "in_progress", actor_user_id=user["id"])
                            except ValueError as exc:
                                st.error(f"Unable to start this case: {exc}")
                            else:
                                st.rerun()

                    action_columns = st.columns(3 if manager else 2)
                    if action_columns[0].button("Edit Case", key=f"edit_case_{case['id']}", use_container_width=True):
                        st.session_state.edit_case_id = case["id"]
                        st.rerun()
                    if action_columns[1].button("Set Active", key=f"active_case_{case['id']}", use_container_width=True):
                        _set_active_case(case["id"])
                    if manager and action_columns[2].button(
                        "Delete Case",
                        key=f"delete_case_{case['id']}",
                        use_container_width=True,
                    ):
                        db.delete_case(case["id"])
                        if st.session_state.get("active_case_id") == case["id"]:
                            st.session_state.pop("active_case_id", None)
                        st.rerun()

    if st.session_state.get("edit_case_id") is not None:
        return

    if manager:
        st.divider()
        st.subheader("Create Case")
        clients = db.get_clients()
        if not clients:
            st.info("Create a client before opening a case.")
            return
        client_options = {client["name"]: client["id"] for client in clients}
        with st.form("new_manager_case", clear_on_submit=True):
            client_name = st.selectbox("Client", list(client_options))
            ref, name = st.columns(2)
            case_ref = ref.text_input("Case reference")
            case_name = name.text_input("Operation Name")
            case_type = st.selectbox("Case type", CASE_TYPES)
            if st.form_submit_button("Prepare Case"):
                if not case_ref.strip() or not case_name.strip():
                    st.error("Case reference and case name are required.")
                else:
                    db.add_case(case_ref.strip(), case_name.strip(), client_options[client_name], case_type=case_type)
                    st.rerun()
    else:
        st.divider()
        st.subheader("Create Assigned Case")
        create_assigned = getattr(db, "create_assigned_case", None)
        if not callable(create_assigned):
            st.info("Investigator case creation is not available.")
            return
        clients = db.get_clients()
        if not clients:
            st.info("No clients are available.")
            return
        client_options = {client["name"]: client["id"] for client in clients}
        with st.form("new_investigator_case", clear_on_submit=True):
            client_name = st.selectbox("Client", list(client_options))
            case_ref = st.text_input("Case reference")
            case_name = st.text_input("Operation Name")
            case_type = st.selectbox("Case type", CASE_TYPES)
            if st.form_submit_button("Create assigned preparation case"):
                if not case_ref.strip() or not case_name.strip():
                    st.error("Case reference and case name are required.")
                else:
                    try:
                        create_assigned(
                            case_ref=case_ref.strip(),
                            case_name=case_name.strip(),
                            client_id=client_options[client_name],
                            case_type=case_type,
                            actor_user_id=user["id"],
                        )
                    except ValueError as exc:
                        st.error(f"Unable to create case: {exc}")
                    else:
                        st.rerun()
