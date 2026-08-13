import os
import streamlit as st
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
    del_subjects = db.get_deleted_case_subjects()
    del_findings = db.get_deleted_case_findings()

    if not del_clients and not del_cases and not del_subjects and not del_findings:
        st.info("The recycle bin is empty.")
        return

    if del_clients:
        st.markdown("### Deleted Clients")
        for c in del_clients:
            col1, col2, col3 = st.columns([2, 1, 1])
            col1.write(c["name"])
            if col2.button("Restore", key=f"rc_{c['id']}"):
                db.restore_client(c["id"])
                st.rerun()
            if col3.button("Permanently Delete", key=f"hdc_{c['id']}", type="primary"):
                db.hard_delete_client(c["id"])
                st.rerun()

    if del_cases:
        st.markdown("### Deleted Cases")
        for c in del_cases:
            col1, col2, col3 = st.columns([2, 1, 1])
            col1.write(f"{c['case_name']} ({c.get('client_name', 'Unknown')})")
            if col2.button("Restore", key=f"rp_{c['id']}"):
                db.restore_case(c["id"])
                st.rerun()
            if col3.button("Permanently Delete", key=f"hdp_{c['id']}", type="primary"):
                db.hard_delete_case(c["id"])
                st.rerun()

    if del_subjects:
        st.markdown("### Deleted Case Subjects")
        for s in del_subjects:
            col1, col2, col3 = st.columns([2, 1, 1])
            col1.write(f"{s['display_name']} ({s.get('case_name', 'Unknown')})")
            if col2.button("Restore", key=f"rs_{s['id']}"):
                db.restore_case_subject(s["id"])
                st.rerun()
            if col3.button("Permanently Delete", key=f"hds_{s['id']}", type="primary"):
                db.hard_delete_case_subject(s["id"])
                st.rerun()

    if del_findings:
        st.markdown("### Deleted Intelligence Findings")
        for f in del_findings:
            col1, col2, col3 = st.columns([2, 1, 1])
            subject_suffix = f" — {f['subject_name']}" if f.get('subject_name') else ""
            col1.write(f"{f['title']}{subject_suffix} ({f.get('case_name', 'Unknown')})")
            if col2.button("Restore", key=f"rf_{f['id']}"):
                db.restore_case_finding(f["id"])
                st.rerun()
            if col3.button("Permanently Delete", key=f"hdf_{f['id']}", type="primary"):
                db.hard_delete_case_finding(f["id"])
                st.rerun()


def show_settings():
    @fragment
    def render_settings():
        st.title("Settings")
        st.write("Manage firm details, investigators, and recovery tools.")

        settings = db.get_settings()
        with st.form("firm_settings_form"):
            st.subheader("Firm Settings")
            c_f1, c_f2 = st.columns(2)
            firm_name = c_f1.text_input("Firm Name", value=settings.get("firm_name", "Default Intelligence Firm"))
            firm_website = c_f2.text_input("Firm Website", value=settings.get("firm_website", ""))
            if st.form_submit_button("Save Firm Settings"):
                db.update_setting("firm_name", firm_name)
                db.update_setting("firm_website", firm_website)
                st.success("Firm settings updated.")
                st.rerun()

        st.divider()
        st.subheader("Investigative Team")
        investigators = db.get_investigators()
        if investigators:
            for inv in investigators:
                with st.expander(f"{inv['name']}"):
                    with st.form(f"edit_inv_{inv['id']}"):
                        col_t1, col_t2 = st.columns(2)
                        e_inv_name = col_t1.text_input("Name", value=inv.get("name", ""))
                        e_inv_title = col_t2.text_input("Title", value=inv.get("title", "") or "")
                        e_inv_creds = st.text_input("Credentials / Certifications", value=inv.get("credentials", "") or "")
                        e_inv_bio = st.text_area("Bio / Professional Background", value=inv.get("bio", "") or "")
                        if st.form_submit_button("Save Changes"):
                            db.update_investigator(inv["id"], e_inv_name, e_inv_title, e_inv_creds, e_inv_bio)
                            st.success("Investigator updated.")
                            st.rerun()
                    if st.button("Delete Investigator", key=f"del_inv_{inv['id']}"):
                        db.delete_investigator(inv["id"])
                        st.rerun()
        else:
            st.info("No investigators added yet.")

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

        st.divider()
        st.subheader("Data Recovery")
        if st.button("Open Deleted Items Recovery", use_container_width=True):
            restore_files_dialog()

        if os.path.exists("kairos_backup.zip"):
            with open("kairos_backup.zip", "rb") as f:
                st.download_button("Download Latest Backup", data=f, file_name="kairos_backup.zip", mime="application/zip")

    render_settings()
