from pathlib import Path

import streamlit as st

from utils.auth import require_role_page_auth


_PROJECT_TYPES = (
    "Enhanced Due Diligence",
    "Executive Threat Assessment",
    "Asset Tracing & Recovery",
    "Brand Protection & Anti-Counterfeiting",
    "Insider Threat Investigation",
    "Fraud & Financial Crime Investigation",
    "Person Profile",
    "Custom OSINT Investigation",
)
_TEMPLATE_DIRECTORY = Path(__file__).resolve().parent.parent / "templates"
_DEFAULT_TEMPLATE_PATH = _TEMPLATE_DIRECTORY / "report_template.md"


def _custom_template_path(case_type: str) -> Path:
    safe_type = case_type.replace(" ", "_").replace("/", "_")
    return _TEMPLATE_DIRECTORY / f"report_template_{safe_type}.md"


def show_templates() -> None:
    require_role_page_auth("administrator")
    st.title("Report Templates")
    st.write("Customize the Markdown report template used for each assessment type.")

    selected_type = st.selectbox("Select Project Type to Edit", _PROJECT_TYPES)
    custom_template_path = _custom_template_path(selected_type)
    path_to_read = custom_template_path if custom_template_path.is_file() else _DEFAULT_TEMPLATE_PATH
    is_custom = path_to_read == custom_template_path

    if is_custom:
        st.info(f"Editing custom template for: **{selected_type}**")
    else:
        st.info(f"Displaying the default template for: **{selected_type}**")

    content_key = "templates_editor_content"
    loaded_path_key = "templates_loaded_path"
    if st.session_state.get(loaded_path_key) != str(path_to_read):
        try:
            st.session_state[content_key] = path_to_read.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            st.error(f"Unable to read the selected template: {error}")
            return
        st.session_state[loaded_path_key] = str(path_to_read)

    with st.form("edit_template_form"):
        edited_content = st.text_area("Template Content (Markdown)", key=content_key, height=800)
        save_column, reset_column = st.columns(2)
        with save_column:
            save_requested = st.form_submit_button("Save Custom Template")
        with reset_column:
            reset_requested = is_custom and st.form_submit_button("Reset to Default")

        if save_requested:
            try:
                custom_template_path.write_text(edited_content, encoding="utf-8")
            except OSError as error:
                st.error(f"Unable to save the custom template: {error}")
            else:
                st.session_state[loaded_path_key] = str(custom_template_path)
                st.success(f"Custom template saved for {selected_type}.")
                st.rerun()

        if reset_requested:
            try:
                custom_template_path.unlink()
            except OSError as error:
                st.error(f"Unable to reset the custom template: {error}")
            else:
                st.session_state[loaded_path_key] = str(_DEFAULT_TEMPLATE_PATH)
                st.success(f"Reset {selected_type} to the default template.")
                st.rerun()
