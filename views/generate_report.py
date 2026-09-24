from html import escape

import streamlit as st

from database import operations as db
from reporting.generator import generate_report
from reporting.versioning import build_versioned_output_path, sha256_file, verify_file_sha256
from utils.auth import get_current_user, require_page_auth, user_has_role, verify_current_password
from views.report_document import render_report_document_actions


def _assigned(case: dict, user: dict) -> bool:
    return case.get("lead_investigator_id") == user.get("id")


def _render_readiness(case: dict, subjects: list[dict], findings: list[dict]) -> None:
    checks = (
        ("Tasking", bool((case.get("target_scope") or "").strip())),
        ("Legal authority", bool((case.get("legitimate_interest_assessment") or "").strip())),
        ("Personas", bool(db.get_case_persona_references(case["id"]))),
        ("Summary", bool((case.get("executive_assessment") or "").strip())),
        ("Recommendations", bool((case.get("key_findings_summary") or "").strip())),
        ("Tools", bool((case.get("tools_and_sources_used") or "").strip())),
    )
    with st.container(border=True):
        st.markdown("#### Report Readiness")
        columns = st.columns(4)
        for index, (label, complete) in enumerate(checks):
            colour = "#198754" if complete else "#c9302c"
            icon = "✓" if complete else "✕"
            columns[index % 4].markdown(
                f'<span style="color: {colour}; font-weight: 600;">{icon} {escape(label)}</span>',
                unsafe_allow_html=True,
            )
        columns[2].caption(f"Subjects: {len(subjects)}")
        columns[3].caption(f"Findings: {len(findings)}")


def _latest_draft(versions: list[dict]) -> dict | None:
    drafts = [
        version for version in versions
        if version.get("status") == "draft" and version.get("reservation_status") == "finalized"
    ]
    return max(drafts, key=lambda version: version["version_number"]) if drafts else None


def _latest_final(versions: list[dict]) -> dict | None:
    finals = [
        version for version in versions
        if version.get("status") == "final"
        and version.get("reservation_status") == "finalized"
        and version.get("review_status") == "approved"
    ]
    return max(finals, key=lambda version: version["version_number"]) if finals else None


def _status_label(version: dict) -> str:
    if version.get("status") == "final":
        return "Final"
    review_status = version.get("review_status")
    if review_status == "submitted":
        return "Submitted"
    if review_status == "rejected":
        return "Returned"
    return "Draft"


def _render_feedback(case: dict, version: dict, user: dict) -> None:
    messages = db.get_report_review_messages(version["id"])
    open_key = f"report_feedback_open_{version['id']}"
    if st.session_state.pop("open_report_feedback_case_id", None) == case["id"]:
        st.session_state[open_key] = True
    if messages and st.button("Feedback", key=f"report_feedback_toggle_{version['id']}"):
        st.session_state[open_key] = not st.session_state.get(open_key, False)
    if not st.session_state.get(open_key, False):
        return

    for message in messages:
        st.caption(f"{message['sender_name']} · {message['created_at']}")
        st.write(message["message"])

    if version.get("review_status") != "submitted":
        return
    if version.get("response_required_by_user_id") != user["id"]:
        return
    with st.form(f"report_feedback_response_{version['id']}"):
        response = st.text_area("Response", key=f"report_feedback_text_{version['id']}")
        send_response = st.form_submit_button("Send response")
    if send_response:
        try:
            db.add_report_review_message(version["id"], sender_user_id=user["id"], message=response)
        except (PermissionError, ValueError) as exc:
            st.error(f"Unable to send response: {exc}")
        else:
            st.rerun()
    if messages and st.button("Accept feedback", key=f"accept_report_feedback_{version['id']}"):
        try:
            db.accept_report_feedback(version["id"], investigator_user_id=user["id"])
            db.transition_case_lifecycle(case["id"], "rejected", actor_user_id=user["id"])
        except (PermissionError, ValueError) as exc:
            st.error(f"Unable to accept feedback: {exc}")
        else:
            st.rerun()


