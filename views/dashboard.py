import streamlit as st
import os
from database import operations as db

try:
    fragment = st.fragment
except AttributeError:
    def fragment(func):
        return func

@st.dialog("Restore Deleted Files")
def restore_files_dialog():
    db.cleanup_deleted_items()
    st.write("Items deleted within the last 30 days can be restored here.")
    
    del_clients = db.get_deleted_clients()
    del_cases = db.get_deleted_cases()
    del_findings = db.get_deleted_case_findings()
    
    if not del_clients and not del_cases and not del_findings:
        st.info("The recycle bin is empty.")
        return
        
    if del_clients:
        st.markdown("### Deleted Clients")
        for c in del_clients:
            col1, col2, col3 = st.columns([2, 1, 1])
            col1.write(c['name'])
            if col2.button("Restore", key=f"rc_{c['id']}"):
                db.restore_client(c['id'])
                st.rerun()
            if col3.button("Permanently Delete", key=f"hdc_{c['id']}", type="primary"):
                db.hard_delete_client(c['id'])
                st.rerun()
                
    if del_cases:
        st.markdown("### Deleted Cases")
        for c in del_cases:
            col1, col2, col3 = st.columns([2, 1, 1])
            col1.write(f"{c['case_name']} ({c.get('client_name', 'Unknown')})")
            if col2.button("Restore", key=f"rp_{c['id']}"):
                db.restore_case(c['id'])
                st.rerun()
            if col3.button("Permanently Delete", key=f"hdp_{c['id']}", type="primary"):
                db.hard_delete_case(c['id'])
                st.rerun()
                
    if del_findings:
        st.markdown("### Deleted Intelligence Findings")
        for f in del_findings:
            col1, col2, col3 = st.columns([2, 1, 1])
            col1.write(f"{f['title']} ({f.get('case_name', 'Unknown')})")
            if col2.button("Restore", key=f"rf_{f['id']}"):
                db.restore_case_finding(f['id'])
                st.rerun()
            if col3.button("Permanently Delete", key=f"hdf_{f['id']}", type="primary"):
                db.hard_delete_case_finding(f['id'])
                st.rerun()

