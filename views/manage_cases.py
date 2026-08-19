import streamlit as st
import json
import html
from datetime import date
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
        edit_case_id = st.session_state.get('edit_case_id')

        if not active_client_cases:
            st.info("*No cases found for this client. Create a new case below.*")
        for c in active_client_cases:
            is_editing = edit_case_id == c['id']
            case_label = f"[{c.get('case_ref', 'NO-REF')}] {c['case_name']} (Client: {c['client_name']})"

            if is_editing:
                st.markdown(f"#### {case_label}")
                st.caption("Editing is locked open until you save or cancel.")
                item_container = st.container()
            else:
                item_container = st.expander(case_label)

            with item_container:
                if is_editing:
                    with st.form(f"edit_case_{c['id']}"):
                        col_c1, col_c2 = st.columns(2)
                        ec_ref = col_c1.text_input("Case Reference Number", value=c.get('case_ref', ''))
                        ec_name = col_c2.text_input("Case Name", value=c['case_name'])

                        ec_type_idx = CASE_TYPES.index(c.get('case_type', 'Enhanced Due Diligence')) if c.get('case_type') in CASE_TYPES else 0
                        ec_type = st.selectbox("Case Type", CASE_TYPES, index=ec_type_idx)

                        col_s, col_e, col_r = st.columns(3)
                        ec_start = col_s.date_input(
                            "Start Date",
                            value=date.fromisoformat(c["start_date"]),
                            format="YYYY-MM-DD",
                            key=f"edit_case_start_date_{c['id']}",
                        ).isoformat()
                        ec_end = col_e.date_input(
                            "End Date",
                            value=date.fromisoformat(c["end_date"]),
                            format="YYYY-MM-DD",
                            key=f"edit_case_end_date_{c['id']}",
                        ).isoformat()
                        ec_report_date = col_r.date_input(
                            "Report Date",
                            value=date.fromisoformat(c["report_date"]),
                            format="YYYY-MM-DD",
                            key=f"edit_case_report_date_{c['id']}",
                        ).isoformat()

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
                        ec_covert_persona_reference = st.text_input(
                            "Covert Persona Reference",
                            value=c.get('covert_persona_reference', '') or '',
                            help="Optional, user-editable reference used in the report header for the persona or operating identity associated with this case.",
                        )
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
                                covert_persona_reference=ec_covert_persona_reference,
                                tools_and_sources_used=t_used_json
                            )

                            if save_as_default:
                                db.update_setting('default_legitimate_interest', ec_gdpr)
                                db.update_setting('tools_used', t_used_json)

                            st.session_state.edit_case_id = None
                            st.success("Case updated!")
                            st.rerun()

                    if st.button("Cancel Edit", key=f"cancel_case_{c['id']}"):
                        st.session_state.edit_case_id = None
                        st.rerun()
                else:
                    st.caption(f"Type: {c.get('case_type', 'Unspecified')}")
                    st.write(f"**Lead Investigator:** {c.get('investigator_name', 'Unassigned') or 'Unassigned'}")
                    st.write(
                        f"**Timeline:** {c.get('start_date', 'N/A') or 'N/A'} to {c.get('end_date', 'N/A') or 'N/A'} "
                        f"(Report date: {c.get('report_date', 'N/A') or 'N/A'})"
                    )
                    if c.get('target_scope'):
                        st.write(f"**Tasking:** {c['target_scope']}")

                    col1, col2 = st.columns(2)
                    if col1.button("Edit Case", key=f"edit_case_btn_{c['id']}", use_container_width=True):
                        st.session_state.edit_case_id = c['id']
                        st.rerun()
                    if col2.button("Delete Case", key=f"del_case_{c['id']}", use_container_width=True):
                        delete_case_dialog(c['id'], c['case_name'])

        if edit_case_id is None:
            st.divider()
            st.subheader("Add New Case")
            with st.form("add_case", clear_on_submit=True):
                st.markdown(
                    f"""
                    <div class="add-case-context-banner">
                        &#8505;&nbsp; Opening new case under client <strong>{html.escape(active_client_name)}</strong>
                    </div>
                    <style>
                    .add-case-context-banner {{
                        background-color: rgba(28, 131, 225, 0.1);
                        padding: 0.75rem 1rem;
                        border-radius: 0.5rem;
                        margin-bottom: 1rem;
                        animation: add-case-banner-fade-out 0.4s ease-in 4.6s forwards;
                    }}
                    @keyframes add-case-banner-fade-out {{
                        to {{
                            opacity: 0;
                            height: 0;
                            padding-top: 0;
                            padding-bottom: 0;
                            margin-bottom: 0;
                            overflow: hidden;
                        }}
                    }}
                    </style>
                    """,
                    unsafe_allow_html=True,
                )
                col_nc1, col_nc2 = st.columns(2)
                c_ref = col_nc1.text_input("Case Reference Number", placeholder="e.g., CAS-2026-001")
                c_name = col_nc2.text_input("Case Name", placeholder="e.g., Operation Vanguard")

                c_type = st.selectbox("Case Type", CASE_TYPES)
                c_inv = st.selectbox("Lead Investigator", list(investigator_options.keys()))
                c_covert_persona_reference = st.text_input(
                    "Covert Persona Reference",
                    key="new_case_covert_persona_reference",
                    placeholder="e.g., Persona-12 / Alias / Operating identity",
                    help="Optional reference used in the report header for the covert persona or operating identity associated with this case.",
                )

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
                        covert_persona_reference=c_covert_persona_reference,
                        tools_and_sources_used=settings.get('tools_used', '')
                    )
                    st.session_state.edit_case_id = new_id
                    st.success(f"Successfully created case: {c_name}")
                    st.rerun()

    render_manage_cases()