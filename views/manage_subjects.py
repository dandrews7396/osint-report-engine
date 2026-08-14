from datetime import date

import streamlit as st

from database import operations as db
from database.subjects import (
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


PRINCIPAL_SUBJECT_RELATIONSHIP = "Principal Subject"


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


def _subject_editor_key(subject_id: int | str, field_key: str, prefix: str) -> str:
    return f"{prefix}_{subject_id}_{field_key}"


def _clear_subject_widget_state(subject_id: int | str, prefix: str) -> None:
    prefix_root = f"{prefix}_{subject_id}_"
    for key in list(st.session_state.keys()):
        if key.startswith(prefix_root):
            del st.session_state[key]


def _years_ago(years: int, from_date: date) -> date:
    try:
        return from_date.replace(year=from_date.year - years)
    except ValueError:
        return from_date.replace(month=2, day=28, year=from_date.year - years)


def _render_subject_fields(subject_id: int | str, subject_type: str, existing_data: dict | None, prefix: str) -> dict:
    schema = get_subject_schema(subject_type)
    existing_data = normalize_subject_data(subject_type, existing_data)
    values = {}
    for field in schema["fields"]:
        key = _subject_field_key(subject_id, subject_type, field["key"], prefix)
        default_value = st.session_state.get(key, existing_data.get(field["key"], ""))
        if field["kind"] == "textarea":
            values[field["key"]] = st.text_area(field["label"], value=default_value, placeholder=field.get("placeholder", ""), key=key)
        elif field["kind"] == "date":
            if isinstance(default_value, date):
                default_value = default_value.isoformat()
            stripped_value = default_value.strip() if isinstance(default_value, str) else (default_value or "")
            parsed_date = None
            today = date.today()
            min_value = _years_ago(field["min_years_ago"], today) if field.get("min_years_ago") else None
            max_value = today if field.get("max_date") == "today" else None
            if stripped_value:
                try:
                    parsed_date = date.fromisoformat(stripped_value)
                except ValueError:
                    parsed_date = None

            if stripped_value and (
                parsed_date is None
                or (min_value is not None and parsed_date < min_value)
                or (max_value is not None and parsed_date > max_value)
            ):
                st.caption(
                    f"{field['label']} is outside the calendar picker range or is not an exact date. "
                    "Replace it with an exact in-range date to use the calendar picker."
                )
                values[field["key"]] = st.text_input(
                    field["label"],
                    value=str(default_value) if default_value is not None else "",
                    placeholder=field.get("placeholder", ""),
                    key=key,
                )
            else:
                selected_date = st.date_input(
                    field["label"],
                    value=parsed_date,
                    min_value=min_value,
                    max_value=max_value,
                    format="YYYY-MM-DD",
                    key=key,
                )
                values[field["key"]] = selected_date.isoformat() if isinstance(selected_date, date) else ""
        else:
            values[field["key"]] = st.text_input(field["label"], value=default_value, placeholder=field.get("placeholder", ""), key=key)
    return values


def _subject_label(subject: dict) -> str:
    return f"#{subject['id']} [{subject['subject_type']}] {subject['display_name']} (Case link: {subject['relationship_to_case']})"


def _relationship_option_map(subjects: list[dict], current_subject_id: int | None = None, current_value: str = "") -> dict[str, str]:
    options = {"Principal Subject": PRINCIPAL_SUBJECT_RELATIONSHIP}
    for subject in subjects:
        if current_subject_id is not None and subject["id"] == current_subject_id:
            continue
        label = f"#{subject['id']} [{subject['subject_type']}] {subject['display_name']}"
        options[label] = subject["display_name"]

    normalized_current_value = (current_value or "").strip()
    if normalized_current_value and normalized_current_value not in options.values():
        options[f"{normalized_current_value} (current value)"] = normalized_current_value
    return options


def show_manage_subjects():
    @fragment
    def render_manage_subjects():
        if st.session_state.pop("clear_new_subject_fields", False):
            for key in (
                "new_subject_display_name",
                "new_subject_relationship",
                "new_subject_type",
                "new_subject_notes",
            ):
                st.session_state.pop(key, None)
            _clear_subject_widget_state("new", "new_subject")

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
        edit_subject_id = st.session_state.get('edit_subject_id')
        st.subheader("Current Case Subjects")
        st.caption(f"{len(subjects)} subject(s) on this case")
        st.caption("Internal notes are excluded from generated reports. Use the dedicated notes field only for case-only working notes.")

        if not subjects:
            st.info("No subjects added to this case yet.")
        else:
            for subject in subjects:
                is_editing = edit_subject_id == subject['id']
                subject_label = _subject_label(subject)
                if is_editing:
                    st.markdown(f"#### {subject_label}")
                    st.caption("Editing is locked open until you save or cancel.")
                    item_container = st.container()
                else:
                    item_container = st.expander(subject_label)

                with item_container:
                    st.caption(f"Linked findings: {subject.get('finding_count', 0)}")

                    if is_editing:
                        display_key = _subject_editor_key(subject['id'], "display_name", "edit_subject")
                        relationship_key = _subject_editor_key(subject['id'], "relationship", "edit_subject")
                        type_key = _subject_editor_key(subject['id'], "type", "edit_subject")
                        notes_key = _subject_editor_key(subject['id'], "notes", "edit_subject")
                        relationship_options = _relationship_option_map(
                            subjects,
                            current_subject_id=subject['id'],
                            current_value=subject.get('relationship_to_case', ''),
                        )
                        relationship_option_labels = list(relationship_options.keys())
                        current_relationship_value = subject.get('relationship_to_case', PRINCIPAL_SUBJECT_RELATIONSHIP)
                        relationship_label = next(
                            (label for label, value in relationship_options.items() if value == current_relationship_value),
                            relationship_option_labels[0],
                        )

                        st.session_state.setdefault(display_key, subject.get('display_name', ''))
                        st.session_state.setdefault(relationship_key, relationship_label)
                        st.session_state.setdefault(type_key, subject.get('subject_type', get_subject_type_choices()[0]))
                        st.session_state.setdefault(notes_key, subject.get('notes', ''))

                        e_type = st.selectbox(
                            "Subject Type",
                            get_subject_type_choices(),
                            key=type_key,
                        )
                        with st.form(f"edit_subject_{subject['id']}"):
                            e_display_name = st.text_input(
                                "Display Name",
                                help="Used in case lists and reports.",
                                key=display_key,
                            )
                            e_relationship = st.selectbox(
                                "Relationship to Case",
                                relationship_option_labels,
                                key=relationship_key,
                            )
                            e_data = _render_subject_fields(subject['id'], e_type, subject.get('subject_data', {}), "edit_subject")
                            e_notes = st.text_area(
                                "Notes (these will not appear in a generated report)",
                                help="Internal-only notes for case management. They are not included in generated reports.",
                                key=notes_key,
                            )

                            if st.form_submit_button("Save Subject Changes"):
                                cleaned_data = {k: (v or "").strip() for k, v in e_data.items()}
                                display_name = e_display_name.strip() or subject_display_name(e_type, cleaned_data)
                                db.update_case_subject(
                                    subject['id'],
                                    e_type,
                                    relationship_options[e_relationship],
                                    display_name,
                                    cleaned_data,
                                    e_notes,
                                )
                                st.session_state.edit_subject_id = None
                                _clear_subject_widget_state(subject['id'], "edit_subject")
                                st.success("Subject updated.")
                                st.rerun()

                        if st.button("Cancel Edit", key=f"cancel_subject_{subject['id']}"):
                            st.session_state.edit_subject_id = None
                            _clear_subject_widget_state(subject['id'], "edit_subject")
                            st.rerun()
                    else:
                        if subject.get('notes'):
                            st.write(f"**Internal Notes:** {subject['notes']}")

                        col1, col2 = st.columns(2)
                        if col1.button("Edit Subject", key=f"edit_subject_btn_{subject['id']}", use_container_width=True):
                            st.session_state.edit_subject_id = subject['id']
                            st.rerun()
                        if col2.button("Delete Subject", key=f"delete_subject_btn_{subject['id']}", use_container_width=True):
                            delete_subject_dialog(subject['id'], subject['display_name'])

        if edit_subject_id is None:
            st.divider()
            st.subheader("Add New Subject")
            st.session_state.setdefault("new_subject_display_name", "")
            st.session_state.setdefault("new_subject_type", get_subject_type_choices()[0])
            st.session_state.setdefault("new_subject_notes", "")
            new_relationship_options = _relationship_option_map(subjects)
            new_relationship_option_labels = list(new_relationship_options.keys())
            st.session_state.setdefault("new_subject_relationship", new_relationship_option_labels[0])

            new_type = st.selectbox(
                "Subject Type",
                get_subject_type_choices(),
                key="new_subject_type",
            )
            with st.form("add_subject"):
                col1, col2 = st.columns(2)
                new_display_name = col1.text_input(
                    "Display Name",
                    help="Used in case lists and reports.",
                    key="new_subject_display_name",
                )
                new_relationship = col2.selectbox(
                    "Relationship to Case",
                    new_relationship_option_labels,
                    key="new_subject_relationship",
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
                        new_relationship_options[new_relationship],
                        display_name,
                        cleaned_data,
                        new_notes,
                    )
                    st.session_state.edit_subject_id = new_id
                    st.session_state["clear_new_subject_fields"] = True
                    st.success(f"Added subject: {display_name}")
                    st.rerun()

    render_manage_subjects()
