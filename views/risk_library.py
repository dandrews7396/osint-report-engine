import streamlit as st
import pandas as pd
from database import operations as db
from database.findings import get_domain_category_choices
from streamlit_jodit import st_jodit
from utils.auth import get_current_user
from utils.helpers import process_base64_images, restore_base64_images, sanitize_rich_html

try:
    fragment = st.fragment
except AttributeError:
    def fragment(func):
        return func


def _risk_guidance_editor(value: str, key: str) -> str:
    st.markdown("**Investigative Guidance / Recommended Steps**")
    st.caption("Standard operating procedures and investigative guidance to verify and document this finding.")
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


def _new_risk_guidance_editor_key() -> str:
    generation = st.session_state.get("new_risk_guidance_generation", 0)
    return f"new_risk_guidance_{generation}"


def show_risk_library():
    DOMAIN_CATEGORIES = get_domain_category_choices()
    RISK_LEVELS = ["Critical", "High", "Medium", "Low", "Informational"]
    CONFIDENCE_LEVELS = ["High Confidence", "Moderate Confidence", "Low Confidence", "Unverified"]
    user = get_current_user()
    if not user:
        st.warning("Sign in before managing risk templates.")
        return
    is_manager = user.get("role") == "manager"

    def get_library_items() -> list[dict]:
        entries_api = getattr(db, "get_risk_library_entries", None)
        if callable(entries_api):
            return entries_api(include_retired=is_manager)
        return db.get_risk_library()

    def is_retired(item: dict) -> bool:
        return bool(item.get("retired_at") or item.get("is_retired"))

    def retirement_control(item: dict) -> None:
        if not is_manager:
            st.caption("Only managers can retire or restore templates.")
            return

        action = "restore_risk_library_item" if is_retired(item) else "retire_risk_library_item"
        label = "Restore Template" if is_retired(item) else "Retire Template"
        retirement_api = getattr(db, action, None)
        if not callable(retirement_api):
            st.warning(
                "Template retirement is unavailable until the risk-library retirement integration is configured "
                f"(database.{action})."
            )
            return
        if st.button(label, key=f"{action}_{item['id']}", type="primary"):
            retirement_api(item["id"], user["username"])
            st.success(f"Template {label.lower().replace(' template', 'd')}.")
            st.rerun()

    @fragment
    def render_risk_entries():
        st.title("OSINT Risk & Threat Library")
        st.write("Manage standardized threat vectors, risk templates, and investigative guidance. These pre-configured templates can be searched, managed, and imported directly into active cases.")
        if is_manager:
            st.info("Managers can create and edit templates and may retire or restore them. Case evidence remains read-only.")
        else:
            st.info("Investigators can create and edit risk templates. Retirement and restoration are manager-only.")

        st.subheader("Risk Library Entries")

        col_search, col_cat_filter = st.columns([2, 1])
        search_query = col_search.text_input("Search Library", placeholder="Search by title, description, or guidance...")
        cat_filter = col_cat_filter.selectbox("Filter by Category", ["All Categories"] + DOMAIN_CATEGORIES)

        library_items = get_library_items()
        has_search_input = bool(search_query.strip()) or cat_filter != "All Categories"
        matching_items = library_items
        if has_search_input:
            if cat_filter != "All Categories":
                matching_items = [item for item in matching_items if item.get('category') == cat_filter]
            if search_query.strip():
                q = search_query.lower()
                matching_items = [
                    item for item in matching_items
                    if q in item['title'].lower()
                    or q in (item.get('description') or '').lower()
                    or q in (item.get('investigative_guidance') or '').lower()
                ]

        if not has_search_input:
            if not library_items:
                st.info("No risk templates have been created yet. Add a template or import a CSV to get started.")
            matching_items = []
        elif not matching_items:
            st.info("No risk templates match the current search or category filter.")

        edit_risk_id = st.session_state.get("edit_risk_id")
        for item in sorted(
            matching_items[:3],
            key=lambda item: item["id"] == edit_risk_id,
        ):
            retired = is_retired(item)
            is_expanded = edit_risk_id == item['id']
            state_label = " — RETIRED" if retired else ""
            expander_label = f"[{item.get('default_risk_level', 'Medium')}] {item['title']} ({item.get('category', 'Uncategorized')}){state_label}"

            if is_expanded:
                st.markdown(f"#### {expander_label}")
                st.caption("Editing is locked open until you save or cancel.")
                item_container = st.container()
            else:
                item_container = st.expander(expander_label)

            with item_container:
                if retired:
                    st.caption("This template is retired and cannot be edited until restored.")
                    retirement_control(item)
                    continue
                if is_expanded:
                    with st.form(f"edit_risk_form_{item['id']}"):
                        e_title = st.text_input("Title", value=item['title'])

                        col1, col2, col3 = st.columns(3)
                        cat_idx = DOMAIN_CATEGORIES.index(item.get('category')) if item.get('category') in DOMAIN_CATEGORIES else 0
                        e_category = col1.selectbox("Category", DOMAIN_CATEGORIES, index=cat_idx, key=f"cat_{item['id']}")

                        risk_idx = RISK_LEVELS.index(item.get('default_risk_level')) if item.get('default_risk_level') in RISK_LEVELS else 2
                        e_risk = col2.selectbox("Default Risk Level", RISK_LEVELS, index=risk_idx, key=f"risk_{item['id']}")

                        conf_idx = CONFIDENCE_LEVELS.index(item.get('source_confidence', 'High Confidence')) if item.get('source_confidence') in CONFIDENCE_LEVELS else 0
                        e_conf = col3.selectbox("Default Source Confidence", CONFIDENCE_LEVELS, index=conf_idx, key=f"conf_{item['id']}")

                        e_desc = st.text_area("Description", value=item.get('description', '') or '', height=100)
                        e_guidance = _risk_guidance_editor(
                            item.get("investigative_guidance", "") or "",
                            f"edit_risk_guidance_{item['id']}",
                        )
                        e_refs = st.text_area("References & Framework Citations (one per line)", value=item.get('refs', '') or '', height=80)

                        if st.form_submit_button("Save Changes"):
                            db.update_risk_library_item(
                                item['id'],
                                e_category,
                                e_title,
                                e_risk,
                                e_desc,
                                sanitize_rich_html(e_guidance),
                                e_conf,
                                e_refs
                            )
                            st.session_state.pop("edit_risk_id", None)
                            st.success("Updated risk template.")
                            st.rerun()
                    if st.button("Cancel Edit", key=f"cancel_risk_{item['id']}"):
                        st.session_state.pop("edit_risk_id", None)
                        st.rerun()
                else:
                    if item.get("description"):
                        st.write(item["description"])
                    controls = st.columns(2)
                    if controls[0].button("Edit Template", key=f"edit_risk_{item['id']}", use_container_width=True):
                        st.session_state.edit_risk_id = item["id"]
                        st.rerun()
                    with controls[1]:
                        retirement_control(item)

    @fragment
    def render_risk_bulk_import():
        st.divider()
        with st.expander("Bulk Import Risk Templates (CSV)", expanded=False):
            st.write("Upload a CSV file containing standardized risk templates. The CSV must include a `title` column.")

            sample_csv = "category,title,default_risk_level,description,investigative_guidance,source_confidence,refs\n" \
                         "Identity & PII,Exposed Corporate Executive Credentials,High,Leaked passwords discovered on dark web breach databases.,Search HaveIBeenPwned and DeHashed APIs for compromised domain records.,High Confidence,HIBP API\n" \
                         "Corporate Governance & Ownership,Unregistered Offshore Parent Company,Medium,Subsidiary entity lacks disclosure in domestic filing registry.,Cross-reference OpenCorporates and local commercial registry filings.,Moderate Confidence,OpenCorporates"

            st.download_button(
                label="Download Template CSV",
                data=sample_csv,
                file_name="risk_library_template.csv",
                mime="text/csv"
            )

            uploaded_csv = st.file_uploader("Upload Risk CSV File", type=["csv"], key="risk_csv_uploader")

            if uploaded_csv is not None:
                try:
                    df = pd.read_csv(uploaded_csv)
                    st.write("**Preview Uploaded Data:**")
                    st.dataframe(df.head(5), use_container_width=True)

                    if "title" not in [col.lower() for col in df.columns]:
                        st.error("CSV file missing required column: `title`")
                    else:
                        if st.button("Process & Import CSV Records"):
                            imported_count = 0
                            df.columns = [c.lower().strip() for c in df.columns]

                            for _, row in df.iterrows():
                                title = str(row.get("title", "")).strip()
                                if not title or pd.isna(row.get("title")):
                                    continue

                                category = str(row.get("category", "Custom Category")).strip()
                                if category not in DOMAIN_CATEGORIES:
                                    category = "Custom Category"

                                risk_level = str(row.get("default_risk_level", "Medium")).strip().capitalize()
                                if risk_level not in RISK_LEVELS:
                                    risk_level = "Medium"

                                source_conf = str(row.get("source_confidence", "High Confidence")).strip()
                                if source_conf not in CONFIDENCE_LEVELS:
                                    source_conf = "High Confidence"

                                description = str(row.get("description", "")) if not pd.isna(row.get("description")) else ""
                                guidance = str(row.get("investigative_guidance", "")) if not pd.isna(row.get("investigative_guidance")) else ""
                                refs = str(row.get("refs", "")) if not pd.isna(row.get("refs")) else ""

                                db.add_risk_library_item(
                                    category=category,
                                    title=title,
                                    default_risk_level=risk_level,
                                    description=description,
                                    investigative_guidance=sanitize_rich_html(guidance),
                                    source_confidence=source_conf,
                                    refs=refs
                                )
                                imported_count += 1

                            st.success(f"Successfully imported {imported_count} risk templates into the Risk Library!")
                            st.rerun()

                except Exception as e:
                    st.error(f"Error reading CSV file: {e}")

    @fragment
    def render_risk_add_form():
        st.divider()
        st.subheader("Add Risk Template")
        with st.form("add_risk_template_form", clear_on_submit=True):
            a_title = st.text_input("Risk Title", placeholder="e.g., Unsanctified Foreign Entity Registration")

            col_a1, col_a2, col_a3 = st.columns(3)
            a_category = col_a1.selectbox("Category", DOMAIN_CATEGORIES)
            a_risk = col_a2.selectbox("Default Risk Level", RISK_LEVELS, index=2)
            a_conf = col_a3.selectbox("Default Source Confidence", CONFIDENCE_LEVELS, index=0)

            a_desc = st.text_area("Description", placeholder="General background and nature of this risk or vulnerability...")
            guidance_editor_key = _new_risk_guidance_editor_key()
            a_guidance = _risk_guidance_editor("", guidance_editor_key)
            a_refs = st.text_area("References & Framework Citations", placeholder="e.g., OSINT Framework, MITRE ATT&CK, Companies House API")

            if st.form_submit_button("Add to Risk Library") and a_title:
                db.add_risk_library_item(
                    category=a_category,
                    title=a_title,
                    default_risk_level=a_risk,
                    description=a_desc,
                    investigative_guidance=sanitize_rich_html(a_guidance),
                    source_confidence=a_conf,
                    refs=a_refs
                )
                st.session_state.pop(guidance_editor_key, None)
                st.session_state["new_risk_guidance_generation"] = (
                    st.session_state.get("new_risk_guidance_generation", 0) + 1
                )
                st.success(f"Added '{a_title}' to the OSINT Risk Library!")
                st.rerun()

    render_risk_entries()
    if st.session_state.get("edit_risk_id") is not None:
        return
    render_risk_bulk_import()
    render_risk_add_form()