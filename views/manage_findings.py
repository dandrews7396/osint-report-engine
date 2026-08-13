import streamlit as st
from database import operations as db
from streamlit_jodit import st_jodit
from utils.helpers import process_base64_images, restore_base64_images, sanitize_rich_html

try:
    fragment = st.fragment
except AttributeError:
    def fragment(func):
        return func

def show_manage_findings():
    @fragment
    def render_findings_page():
        st.title("Case Findings & Intelligence")
        st.write("Populate your cases with verified OSINT findings. You can manually enter findings with digital evidence details or import standardized threat vectors directly from your OSINT Risk Library.")

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
        if 'manage_findings_case_id' in st.session_state:
            for i, c_name in enumerate(case_options_list):
                if case_options[c_name] == st.session_state.manage_findings_case_id:
                    default_index = i
                    break

        selected_case_label = st.selectbox(
            "Select Active Case",
            case_options_list,
            index=default_index,
            key="manage_findings_selected_case_label",
        )
        case_id = case_options[selected_case_label]
        st.session_state.manage_findings_case_id = case_id
        active_case = next((c for c in cases if c['id'] == case_id), None)
        subjects = db.get_case_subjects(case_id)
        subject_options = {"No Subject Linked": None}
        for subject in subjects:
            subject_options[f"#{subject['id']} [{subject['subject_type']}] {subject['display_name']} — {subject['relationship_to_case']}"] = subject['id']
        subject_option_labels = list(subject_options.keys())

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

        def render_findings_list():
            st.divider()
            st.subheader("Current Case Intelligence Findings")

            findings = db.get_case_findings_overview(case_id)
            if not findings:
                st.info("No intelligence findings added to this case yet.")
                return

            for f in findings:
                is_expanded = st.session_state.get('edit_finding_id') == f['id']
                with st.expander(
                    f"[{f.get('risk_level', 'Unspecified')}] [{f.get('confidence_level', 'Unspecified')}] {f.get('title', 'Untitled')} ({f.get('category', 'General')})",
                    expanded=is_expanded,
                ):
                    if f.get('subject_name'):
                        st.caption(f"Linked subject: {f['subject_name']}")
                    if is_expanded:
                        full_finding = db.get_case_finding(f['id']) or f
                        with st.form(f"edit_form_{f['id']}"):
                            e_title = st.text_input("Finding Title", value=full_finding['title'])

                            col_cat, col_risk, col_conf = st.columns(3)
                            cat_idx = DOMAIN_CATEGORIES.index(full_finding['category']) if full_finding['category'] in DOMAIN_CATEGORIES else 0
                            e_category = col_cat.selectbox("Domain Category", DOMAIN_CATEGORIES, index=cat_idx)

                            risk_idx = RISK_LEVELS.index(full_finding['risk_level']) if full_finding['risk_level'] in RISK_LEVELS else 2
                            e_risk = col_risk.selectbox("Risk Level", RISK_LEVELS, index=risk_idx)

                            conf_idx = CONFIDENCE_LEVELS.index(full_finding.get('confidence_level', 'High Confidence')) if full_finding.get('confidence_level') in CONFIDENCE_LEVELS else 0
                            e_conf = col_conf.selectbox("Source Confidence", CONFIDENCE_LEVELS, index=conf_idx)

                            subject_index = 0
                            if full_finding.get('subject_id') in subject_options.values():
                                for i, label in enumerate(subject_option_labels):
                                    if subject_options[label] == full_finding.get('subject_id'):
                                        subject_index = i
                                        break
                            e_subject_label = st.selectbox(
                                "Linked Subject (optional)",
                                subject_option_labels,
                                index=subject_index,
                            )
                            e_subject_id = subject_options[e_subject_label]

                            e_summary = st.text_area("Executive Summary", value=full_finding.get('summary', '') or '', height=100)

                            st.markdown("**Detailed Findings & Intelligence Analysis**")
                            st.caption("You can paste images directly into this field; processing happens when you save.")
                            jodit_config = {
                                "theme": "dark",
                                "style": {"background": "#0e1117", "color": "#ffffff"},
                                "height": 350,
                                "uploader": {"insertImageAsBase64URI": True},
                            }
                            safe_details = restore_base64_images(full_finding.get('description', '') or '')
                            e_details = st_jodit(value=safe_details, config=jodit_config, key=f"e_details_{f['id']}")

                            st.markdown("**Digital Evidence & Provenance**")
                            col_e1, col_e2 = st.columns(2)
                            e_url = col_e1.text_input("Evidence URL / Archive Link", value=full_finding.get('evidence_url', '') or '')
                            e_hash = col_e2.text_input("Evidence File SHA-256 Hash", value=full_finding.get('evidence_hash_sha256', '') or '')
                            e_citation = st.text_input("Source Citation / Document Reference", value=full_finding.get('source_citation', '') or '')

                            if st.form_submit_button("Save Changes"):
                                processed_details = process_base64_images(sanitize_rich_html(e_details), active_case['client_id'], case_id)
                                db.update_case_finding(
                                    f['id'],
                                    e_category,
                                    e_title,
                                    e_risk,
                                    e_conf,
                                    e_summary,
                                    processed_details,
                                    e_url,
                                    e_hash,
                                    e_citation,
                                    subject_id=e_subject_id
                                )
                                st.session_state.edit_finding_id = None
                                st.success("Finding updated!")
                                st.rerun()

                        if st.button("Cancel Edit", key=f"cancel_find_{f['id']}"):
                            st.session_state.edit_finding_id = None
                            st.rerun()
                    else:
                        st.write(f"**Source Confidence:** {f.get('source_confidence', 'Unspecified')}")
                        if f.get('summary'):
                            st.write(f"**Summary:** {f['summary']}")
                        if f.get('evidence_url'):
                            st.write(f"**Evidence URL:** [{f['evidence_url']}]({f['evidence_url']})")
                        if f.get('evidence_hash_sha256'):
                            st.caption(f"**SHA-256:** `{f['evidence_hash_sha256']}`")

                        col1, col2 = st.columns(2)
                        if col1.button("Edit Finding", key=f"edit_find_btn_{f['id']}"):
                            st.session_state.edit_finding_id = f['id']
                            st.rerun()
                        if col2.button("Delete Finding", key=f"del_find_{f['id']}"):
                            db.delete_case_finding(f['id'])
                            st.rerun()

        def render_findings_import():
            st.divider()
            with st.expander("Import Vector from Risk Library"):
                risk_lib = db.get_risk_library()

                if not risk_lib:
                    st.info("No pre-populated risk vectors found in the library.")
                else:
                    with st.form("import_from_risk_lib"):
                        lib_options = {f"[{v['default_risk_level']}] {v['title']} ({v.get('category', 'General')})": v for v in risk_lib}
                        selected_vector_name = st.selectbox("Select Threat Vector", list(lib_options.keys()))
                        imported_subject_label = st.selectbox("Linked Subject (optional)", subject_option_labels)
                        imported_subject_id = subject_options[imported_subject_label]

                        if st.form_submit_button("Import to Case") and selected_vector_name:
                            selected_v = lib_options[selected_vector_name]
                            db.add_case_finding(
                                case_id=case_id,
                                subject_id=imported_subject_id,
                                domain_category=selected_v.get('category', 'Custom Category'),
                                title=selected_v['title'],
                                risk_level=selected_v['default_risk_level'],
                                source_confidence=selected_v.get('source_confidence', 'High Confidence'),
                                summary=selected_v.get('description', ''),
                                detailed_findings=sanitize_rich_html(selected_v.get('investigative_guidance', '')),
                                evidence_url='',
                                evidence_hash_sha256='',
                                source_citation=selected_v.get('refs', '')
                            )
                            st.success(f"Imported '{selected_v['title']}' to case.")
                            st.rerun()

        def render_findings_add_form():
            st.divider()
            if 'add_finding_key' not in st.session_state:
                st.session_state.add_finding_key = 0

            st.subheader("Add Manual Intelligence Finding")
            with st.form(f"add_manual_finding_{st.session_state.add_finding_key}", clear_on_submit=True):
                mf_title = st.text_input("Finding Title", placeholder="e.g., Unsanctified Corporate Entity Registered in Offshore Jurisdiction")

                col_m1, col_m2, col_m3 = st.columns(3)
                mf_category = col_m1.selectbox("Domain Category", DOMAIN_CATEGORIES)
                mf_risk = col_m2.selectbox("Risk Level", RISK_LEVELS)
                mf_conf = col_m3.selectbox("Source Confidence", CONFIDENCE_LEVELS)

                mf_summary = st.text_area("Executive Summary", placeholder="Brief high-level summary of the intelligence item...")
                mf_subject_label = st.selectbox("Linked Subject (optional)", subject_option_labels)
                mf_subject_id = subject_options[mf_subject_label]

                st.markdown("**Detailed Findings & Narrative**")
                st.caption("You can paste images directly into this field; processing happens when you add the finding.")
                jodit_config = {
                    "theme": "dark",
                    "style": {"background": "#0e1117", "color": "#ffffff"},
                    "placeholder": "Enter detailed analytical narrative, screenshots, or extracted raw intelligence here...",
                    "height": 350,
                    "uploader": {"insertImageAsBase64URI": True},
                }
                mf_details = st_jodit(value="", config=jodit_config, key=f"mf_details_add_{st.session_state.add_finding_key}")

                st.markdown("**Digital Evidence & Chain of Custody**")
                col_me1, col_me2 = st.columns(2)
                mf_url = col_me1.text_input("Evidence URL / Snapshot Link")
                mf_hash = col_me2.text_input("Evidence File SHA-256 Hash")
                mf_citation = st.text_input("Source Citation / Platform Name", placeholder="e.g., UK Companies House / OpenCorporates API")

                if st.form_submit_button("Add Finding") and mf_title:
                    processed_mf_details = process_base64_images(sanitize_rich_html(mf_details), active_case['client_id'], case_id)
                    db.add_case_finding(
                        case_id=case_id,
                        subject_id=mf_subject_id,
                        domain_category=mf_category,
                        title=mf_title,
                        risk_level=mf_risk,
                        source_confidence=mf_conf,
                        summary=mf_summary,
                        detailed_findings=processed_mf_details,
                        evidence_url=mf_url,
                        evidence_hash_sha256=mf_hash,
                        source_citation=mf_citation
                    )
                    st.success("Finding successfully added to case!")
                    st.session_state.add_finding_key += 1
                    st.rerun()

        render_findings_list()
        render_findings_import()
        render_findings_add_form()

    render_findings_page()