import streamlit as st

from database import operations as db
from database.subjects import (
    SUBJECT_RELATIONSHIP_OPTIONS,
    get_subject_schema,
    get_subject_type_choices,
    normalize_subject_data,
    subject_display_name,
)

try:
    fragment = st.fragment
except AttributeError:
    def fragment(func):
        return func


@st.dialog("Confirm Subject Deletion")
def delete_subject_dialog(subject_id, subject_name):
    st.warning(f"Are you sure you want to delete subject '{subject_name}'? Linked findings will also be hidden.")
    col1, col2 = st.columns(2)
    if col1.button("Yes, Delete", type="primary", use_container_width=True):
        db.delete_case_subject(subject_id)
        st.rerun()
    if col2.button("Cancel", use_container_width=True):
        st.rerun()


def _subject_field_key(subject_id: int | str, subject_type: str, field_key: str, prefix: str) -> str:
    return f"{prefix}_{subject_id}_{subject_type}_{field_key}"


def _render_subject_fields(subject_id: int | str, subject_type: str, existing_data: dict | None, prefix: str) -> dict:
    schema = get_subject_schema(subject_type)
    existing_data = normalize_subject_data(subject_type, existing_data)
    values = {}
    for field in schema["fields"]:
        key = _subject_field_key(subject_id, subject_type, field["key"], prefix)
        default_value = st.session_state.get(key, existing_data.get(field["key"], ""))
        if field["kind"] == "textarea":
            values[field["key"]] = st.text_area(field["label"], value=default_value, placeholder=field.get("placeholder", ""), key=key)
        else:
            values[field["key"]] = st.text_input(field["label"], value=default_value, placeholder=field.get("placeholder", ""), key=key)
    return values


def _subject_label(subject: dict) -> str:
    return f"#{subject['id']} [{subject['subject_type']}] {subject['display_name']} (Case link: {subject['relationship_to_case']})"


def show_manage_subjects():
    @fragment
    def render_manage_subjects():
        st.title("Case Subjects")
        st.write("Assign multiple subjects to each case, capture the relevant type-specific details, and link findings back to the right subject.")

        cases = db.get_cases()
        active_client_id = st.session_state.get('active_client_id')
        if active_client_id:
            cases = [c for c in cases if c['client_id'] == active_client_id]

        if not cases:
            st.warning("Please create a case for the active client first.")
            return

        case_options = {f"[{c.get('case_ref', 'NO-REF')}] {c['case_name']} (Client: {c['client_name']})": c['id'] for c in cases}
        case_options_list = list(case_options.keys())
        default_index = 0
        if 'manage_subjects_case_id' in st.session_state:
            for i, case_label in enumerate(case_options_list):
                if case_options[case_label] == st.session_state.manage_subjects_case_id:
                    default_index = i
                    break

        selected_case_label = st.selectbox(
            "Select Active Case",
            case_options_list,
            index=default_index,
            key="manage_subjects_selected_case_label",
        )
        case_id = case_options[selected_case_label]
        st.session_state.manage_subjects_case_id = case_id

        subjects = db.get_case_subjects(case_id)
        st.subheader("Current Case Subjects")
        st.caption(f"{len(subjects)} subject(s) on this case")
        st.caption("Internal notes are excluded from generated reports. Use the dedicated notes field only for case-only working notes.")

        if not subjects:
            st.info("No subjects added to this case yet.")
        else:
            for subject in subjects:
                is_expanded = st.session_state.get('edit_subject_id') == subject['id']
                with st.expander(_subject_label(subject), expanded=is_expanded):
                    st.caption(f"Linked findings: {subject.get('finding_count', 0)}")

                    if is_expanded:
                        with st.form(f"edit_subject_{subject['id']}"):
                            e_display_name = st.text_input(
                                "Display Name",
                                value=subject.get('display_name', ''),
                                help="Used in case lists and reports.",
                                key=f"edit_subject_{subject['id']}_display_name",
                            )
                            e_relationship = st.selectbox(
                                "Relationship to Case",
                                SUBJECT_RELATIONSHIP_OPTIONS,
                                index=SUBJECT_RELATIONSHIP_OPTIONS.index(subject.get('relationship_to_case')) if subject.get('relationship_to_case') in SUBJECT_RELATIONSHIP_OPTIONS else 0,
                                key=f"edit_subject_{subject['id']}_relationship",
                            )
                            e_type = st.selectbox(
                                "Subject Type",
                                get_subject_type_choices(),
                                index=get_subject_type_choices().index(subject.get('subject_type')) if subject.get('subject_type') in get_subject_type_choices() else 0,
                                key=f"edit_subject_{subject['id']}_type",
                            )
                            e_data = _render_subject_fields(subject['id'], e_type, subject.get('subject_data', {}), "edit_subject")
                            e_notes = st.text_area(
                                "Notes (these will not appear in a generated report)",
                                value=subject.get('notes', ''),
                                help="Internal-only notes for case management. They are not included in generated reports.",
                                key=f"edit_subject_{subject['id']}_notes",
                            )

                            if st.form_submit_button("Save Subject Changes"):
                                cleaned_data = {k: (v or "").strip() for k, v in e_data.items()}
                                display_name = e_display_name.strip() or subject_display_name(e_type, cleaned_data)
                                db.update_case_subject(
                                    subject['id'],
                                    e_type,
                                    e_relationship,
                                    display_name,
                                    cleaned_data,
                                    e_notes,
                                )
                                st.session_state.edit_subject_id = None
                                st.success("Subject updated.")
                                st.rerun()

                    col1, col2 = st.columns(2)
                    if col1.button("Edit Subject", key=f"edit_subject_btn_{subject['id']}"):
                        st.session_state.edit_subject_id = subject['id']
                        st.rerun()
                    if col2.button("Delete Subject", key=f"delete_subject_btn_{subject['id']}"):
                        delete_subject_dialog(subject['id'], subject['display_name'])

        st.divider()
        st.subheader("Add New Subject")
        with st.form("add_subject", clear_on_submit=True):
            col1, col2 = st.columns(2)
            new_display_name = col1.text_input(
                "Display Name",
                help="Used in case lists and reports.",
                key="new_subject_display_name",
            )
            new_relationship = col2.selectbox(
                "Relationship to Case",
                SUBJECT_RELATIONSHIP_OPTIONS,
                key="new_subject_relationship",
            )
            new_type = st.selectbox(
                "Subject Type",
                get_subject_type_choices(),
                key="new_subject_type",
            )
            new_data = _render_subject_fields("new", new_type, {}, "new_subject")
            new_notes = st.text_area(
                "Notes (these will not appear in a generated report)",
                key="new_subject_notes",
                help="Internal-only notes for case management. They are not included in generated reports.",
            )

            if st.form_submit_button("Add Subject"):
                cleaned_data = {k: (v or "").strip() for k, v in new_data.items()}
                display_name = new_display_name.strip() or subject_display_name(new_type, cleaned_data)
                new_id = db.add_case_subject(
                    case_id,
                    new_type,
                    new_relationship,
                    display_name,
                    cleaned_data,
                    new_notes,
                )
                st.session_state.edit_subject_id = new_id
                st.success(f"Added subject: {display_name}")
                st.rerun()

    render_manage_subjects()
