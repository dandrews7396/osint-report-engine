from datetime import date

import streamlit as st
from database import operations as db
from database.findings import (
    get_domain_category_choices,
    get_finding_schema,
    normalize_finding_data,
)
from streamlit_jodit import st_jodit
from utils.helpers import process_base64_images, restore_base64_images, sanitize_rich_html

try:
    fragment = st.fragment
except AttributeError:
    def fragment(func):
        return func


RISK_LEVELS = ["Critical", "High", "Medium", "Low", "Informational"]
CONFIDENCE_LEVELS = ["High Confidence", "Moderate Confidence", "Low Confidence", "Unverified"]


def _finding_field_key(finding_id: int | str, category: str, field_key: str, prefix: str) -> str:
    return f"{prefix}_{finding_id}_{category}_{field_key}"


def _clear_finding_category_widget_state(finding_id: int | str, prefix: str) -> None:
    prefix_root = f"{prefix}_{finding_id}_"
    for key in list(st.session_state.keys()):
        if key.startswith(prefix_root):
            del st.session_state[key]


def _render_finding_category_fields(
    finding_id: int | str,
    category: str,
    existing_data: dict | None,
    prefix: str,
) -> dict[str, str]:
    values = {}
    normalized_data = normalize_finding_data(category, existing_data)
    for field in get_finding_schema(category)["fields"]:
        key = _finding_field_key(finding_id, category, field["key"], prefix)
        default_value = st.session_state.get(key, normalized_data[field["key"]])
        if field["kind"] == "textarea":
            values[field["key"]] = st.text_area(
                field["label"],
                value=default_value,
                placeholder=field.get("placeholder", ""),
                key=key,
            )
        elif field["kind"] == "date":
            parsed_date = (
                default_value
                if isinstance(default_value, date)
                else date.fromisoformat(default_value)
                if default_value
                else None
            )
            max_date = date.today() if field.get("max_date") == "today" else None
            selected_date = st.date_input(
                field["label"],
                value=parsed_date,
                format="YYYY-MM-DD",
                key=key,
                max_value=max_date,
            )
            values[field["key"]] = selected_date.isoformat() if isinstance(selected_date, date) else ""
        elif field["kind"] == "select":
            options = field["options"]
            index = options.index(default_value) if default_value in options else 0
            values[field["key"]] = st.selectbox(field["label"], options, index=index, key=key)
        else:
            values[field["key"]] = st.text_input(
                field["label"],
                value=default_value,
                placeholder=field.get("placeholder", ""),
                key=key,
            )
    return values


def _finding_details_editor(value: str, key: str) -> str:
    st.markdown("**Detailed Findings & Intelligence Analysis**")
    st.caption("Use this field for the analytical narrative, screenshots, and captures that should display in the report.")
    return st_jodit(
        value=restore_base64_images(value),
        config={
            "theme": "dark",
            "style": {"background": "#0e1117", "color": "#ffffff"},
            "height": 350,
            "uploader": {"insertImageAsBase64URI": True},
        },
        key=key,
    )


