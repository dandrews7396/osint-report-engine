import streamlit as st
import json
from database import operations as db

try:
    fragment = st.fragment
except AttributeError:
    def fragment(func):
        return func

@st.dialog("Confirm Deletion")
def delete_case_dialog(case_id, case_name):
    st.warning(f"Are you sure you want to delete Case '{case_name}'? This action cannot be undone.")
    col1, col2 = st.columns(2)
    if col1.button("Yes, Delete", type="primary", use_container_width=True):
        db.delete_case(case_id)
        st.rerun()
    if col2.button("Cancel", use_container_width=True):
        st.rerun()

def show_manage_cases():
    @fragment
    def render_manage_cases():
        st.title("Manage Intelligence Cases")
        st.write("Create and edit OSINT cases for your active client. Define case parameters, primary targets, legal/GDPR legitimate interest justification, assigned investigators, and intelligence tools.")

        clients = db.get_clients()
        if not clients:
            st.warning("Please create a client on the Dashboard first.")
            return

        client_options = {c['name']: c['id'] for c in clients}
        active_client_id = st.session_state.get('active_client_id')
        if active_client_id not in client_options.values():
            active_client_id = clients[0]['id']
            st.session_state.active_client_id = active_client_id

        active_client_name = next(c['name'] for c in clients if c['id'] == active_client_id)

        CASE_TYPES = [
            "Enhanced Due Diligence",
            "Executive Threat Assessment",
            "Asset Tracing & Recovery",
            "Brand Protection & Anti-Counterfeiting",
            "Insider Threat Investigation",
            "Fraud & Financial Crime Investigation",
            "Person Profile",
            "Custom OSINT Investigation"
        ]

        investigators = db.get_investigators()
        investigator_options = {"No Investigator": {"name": "", "title": "", "credentials": "", "bio": ""}}
        if investigators:
            for inv in investigators:
                investigator_options[inv['name']] = inv

        st.subheader(f"Active Cases for {active_client_name}")
        cases = db.get_cases()
        active_client_cases = [c for c in cases if c['client_id'] == active_client_id]

        if not active_client_cases:
            st.info("*No cases found for this client. Create a new case below.*")

        for c in active_client_cases:
            is_expanded = st.session_state.get('edit_case_id') == c['id']
            case_label = f"[{c.get('case_ref', 'NO-REF')}] {c['case_name']} (Client: {c['client_name']})"

            with st.expander(case_label, expanded=is_expanded):
                with st.form(f"edit_case_{c['id']}"):
                    col_c1, col_c2 = st.columns(2)
                    ec_ref = col_c1.text_input("Case Reference Number", value=c.get('case_ref', ''))
                    ec_name = col_c2.text_input("Case Name", value=c['case_name'])

                    ec_type_idx = CASE_TYPES.index(c.get('case_type', 'Enhanced Due Diligence')) if c.get('case_type') in CASE_TYPES else 0
                    ec_type = st.selectbox("Case Type", CASE_TYPES, index=ec_type_idx)

                    col_s, col_e, col_r = st.columns(3)
                    ec_start = col_s.text_input("Start Date", value=c.get('start_date', ''))
                    ec_end = col_e.text_input("End Date", value=c.get('end_date', ''))
                    ec_report_date = col_r.text_input("Report Date", value=c.get('report_date', ''))

                    st.markdown("### Tasking & Legal Framework")
                    ec_tasking = st.text_area("Tasking Specification (Entities, Individuals, Domains, Handles)", value=c.get('target_scope', '') or '', height=100)
                    ec_gdpr = st.text_area("UK GDPR / Legitimate Interest Statement", value=c.get('legitimate_interest', '') or '', height=100, help="Document the lawful basis and necessity for processing personal data under UK GDPR.")

                    st.markdown("### Assignment & Narrative")
                    ec_inv_idx = 0
                    ec_inv_name = c.get('investigator_name', '')
                    inv_names = list(investigator_options.keys())
                    if ec_inv_name in inv_names:
                        ec_inv_idx = inv_names.index(ec_inv_name)

                    ec_inv = st.selectbox("Lead Investigator", inv_names, index=ec_inv_idx)
                    ec_exec_summary = st.text_area("Executive Summary", value=c.get('executive_summary', '') or '', height=120)
                    ec_key_findings = st.text_area("Key Intelligence Findings Summary", value=c.get('key_findings_summary', '') or '', height=120)

                    st.markdown("#### OSINT Tools & Platforms Utilised")
                    tools_str = c.get('tools_used', '[]')
                    try:
                        t_list = json.loads(tools_str)
                        if not isinstance(t_list, list):
                            t_list = [{"Name": "Tool", "Description": tools_str}]
                    except Exception:
                        t_list = [{"Name": "Unknown Tool", "Description": tools_str}] if tools_str else []

                    if not t_list:
                        t_list = [{"Name": "", "Description": ""}]

                    edited_t_list = st.data_editor(
                        t_list,
                        column_config={
                            "Name": st.column_config.TextColumn("Tool / Platform Name", width="medium", required=True),
                            "Description": st.column_config.TextColumn("Purpose / Usage Description", width="large", required=True)
                        },
                        num_rows="dynamic",
                        use_container_width=True,
                        key=f"te_{c['id']}"
                    )

                    save_as_default = st.checkbox("Save legal statement and tool configuration as Firm Defaults", key=f"sad_{c['id']}")

                    if st.form_submit_button("Save Case Details"):
                        cleaned_t_list = [t for t in edited_t_list if t.get("Name") or t.get("Description")]
                        t_used_json = json.dumps(cleaned_t_list)
                        selected_inv = investigator_options[ec_inv]

                        db.update_case(
                            case_id=c['id'],
                            case_ref=ec_ref,
                            case_name=ec_name,
                            case_type=ec_type,
                            start_date=ec_start,
                            end_date=ec_end,
                            report_date=ec_report_date,
                            lead_investigator=selected_inv['name'],
                            investigator_description=selected_inv['bio'],
                            target_scope=ec_tasking,
                            legitimate_interest_assessment=ec_gdpr,
                            executive_assessment=ec_exec_summary,
                            key_findings_summary=ec_key_findings,
                            tools_and_sources_used=t_used_json
                        )

                        if save_as_default:
                            db.update_setting('default_legitimate_interest', ec_gdpr)
                            db.update_setting('tools_used', t_used_json)

                        st.success("Case updated!")
                        st.rerun()

                if st.button("Delete Case", key=f"del_case_{c['id']}"):
                    delete_case_dialog(c['id'], c['case_name'])

        st.divider()
        st.subheader("Add New Case")
        with st.form("add_case", clear_on_submit=True):
            st.info(f"Opening new case under client **{active_client_name}**")
            col_nc1, col_nc2 = st.columns(2)
            c_ref = col_nc1.text_input("Case Reference Number", placeholder="e.g., CAS-2026-001")
            c_name = col_nc2.text_input("Case Name", placeholder="e.g., Operation Vanguard")

            c_type = st.selectbox("Case Type", CASE_TYPES)
            c_inv = st.selectbox("Lead Investigator", list(investigator_options.keys()))

            col_s, col_e, col_r = st.columns(3)
            c_start = col_s.date_input("Start Date").strftime('%Y-%m-%d')
            c_end = col_e.date_input("End Date").strftime('%Y-%m-%d')
            c_report_date = col_r.date_input("Report Date").strftime('%Y-%m-%d')

            if st.form_submit_button("Add Case") and c_name:
                settings = db.get_settings()
                selected_inv = investigator_options[c_inv]

                new_id = db.add_case(
                    case_ref=c_ref,
                    case_name=c_name,
                    client_id=active_client_id,
                    case_type=c_type,
                    start_date=c_start,
                    end_date=c_end,
                    report_date=c_report_date,
                    lead_investigator=selected_inv['name'],
                    investigator_description=selected_inv['bio'],
                    target_scope='',
                    legitimate_interest_assessment=settings.get('default_legitimate_interest', ''),
                    executive_assessment='',
                    key_findings_summary='',
                    tools_and_sources_used=settings.get('tools_used', '')
                )
                st.session_state.edit_case_id = new_id
                st.success(f"Successfully created case: {c_name}")
                st.rerun()

    render_manage_cases()