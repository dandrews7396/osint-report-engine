import streamlit as st
import os
import base64
from database import operations as db
from reporting.generator import generate_report, generate_attestation

def show_generate_report():
    st.title("Generate Intelligence Deliverables")
    st.write("Compile all case metadata, target specifications, legal declarations, and verified intelligence findings into professional PDF deliverables.")
    
    cases = db.get_cases()
    active_client_id = st.session_state.get('active_client_id')
    if active_client_id:
        cases = [c for c in cases if c['client_id'] == active_client_id]
        
    if not cases:
        st.warning("Please create a case for the active client first.")
        return
        
    case_options = {f"[{c.get('case_ref', 'NO-REF')}] {c['case_name']} (Client: {c['client_name']})": c for c in cases}
    selected_cname = st.selectbox("Select Active Case", list(case_options.keys()))
    case = case_options[selected_cname]
    
    findings = db.get_case_findings(case['id'])
    st.info(f"**Case Reference:** `{case.get('case_ref', 'N/A')}` | **Total Findings:** `{len(findings)}`")
    
    output_dir = "reports"
    os.makedirs(output_dir, exist_ok=True)
    
    out_filename = f"{output_dir}/case_report_{case['id']}.pdf"
    out_attestation = f"{output_dir}/attestation_{case['id']}.pdf"
    
    with st.expander("Attestation / Lead Investigator Customization"):
        db_investigators = db.get_investigators()
        inv_name = case.get('investigator_name', '')
        
        if case.get('attestation_bio') is not None:
            default_bio = case.get('attestation_bio')
        else:
            default_bio = ""
            if inv_name:
                db_inv = next((i for i in db_investigators if i['name'] == inv_name), None)
                if db_inv:
                    default_bio = db_inv.get('bio', '')
        
        with st.form(f"attestation_customization_form_{case['id']}"):
            attestation_bio = st.text_area("Lead Investigator Bio for Attestation Letter", value=default_bio, height=150)
            if st.form_submit_button("Save Customization"):
                db.update_case_attestation_bio(case['id'], attestation_bio)
                st.success("Customization saved!")
                st.rerun()
    
    col_rep, col_att = st.columns(2)
    
    with col_rep:
        if st.button("Generate OSINT PDF Report", use_container_width=True, type="primary"):
            if not findings:
                st.error("No intelligence findings recorded. Please add findings before generating the report.")
            else:
                with st.spinner("Compiling Intelligence Report PDF..."):
                    clients = db.get_clients()
                    client = next((c for c in clients if c['id'] == case['client_id']), None)
                    firm = db.get_settings()
                    try:
                        generate_report(case, client, firm, findings, out_filename)
                        st.success("Intelligence Report generated successfully!")
                        
                        missing = []
                        if not case.get('investigator_name'): missing.append("Lead Investigator")
                        if not case.get('target_scope'): missing.append("Target Specification")
                        if not case.get('legitimate_interest'): missing.append("UK GDPR / Legitimate Interest Statement")
                        if not case.get('executive_summary'): missing.append("Executive Summary")
                        if not case.get('key_findings_summary'): missing.append("Key Findings Summary")
                        if not case.get('tools_used') or case.get('tools_used') == '[]' or case.get('tools_used') == '[{"Name": "", "Description": ""}]': missing.append("Tools / Platforms Utilised")
                        
                        if missing:
                            st.warning(f"Note: The following case fields are blank and may appear unpopulated in the report: {', '.join(missing)}")
                            
                    except Exception as e:
                        st.error(f"Failed to generate report: {e}")
    
    with col_att:
        if st.button("Generate Attestation Letter", use_container_width=True):
            with st.spinner("Generating Attestation Letter PDF..."):
                clients = db.get_clients()
                client = next((c for c in clients if c['id'] == case['client_id']), None)
                firm = db.get_settings()
                try:
                    generate_attestation(case, client, firm, out_attestation, custom_bio=attestation_bio)
                    st.success("Attestation Letter generated successfully!")
                    
                    missing = []
                    if not case.get('investigator_name'): missing.append("Lead Investigator")
                    if not case.get('start_date'): missing.append("Start Date")
                    if not case.get('end_date'): missing.append("End Date")
                    if not case.get('target_scope'): missing.append("Target Specification Scope")
                    if not attestation_bio: missing.append("Investigator Bio")
                    
                    if missing:
                        st.warning(f"Note: The following fields are blank and may appear unpopulated in the letter: {', '.join(missing)}")
                        
                except Exception as e:
                    st.error(f"Failed to generate attestation: {e}")
                    
    if os.path.exists(out_filename):
        st.divider()
        st.subheader("Intelligence Report Deliverable")
        with open(out_filename, "rb") as pdf_file:
            pdf_data = pdf_file.read()
            case_slug = case['case_name'].replace(' ', '_')
            st.download_button(
                label="Download OSINT PDF Report",
                data=pdf_data,
                file_name=f"OSINT_Report_{case.get('case_ref', 'REF')}_{case_slug}.pdf",
                mime="application/pdf"
            )
        with st.expander("Preview Intelligence Report"):
            base64_pdf = base64.b64encode(pdf_data).decode('utf-8')
            pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800px" type="application/pdf"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)

    if os.path.exists(out_attestation):
        st.divider()
        st.subheader("Attestation Letter Deliverable")
        with open(out_attestation, "rb") as pdf_file:
            pdf_data = pdf_file.read()
            case_slug = case['case_name'].replace(' ', '_')
            st.download_button(
                label="Download Attestation Letter",
                data=pdf_data,
                file_name=f"Attestation_{case.get('case_ref', 'REF')}_{case_slug}.pdf",
                mime="application/pdf"
            )
        with st.expander("Preview Attestation Letter"):
            base64_pdf = base64.b64encode(pdf_data).decode('utf-8')
            pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800px" type="application/pdf"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)