def show_manage_findings():
    @fragment
    def render_findings_page():
        if st.session_state.pop("clear_new_finding_category", False):
            st.session_state.pop("new_finding_category", None)

        st.title("Case Findings & Intelligence")
        st.write("Populate your cases with verified OSINT findings, including category-specific intelligence data and report-ready captures.")

        cases = db.get_cases()
        active_client_id = st.session_state.get("active_client_id")
        if active_client_id:
            cases = [case for case in cases if case["client_id"] == active_client_id]
        if not cases:
            st.warning("Please create a case for the active client first.")
            return

        case_id = st.session_state.get("active_case_id")
        active_case = next((case for case in cases if case["id"] == case_id), None)
        if active_case is None:
            st.info("Select an active case from its expander on Manage Cases before adding findings.")
            return

        subjects = db.get_case_subjects(case_id)
        subject_options = {"No Subject Linked": None}
        for subject in subjects:
            subject_options[
                f"#{subject['id']} [{subject['subject_type']}] {subject['display_name']} — {subject['relationship_to_case']}"
            ] = subject["id"]
        subject_option_labels = list(subject_options)
        categories = get_domain_category_choices()
        edit_finding_id = st.session_state.get("edit_finding_id")

        st.caption(
            f"Active case: [{active_case.get('case_ref', 'NO-REF')}] {active_case['case_name']}"
        )
        st.divider()
        st.subheader("Current Case Intelligence Findings")
        findings = db.get_case_findings_overview(case_id)
        if not findings:
            st.info("No intelligence findings added to this case yet.")

        for finding in findings:
            is_editing = edit_finding_id == finding["id"]
            finding_label = (
                f"[{finding.get('risk_level', 'Unspecified')}] "
                f"[{finding.get('confidence_level', 'Unspecified')}] "
                f"{finding.get('title', 'Untitled')} ({finding.get('category', 'General')})"
            )
            item_container = st.container() if is_editing else st.expander(finding_label)
            with item_container:
                if finding.get("subject_name"):
                    st.caption(f"Linked subject: {finding['subject_name']}")
                if is_editing:
                    full_finding = db.get_case_finding(finding["id"]) or finding
                    category_key = f"edit_finding_{finding['id']}_category"
                    st.session_state.setdefault(category_key, full_finding["category"])
                    edit_category = st.selectbox(
                        "Domain Category",
                        categories,
                        key=category_key,
                    )
                    with st.form(f"edit_finding_{finding['id']}"):
                        e_title = st.text_input("Finding Title", value=full_finding["title"])
                        col_risk, col_conf = st.columns(2)
                        risk_index = RISK_LEVELS.index(full_finding["risk_level"]) if full_finding["risk_level"] in RISK_LEVELS else 2
                        e_risk = col_risk.selectbox("Risk Level", RISK_LEVELS, index=risk_index)
                        confidence = full_finding.get("confidence_level", "High Confidence")
                        confidence_index = CONFIDENCE_LEVELS.index(confidence) if confidence in CONFIDENCE_LEVELS else 0
                        e_confidence = col_conf.selectbox("Source Confidence", CONFIDENCE_LEVELS, index=confidence_index)

                        subject_index = next(
                            (
                                index
                                for index, label in enumerate(subject_option_labels)
                                if subject_options[label] == full_finding.get("subject_id")
                            ),
                            0,
                        )
                        e_subject_label = st.selectbox("Linked Subject (optional)", subject_option_labels, index=subject_index)
                        e_summary = st.text_area("Executive Summary", value=full_finding.get("summary", ""), height=100)
                        e_category_data = _render_finding_category_fields(
                            finding["id"],
                            edit_category,
                            full_finding.get("category_data"),
                            "edit_finding",
                        )
                        e_details = _finding_details_editor(
                            full_finding.get("description", ""),
                            f"edit_finding_{finding['id']}_details",
                        )
                        e_source = st.text_input(
                            "Source",
                            value=full_finding.get("source", ""),
                            help="Record the relevant URL, citation, or Tool used.",
                        )

                        if st.form_submit_button("Save Changes"):
                            db.update_case_finding(
                                finding_id=finding["id"],
                                domain_category=edit_category,
                                title=e_title or "",
                                risk_level=e_risk,
                                source_confidence=e_confidence,
                                summary=e_summary or "",
                                detailed_findings=process_base64_images(
                                    sanitize_rich_html(e_details),
                                    active_case["client_id"],
                                    case_id,
                                ),
                                source=e_source or "",
                                category_data=e_category_data,
                                subject_id=subject_options[e_subject_label],
                            )
                            st.session_state.edit_finding_id = None
                            _clear_finding_category_widget_state(finding["id"], "edit_finding")
                            st.success("Finding updated.")
                            st.rerun()

                    if st.button("Cancel Edit", key=f"cancel_finding_{finding['id']}"):
                        st.session_state.edit_finding_id = None
                        _clear_finding_category_widget_state(finding["id"], "edit_finding")
                        st.rerun()
                else:
                    if finding.get("summary"):
                        st.write(f"**Summary:** {finding['summary']}")
                    if finding.get("source"):
                        st.write(f"**Source:** {finding['source']}")
                    col_edit, col_delete = st.columns(2)
                    if col_edit.button("Edit Finding", key=f"edit_finding_{finding['id']}", use_container_width=True):
                        st.session_state.edit_finding_id = finding["id"]
                        st.rerun()
                    if col_delete.button("Delete Finding", key=f"delete_finding_{finding['id']}", use_container_width=True):
                        db.delete_case_finding(finding["id"])
                        st.rerun()

        if edit_finding_id is not None:
            return

        st.divider()
        with st.expander("Import Vector from Risk Library"):
            risk_library = db.get_risk_library()
            if not risk_library:
                st.info("No pre-populated risk vectors found in the library.")
            else:
                with st.form("import_from_risk_library"):
                    library_options = {
                        f"[{vector['default_risk_level']}] {vector['title']} ({vector.get('category', 'General')})": vector
                        for vector in risk_library
                    }
                    selected_vector_label = st.selectbox("Select Threat Vector", list(library_options))
                    imported_subject_label = st.selectbox("Linked Subject (optional)", subject_option_labels)
                    if st.form_submit_button("Import to Case"):
                        vector = library_options[selected_vector_label]
                        db.add_case_finding(
                            case_id=case_id,
                            subject_id=subject_options[imported_subject_label],
                            domain_category=vector["category"],
                            title=vector["title"],
                            risk_level=vector["default_risk_level"],
                            source_confidence=vector.get("source_confidence", "High Confidence"),
                            summary=vector.get("description", ""),
                            detailed_findings=sanitize_rich_html(vector.get("investigative_guidance", "")),
                            source=vector.get("refs", ""),
                            category_data={},
                        )
                        st.success(f"Imported '{vector['title']}' to case. Complete its category-specific fields by editing the finding.")
                        st.rerun()

        st.divider()
        st.subheader("Add Manual Intelligence Finding")
        st.session_state.setdefault("new_finding_category", categories[0])
        new_category = st.selectbox("Domain Category", categories, key="new_finding_category")
        with st.form("add_manual_finding", clear_on_submit=True):
            mf_title = st.text_input("Finding Title", placeholder="e.g., Unsanctioned Corporate Entity Registered in Offshore Jurisdiction")
            col_risk, col_conf = st.columns(2)
            mf_risk = col_risk.selectbox("Risk Level", RISK_LEVELS)
            mf_confidence = col_conf.selectbox("Source Confidence", CONFIDENCE_LEVELS)
            mf_subject_label = st.selectbox("Linked Subject (optional)", subject_option_labels)
            mf_summary = st.text_area("Executive Summary", placeholder="Brief high-level summary of the intelligence item...")
            mf_category_data = _render_finding_category_fields("new", new_category, {}, "new_finding")
            mf_details = _finding_details_editor("", "new_finding_details")
            mf_source = st.text_input("Source", help="Record the relevant URL, citation, or other source reference.")

            if st.form_submit_button("Add Finding") and mf_title:
                db.add_case_finding(
                    case_id=case_id,
                    subject_id=subject_options[mf_subject_label],
                    domain_category=new_category,
                    title=mf_title,
                    risk_level=mf_risk,
                    source_confidence=mf_confidence,
                    summary=mf_summary,
                    detailed_findings=process_base64_images(
                        sanitize_rich_html(mf_details),
                        active_case["client_id"],
                        case_id,
                    ),
                    source=mf_source,
                    category_data=mf_category_data,
                )
                _clear_finding_category_widget_state("new", "new_finding")
                st.session_state["clear_new_finding_category"] = True
                st.success("Finding successfully added.")
                st.rerun()

    render_findings_page()