def _render_current_document(
    case: dict,
    version: dict | None,
    user: dict,
    *,
    read_only: bool = False,
) -> None:
    if not version:
        return
    with st.container(border=True):
        left, right = st.columns((6, 1), vertical_alignment="center")
        document_label = "Final Report" if version.get("status") == "final" else "Draft"
        left.markdown(f"**{document_label} v{version['version_number']}**")
        verified = render_report_document_actions(version, key_prefix=f"investigator_report_{version['id']}")
        if verified:
            right.markdown(f"**{_status_label(version)} · Verified**")
        if not read_only:
            _render_feedback(case, version, user)


def _generate_draft(case: dict, findings: list[dict], user: dict) -> None:
    client = next((item for item in db.get_clients() if item["id"] == case["client_id"]), None)
    reservation = None
    output_path = None
    wrote_artifact = False
    try:
        reservation = db.reserve_report_version(case["id"], status="draft", actor_user_id=user["id"])
        output_path = build_versioned_output_path(
            "reports", case.get("case_ref") or f"case-{case['id']}",
            reservation["version_number"], status="draft",
        )
        output_path.parent.mkdir(exist_ok=True)
        generate_report(
            case, client, db.get_settings(), findings,
            include_risk_graphs=True, status="draft", version=reservation["version_number"],
            output_directory=output_path.parent,
        )
        wrote_artifact = True
        digest = sha256_file(output_path)
        verify_file_sha256(output_path, digest)
        db.finalize_report_version_reservation(
            reservation["reservation_id"], actor_user_id=user["id"],
            content_hash=digest, storage_reference=str(output_path),
            case_start_date=case.get("start_date"),
        )
    except Exception as exc:
        if reservation:
            if wrote_artifact and output_path:
                output_path.unlink(missing_ok=True)
            try:
                db.abandon_report_version_reservation(reservation["reservation_id"], actor_user_id=user["id"])
            except (PermissionError, ValueError):
                pass
        st.error(f"Draft generation failed: {exc}")
        return
    st.success(f"Draft v{reservation['version_number']} generated.")
    st.rerun()


def show_generate_report() -> None:
    require_page_auth()
    user = get_current_user()
    if not user:
        return
    if user_has_role(user, "manager", "administrator"):
        st.title("Generate Report Draft")
        st.info("Managers review and sign off submitted reports; investigators generate and submit drafts.")
        return

    active_case_id = st.session_state.get("active_case_id")
    case = next(
        (
            item for item in db.get_cases_with_workflow()
            if item["id"] == active_case_id and _assigned(item, user)
        ),
        None,
    )
    if not case:
        st.title("Generate Report Draft")
        st.info("Select an active assigned case from Manage Cases before generating a report.")
        return

    lifecycle_status = case.get("lifecycle_status")
    st.title("View Report" if lifecycle_status == "completed" else "Generate Report Draft")
    st.caption(f"[{case.get('case_ref', 'NO-REF')}] {case['case_name']}")
    versions = db.get_report_versions(case["id"])
    if lifecycle_status == "completed":
        final_report = _latest_final(versions)
        if not final_report:
            st.error("No finalized report is recorded for this completed case.")
            return
        _render_current_document(case, final_report, user, read_only=True)
        return

    subjects = db.get_case_subjects(case["id"])
    findings = db.get_case_findings(case["id"])
    current_draft = _latest_draft(versions)
    _render_readiness(case, subjects, findings)
    _render_current_document(case, current_draft, user)

    if lifecycle_status in {"in_progress", "rejected"}:
        label = "Generate Revised Draft" if current_draft else "Generate Draft"
        if st.button(label, type="primary"):
            if not findings:
                st.error("A draft cannot be generated until the case has at least one finding.")
                return
            _generate_draft(case, findings, user)

        with st.form(f"submit_draft_{case['id']}"):
            submit_password = st.text_input("Current password to submit", type="password")
            submit_requested = st.form_submit_button("Submit")
        if submit_requested:
            if not verify_current_password(user, submit_password):
                st.error("Current password verification failed.")
                return
            if not current_draft or current_draft.get("review_status") not in {"draft", "rejected"}:
                st.error("Generate a recorded draft before submitting this case.")
                return
            try:
                db.submit_report_version(current_draft["id"], actor_user_id=user["id"])
                db.transition_case_lifecycle(case["id"], "submitted", actor_user_id=user["id"])
            except ValueError as exc:
                st.error(f"Unable to submit this case: {exc}")
            else:
                st.success("Draft submitted.")
                st.rerun()
