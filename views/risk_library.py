import streamlit as st
import pandas as pd
import io
from database import operations as db

try:
    fragment = st.fragment
except AttributeError:
    def fragment(func):
        return func

def show_risk_library():
    st.title("OSINT Risk & Threat Library")
    st.write("Manage standardized threat vectors, risk templates, and investigative guidance. These pre-configured templates can be searched, managed, and imported directly into active cases.")
    
    DOMAIN_CATEGORIES = [
        "Identity & PII",
        "Corporate Governance & Ownership",
        "Infrastructure & Network Assets",
        "Social Media & Digital Footprint",
        "Financial & Asset Tracing",
        "Dark Web & Leaked Data",
        "Geopolitical & Physical Security",
        "Custom Category"
    ]
    
    RISK_LEVELS = ["Critical", "High", "Medium", "Low", "Informational"]
    CONFIDENCE_LEVELS = ["High Confidence", "Moderate Confidence", "Low Confidence", "Unverified"]

    @fragment
    def render_risk_library_interactive_sections():
        st.subheader("Risk Library Entries")
        
        col_search, col_cat_filter = st.columns([2, 1])
        search_query = col_search.text_input("Search Library", placeholder="Search by title, description, or guidance...")
        cat_filter = col_cat_filter.selectbox("Filter by Category", ["All Categories"] + DOMAIN_CATEGORIES)

        library_items = db.get_risk_library()

        if library_items:
            if cat_filter != "All Categories":
                library_items = [item for item in library_items if item.get('category') == cat_filter]
            if search_query:
                q = search_query.lower()
                library_items = [
                    item for item in library_items 
                    if q in item['title'].lower() 
                    or q in (item.get('description') or '').lower() 
                    or q in (item.get('investigative_guidance') or '').lower()
                ]

        if not library_items:
            st.info("No risk vectors found matching the specified criteria.")
        else:
            for item in library_items:
                is_expanded = st.session_state.get('edit_risk_id') == item['id']
                expander_label = f"[{item.get('default_risk_level', 'Medium')}] {item['title']} ({item.get('category', 'Uncategorized')})"
                
                with st.expander(expander_label, expanded=is_expanded):
                    with st.form(f"edit_risk_form_{item['id']}"):
                        e_title = st.text_input("Risk Vector Title", value=item['title'])
                        
                        col1, col2, col3 = st.columns(3)
                        cat_idx = DOMAIN_CATEGORIES.index(item.get('category')) if item.get('category') in DOMAIN_CATEGORIES else 0
                        e_category = col1.selectbox("Category", DOMAIN_CATEGORIES, index=cat_idx, key=f"cat_{item['id']}")
                        
                        risk_idx = RISK_LEVELS.index(item.get('default_risk_level')) if item.get('default_risk_level') in RISK_LEVELS else 2
                        e_risk = col2.selectbox("Default Risk Level", RISK_LEVELS, index=risk_idx, key=f"risk_{item['id']}")
                        
                        conf_idx = CONFIDENCE_LEVELS.index(item.get('source_confidence', 'High Confidence')) if item.get('source_confidence') in CONFIDENCE_LEVELS else 0
                        e_conf = col3.selectbox("Default Source Confidence", CONFIDENCE_LEVELS, index=conf_idx, key=f"conf_{item['id']}")
                        
                        e_desc = st.text_area("Vector Description", value=item.get('description', '') or '', height=100)
                        e_guidance = st.text_area("Investigative Guidance / Next Steps", value=item.get('investigative_guidance', '') or '', height=120)
                        e_refs = st.text_area("References & Framework Citations (one per line)", value=item.get('refs', '') or '', height=80)
                        
                        if st.form_submit_button("Save Changes"):
                            db.update_risk_library_item(
                                item['id'],
                                e_category,
                                e_title,
                                e_risk,
                                e_desc,
                                e_guidance,
                                e_conf,
                                e_refs
                            )
                            st.session_state.edit_risk_id = None
                            st.success("Updated risk vector template.")
                            st.rerun()

                    col_del1, col_del2 = st.columns([1, 4])
                    if col_del1.button("Delete Entry", key=f"del_risk_{item['id']}", type="primary"):
                        db.delete_risk_library_item(item['id'])
                        st.success("Deleted risk vector.")
                        st.rerun()

        st.divider()

        # --- BULK IMPORT SECTION ---
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
                            # Normalize column headers to lowercase
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
                                    investigative_guidance=guidance,
                                    source_confidence=source_conf,
                                    refs=refs
                                )
                                imported_count += 1

                            st.success(f"Successfully imported {imported_count} risk templates into the Risk Library!")
                            st.rerun()

                except Exception as e:
                    st.error(f"Error reading CSV file: {e}")

        st.divider()
        st.subheader("Add Single Risk Vector Template")
        with st.form("add_risk_template_form", clear_on_submit=True):
            a_title = st.text_input("Risk Vector Title", placeholder="e.g., Unsanctified Foreign Entity Registration")
            
            col_a1, col_a2, col_a3 = st.columns(3)
            a_category = col_a1.selectbox("Category", DOMAIN_CATEGORIES)
            a_risk = col_a2.selectbox("Default Risk Level", RISK_LEVELS, index=2)
            a_conf = col_a3.selectbox("Default Source Confidence", CONFIDENCE_LEVELS, index=0)
            
            a_desc = st.text_area("Vector Description", placeholder="General background and nature of this risk or vulnerability...")
            a_guidance = st.text_area("Investigative Guidance / Recommended Steps", placeholder="Standard operating procedures to investigate, verify, and document this finding...")
            a_refs = st.text_area("References & Framework Citations", placeholder="e.g., OSINT Framework, MITRE ATT&CK, Companies House API")
            
            if st.form_submit_button("Add to Risk Library") and a_title:
                db.add_risk_library_item(
                    category=a_category,
                    title=a_title,
                    default_risk_level=a_risk,
                    description=a_desc,
                    investigative_guidance=a_guidance,
                    source_confidence=a_conf,
                    refs=a_refs
                )
                st.success(f"Added '{a_title}' to the OSINT Risk Library!")
                st.rerun()

    render_risk_library_interactive_sections()