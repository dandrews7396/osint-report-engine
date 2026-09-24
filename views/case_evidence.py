"""Shared access controls and read-only evidence browser for case evidence pages."""

from dataclasses import dataclass

import streamlit as st

from database import operations as db
from utils.auth import get_current_user, require_page_auth, user_has_role
from utils.helpers import format_lifecycle_status, restore_base64_images, sanitize_rich_html


@dataclass(frozen=True)
class CaseEvidenceAccess:
    can_mutate: bool
    message: str


def current_user_is_manager() -> bool:
    user = get_current_user()
    return bool(user and user.get("role") == "manager")


def case_evidence_access(case: dict) -> CaseEvidenceAccess:
    """Return the UI mutation permission supplied by the authorization data layer."""
    user = get_current_user()
    if not user:
        return CaseEvidenceAccess(False, "Sign in before viewing or changing case evidence.")
    if current_user_is_manager():
        return CaseEvidenceAccess(
            False,
            "Managers have read-only cross-case evidence access. Investigator evidence changes are unavailable.",
        )

    access_api = getattr(db, "get_case_evidence_access", None)
    if not callable(access_api):
        return CaseEvidenceAccess(
            False,
            "Evidence editing is unavailable until case-access integration is configured "
            "(database.get_case_evidence_access).",
        )

    access = access_api(user["username"], case["id"]) or {}
    assigned = bool(access.get("assigned", False))
    is_in_progress = bool(access.get("is_in_progress", False))
    state = format_lifecycle_status(access.get("case_state", access.get("state")))
    if not assigned:
        return CaseEvidenceAccess(
            False,
            f"Read-only: you are not assigned to this case (state: {state}).",
        )
    if not is_in_progress:
        return CaseEvidenceAccess(
            False,
            f"Evidence changes are gated while this case is {state}. "
            "Move it to In Progress before adding, editing, or deleting subjects and findings.",
        )
    return CaseEvidenceAccess(
        True,
        f"Evidence editing enabled for your assigned In Progress case (state: {state}).",
    )


def render_manager_evidence_browser() -> None:
    """Render a cross-case browser without any mutating controls."""
    require_page_auth()
    user = get_current_user()
    if not user_has_role(user, "manager"):
        st.error("Only managers can access the case evidence browser.")
        return
    st.title("Cross-Case Evidence Browser")
    st.info("Manager access is read-only. Subjects and findings cannot be changed from this view.")
    cases = db.get_cases()
    if not cases:
        st.info("No active cases are available to browse.")
        return

    choices = {
        f"[{case.get('case_ref', 'NO-REF')}] {case['case_name']} — {case.get('client_name', 'Unknown client')}": case
        for case in cases
    }
    selected = st.selectbox("Browse case evidence", list(choices), key="manager_evidence_case")
    case = choices[selected]
    subjects = db.get_case_subjects(case["id"])
    findings = db.get_case_findings(case["id"])

    st.caption(f"{len(subjects)} subject(s) and {len(findings)} finding(s) in this case.")
    st.subheader("Subjects")
    if not subjects:
        st.info("No subjects recorded for this case.")
    for subject in subjects:
        with st.expander(
            f"#{subject['id']} [{subject['subject_type']}] {subject['display_name']} "
            f"({subject['relationship_to_case']})"
        ):
            if subject.get("notes"):
                st.write(f"**Internal notes:** {subject['notes']}")

    st.subheader("Findings")
    if not findings:
        st.info("No findings recorded for this case.")
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
