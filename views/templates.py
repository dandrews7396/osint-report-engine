import streamlit as st
import os

try:
    fragment = st.fragment
except AttributeError:
    def fragment(func):
        return func

def show_templates():
    project_types = [
        "Enhanced Due Diligence",
        "Executive Threat Assessment",
        "Asset Tracing & Recovery",
        "Brand Protection & Anti-Counterfeiting",
        "Insider Threat Investigation",
        "Fraud & Financial Crime Investigation",
        "Person Profile",
        "Custom OSINT Investigation"
    ]
    
    template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')

    @fragment
    def render_template_editor():
        st.title("Report Templates")
        st.write("Customize the Markdown report template used for each specific assessment type.")

        selected_type = st.selectbox(
            "Select Project Type to Edit",
            project_types,
            key="templates_selected_type",
        )
        safe_type = selected_type.replace(' ', '_').replace('/', '_')

        custom_template_path = os.path.join(template_dir, f'report_template_{safe_type}.md')
        default_template_path = os.path.join(template_dir, 'report_template.md')

        is_custom = os.path.exists(custom_template_path)
        if is_custom:
            st.info(f"Editing custom template for: **{selected_type}**")
            path_to_read = custom_template_path
        else:
            st.info(f"No custom template found for **{selected_type}**. Displaying the default template.")
            path_to_read = default_template_path

        editor_state_key = "templates_editor_content"
        loaded_state_key = "templates_loaded_path"

        if st.session_state.get(loaded_state_key) != path_to_read:
            try:
                with open(path_to_read, 'r', encoding='utf-8') as f:
                    st.session_state[editor_state_key] = f.read()
                st.session_state[loaded_state_key] = path_to_read
            except Exception as e:
                st.error(f"Error reading template: {e}")
                return

        with st.form("edit_template_form"):
            edited_content = st.text_area(
                "Template Content (Markdown)",
                key=editor_state_key,
                height=800,
            )
            col1, col2 = st.columns([1, 1])

            with col1:
                if st.form_submit_button("Save Template"):
                    try:
                        with open(custom_template_path, 'w', encoding='utf-8') as f:
                            f.write(edited_content)
                        st.success(f"Custom template saved for {selected_type}!")
                        st.session_state[loaded_state_key] = custom_template_path
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to save template: {e}")

            with col2:
                if is_custom:
                    if st.form_submit_button("Reset to Default (Delete Custom)"):
                        try:
                            os.remove(custom_template_path)
                            st.session_state[loaded_state_key] = default_template_path
                            st.success(f"Custom template deleted for {selected_type}. Reverted to default.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to delete template: {e}")

    render_template_editor()
