from datetime import date

import streamlit as st

from database import operations as db
from reporting.generator import generate_report
from reporting.versioning import (
    build_versioned_output_path,
    sha256_file,
    verify_file_sha256,
)
from utils.auth import get_current_user, require_page_auth, user_has_role, verify_current_password
from views.report_document import render_report_document_actions


def _workflow_cases() -> list[dict]:
    getter = getattr(db, "get_cases_with_workflow", None)
    return getter() if callable(getter) else db.get_cases()


def _render_final_report(case: dict, user: dict, approval_data: dict) -> dict:
    reservation = db.reserve_report_version(case["id"], status="final", actor_user_id=user["id"])
    output_path = build_versioned_output_path(
        "reports", case.get("case_ref") or f"case-{case['id']}",
        reservation["version_number"], status="final",
    )
    output_path.parent.mkdir(exist_ok=True)
    client = next((item for item in db.get_clients() if item["id"] == case["client_id"]), None)
    wrote_artifact = False
    try:
        generate_report(
            case, client, db.get_settings(), db.get_case_findings(case["id"]),
            include_risk_graphs=True, status="final", approval_data=approval_data,
            case_start_date=case.get("start_date"), version=reservation["version_number"],
            output_directory=output_path.parent,
        )
        wrote_artifact = True
        digest = sha256_file(output_path)
        verify_file_sha256(output_path, digest)
        return db.finalize_report_version_reservation(
            reservation["reservation_id"], actor_user_id=user["id"],
            content_hash=digest, storage_reference=str(output_path),
            case_start_date=case.get("start_date"), approval_data=approval_data,
        )
    except Exception:
        if wrote_artifact:
            output_path.unlink(missing_ok=True)
        try:
            db.abandon_report_version_reservation(reservation["reservation_id"], actor_user_id=user["id"])
        except (PermissionError, ValueError):
            pass
        raise


def _render_feedback(version: dict, user: dict) -> None:
    messages = db.get_report_review_messages(version["id"])
    open_key = f"manager_feedback_open_{version['id']}"
    if version.get("response_required_by_user_id") == user["id"]:
        st.session_state[open_key] = True
    if messages and st.button("Feedback", key=f"manager_feedback_toggle_{version['id']}"):
        st.session_state[open_key] = not st.session_state.get(open_key, False)
    elif not messages and version.get("response_required_by_user_id") == user["id"]:
        st.caption("Add feedback or approve this report.")
    if not st.session_state.get(open_key, False):
        return
    for message in messages:
        st.caption(f"{message['sender_name']} · {message['created_at']}")
        st.write(message["message"])
    if version.get("response_required_by_user_id") != user["id"]:
        return
    with st.form(f"manager_feedback_form_{version['id']}"):
        feedback = st.text_area("Feedback", key=f"manager_feedback_text_{version['id']}")
        send_feedback = st.form_submit_button("Send feedback")
    if send_feedback:
        try:
            db.add_report_review_message(version["id"], sender_user_id=user["id"], message=feedback)
        except (PermissionError, ValueError) as exc:
            st.error(f"Unable to send feedback: {exc}")
        else:
            st.rerun()


def _render_review(case: dict, version: dict, user: dict) -> None:
    with st.container(border=True):
        left, right = st.columns((6, 1), vertical_alignment="center")
        left.markdown(f"**Draft v{version['version_number']}**")
        verified = render_report_document_actions(version, key_prefix=f"manager_report_{version['id']}")
        if verified:
            right.markdown("**Submitted · Verified**")
        _render_feedback(version, user)
        if not verified or version.get("response_required_by_user_id") != user["id"]:
            return
        with st.form(f"approve_report_{version['id']}"):
            signature = st.text_input("Sign-off signature (optional)")
            approval_password = st.text_input("Current password to approve", type="password")
            approve_requested = st.form_submit_button("Approve", type="primary")
        if approve_requested:
            if not verify_current_password(user, approval_password):
                st.error("Current password verification failed.")
                return
            approval_data = {
                "approved_by": user.get("display_name") or user["username"],
                "approved_at": date.today().isoformat(),
                "title": user.get("title") or "",
                "signature": signature,
            }
            try:
                final_report = _render_final_report(case, user, approval_data)
                db.review_report_version(version["id"], "approve", reviewer_user_id=user["id"])
                db.transition_case_lifecycle(case["id"], "completed", actor_user_id=user["id"])
                db.log_audit_event(
                    user["id"], "report.approved", "report_version", version["id"],
                    {"case_id": case["id"], "final_version": final_report["version_number"]},
                )
            except (OSError, PermissionError, ValueError) as exc:
                st.error(f"Unable to approve this report: {exc}")
            else:
                st.success(f"Report approved and recorded as final version {final_report['version_number']}.")
                st.rerun()


def _render_queue_card(version: dict, *, action: str, key: str) -> bool:
    with st.container(border=True):
        left, right = st.columns((6, 1), vertical_alignment="center")
        left.markdown(
            f"**[{version.get('case_ref', 'NO-REF')}] {version['case_name']}**"
            f" · {version.get('investigator_name') or 'Unassigned'}"
        )
        return right.button(action, key=key)


def show_review_reports() -> None:
    require_page_auth()
    user = get_current_user()
    if not user or not user_has_role(user, "manager"):
        st.error("Only managers can review and sign off reports.")
        return
    st.title("Review Reports")
    submitted = db.get_submitted_report_versions()
    available = [version for version in submitted if version.get("assigned_manager_user_id") is None]
    mine = [
        version for version in submitted
        if version.get("assigned_manager_user_id") == user["id"]
        and version.get("response_required_by_user_id") == user["id"]
    ]

    st.subheader("Available for Review")
    if not available:
        st.caption("No reports are available for review.")
    for version in available:
        if _render_queue_card(version, action="Review", key=f"claim_report_{version['id']}"):
            try:
                db.claim_report_review(version["id"], manager_user_id=user["id"])
            except (PermissionError, ValueError) as exc:
                st.error(f"Unable to claim report: {exc}")
            else:
                st.session_state.open_review_report_id = version["id"]
                st.rerun()

    st.subheader("My Reviews")
    if not mine:
        st.caption("No reports are assigned to you.")
    for version in mine:
        if _render_queue_card(version, action="View", key=f"view_report_{version['id']}"):
            st.session_state.open_review_report_id = version["id"]
            st.rerun()

    report_id = st.session_state.get("open_review_report_id")
    version = next((item for item in mine if item["id"] == report_id), None)
    if not version:
        return
    case = next((item for item in _workflow_cases() if item["id"] == version["case_id"]), None)
    if not case:
        st.error("The case for this report is no longer available.")
        return
    _render_review(case, version, user)