def show_dashboard():
    @fragment
    def render_dashboard_page():
        st.title("OSINT Intelligence Engine")
        st.write("Welcome to the OSINT Intelligence Engine. Use this dashboard as your central hub to manage intelligence cases, client rosters, firm configuration, and investigative personnel.")

        def render_dashboard_metrics():
            clients = db.get_clients()
            cases = db.get_cases()
            risks = db.get_risk_library()

            col1, col2, col3 = st.columns(3)
            col1.metric("Active Clients", len(clients))
            col2.metric("Total Cases", len(cases))
            col3.metric("Risk Templates", len(risks))

        def render_client_overview():
            st.divider()
            st.subheader("Client Overview")

            with st.expander("Add New Client"):
                with st.form("dash_add_client"):
                    c_f1, c_f2 = st.columns(2)
                    c_name = c_f1.text_input("Client Name")
                    c_type = c_f2.selectbox("Client Type", ["Law Firm", "Corporate Security", "Financial Institution", "Private Client", "Government"])
                    c_email = st.text_input("Contact Email")
                    c_desc = st.text_area("Description / Notes")
                    if st.form_submit_button("Add Client") and c_name:
                        db.add_client(c_name, c_type, c_email, c_desc)
                        st.success(f"Added client: {c_name}")
                        st.rerun()

            clients = db.get_clients()
            cases = db.get_cases()

            if not clients:
                st.info("No clients found. Add a new client above to get started.")
                return

            client_options = {c['name']: c['id'] for c in clients}
            client_options_list = list(client_options.keys())
            default_index = 0
            if 'dashboard_active_client_id' not in st.session_state:
                if 'active_client_id' in st.session_state:
                    st.session_state.dashboard_active_client_id = st.session_state.active_client_id
                else:
                    recent_client = db.get_client_with_most_recent_finding()
                    if recent_client:
                        st.session_state.dashboard_active_client_id = recent_client
                    else:
                        st.session_state.dashboard_active_client_id = client_options[client_options_list[0]]

            for i, c_name in enumerate(client_options_list):
                if client_options[c_name] == st.session_state.dashboard_active_client_id:
                    default_index = i
                    break

            selected_client_name = st.selectbox(
                "Active Client",
                client_options_list,
                index=default_index,
                key="dashboard_selected_client_name",
            )
            client_id = client_options[selected_client_name]
            st.session_state.active_client_id = client_id
            st.session_state.dashboard_active_client_id = client_id

            client_cases = [c for c in cases if c['client_id'] == client_id]

            if client_cases:
                st.markdown(f"**Cases for {selected_client_name}**")
                for cc in client_cases:
                    with st.container():
                        col_pn, col_pb1, col_pb2 = st.columns([2, 1, 1])
                        col_pn.write(f"- **[{cc.get('case_ref', 'NO-REF')}]** {cc['case_name']} *({cc.get('case_type', 'Unknown Type')})*")
                        if col_pb1.button("Edit Case", key=f"dash_go_case_{cc['id']}"):
                            st.session_state.nav = "Manage Cases"
                            st.session_state.edit_case_id = cc['id']
                            st.rerun()
                        if col_pb2.button("Add Findings", key=f"dash_add_find_{cc['id']}"):
                            st.session_state.nav = "Case Findings"
                            st.session_state.manage_findings_case_id = cc['id']
                            st.rerun()
            else:
                st.write(f"*No cases assigned to {selected_client_name} yet.*")

        def render_firm_and_team():
            st.divider()

            settings = db.get_settings()
            st.subheader("Firm Settings")
            with st.form("dash_firm_settings"):
                c_f1, c_f2 = st.columns(2)
                firm_name = c_f1.text_input("Firm Name", value=settings.get('firm_name', 'Default Intelligence Firm'))
                firm_website = c_f2.text_input("Firm Website", value=settings.get('firm_website', ''))
                if st.form_submit_button("Save Firm Settings"):
                    db.update_setting('firm_name', firm_name)
                    db.update_setting('firm_website', firm_website)
                    st.success("Firm Settings updated!")
                    st.rerun()

            st.subheader("Investigative Team")
            investigators = db.get_investigators()
            if investigators:
                for inv in investigators:
                    with st.expander(f"**{inv['name']}** ({inv.get('credentials', 'No Credentials')})"):
                        with st.form(f"edit_inv_{inv['id']}"):
                            col_t1, col_t2 = st.columns(2)
                            e_inv_name = col_t1.text_input("Name", value=inv['name'])
                            e_inv_title = col_t2.text_input("Title", value=inv.get('title', ''))
                            e_inv_creds = st.text_input("Credentials / Certifications", value=inv.get('credentials', ''))
                            e_inv_bio = st.text_area("Bio / Professional Background", value=inv['bio'])
                            if st.form_submit_button("Save Changes"):
                                db.update_investigator(inv['id'], e_inv_name, e_inv_title, e_inv_creds, e_inv_bio)
                                st.success("Investigator updated.")
                                st.rerun()
                        if st.button("Delete Investigator", key=f"del_inv_{inv['id']}"):
                            db.delete_investigator(inv['id'])
                            st.rerun()
            else:
                st.write("No investigators added yet.")

            with st.expander("Add New Investigator"):
                with st.form("add_investigator"):
                    col_t1, col_t2 = st.columns(2)
                    inv_name = col_t1.text_input("Name")
                    inv_title = col_t2.text_input("Title")
                    inv_creds = st.text_input("Credentials / Certifications", placeholder="e.g., CIFI, OSINT-S, CII")
                    inv_bio = st.text_area("Bio / Professional Background")
                    if st.form_submit_button("Add Investigator") and inv_name:
                        db.add_investigator(inv_name, inv_title, inv_creds, inv_bio)
                        st.success("Added investigator.")
                        st.rerun()

        def render_data_management():
            st.divider()
            st.subheader("Data Management")
            st.write("Export your entire local database and investigation assets to a portable ZIP archive, or recover deleted intelligence records.")

            col_dm1, col_dm2 = st.columns(2)
            with col_dm1:
                if st.button("Generate Backup Archive", use_container_width=True):
                    import shutil
                    shutil.make_archive('kairos_backup', 'zip', 'data')
                    st.session_state.backup_ready = True
                    st.rerun()

                if st.session_state.get('backup_ready'):
                    if os.path.exists('kairos_backup.zip'):
                        with open('kairos_backup.zip', 'rb') as f:
                            st.download_button("Download ZIP", data=f, file_name="kairos_backup.zip", mime="application/zip", use_container_width=True)

            with col_dm2:
                if st.button("Restore Deleted Files", use_container_width=True):
                    restore_files_dialog()

        render_dashboard_metrics()
        render_client_overview()
        render_firm_and_team()
        render_data_management()

    render_dashboard_page()