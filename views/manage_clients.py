import streamlit as st
from database import operations as db

try:
    fragment = st.fragment
except AttributeError:
    def fragment(func):
        return func


def show_manage_clients():
    @fragment
    def render_manage_clients():
        st.title("Manage Clients")
        st.write("Create, edit, and activate client records.")

        clients = db.get_clients()
        if not clients:
            st.info("No clients found. Add one below to get started.")

        with st.form("add_client_form", clear_on_submit=True):
            st.subheader("Add New Client")
            c_f1, c_f2 = st.columns(2)
            c_name = c_f1.text_input("Client Name")
            c_type = c_f2.selectbox(
                "Client Type",
                ["Law Firm", "Corporate Security", "Financial Institution", "Private Client", "Government"]
            )
            c_email = st.text_input("Contact Email")
            c_desc = st.text_area("Description / Notes")
            if st.form_submit_button("Add Client") and c_name:
                db.add_client(c_name, c_type, c_email, c_desc)
                st.success(f"Added client: {c_name}")
                st.rerun()

        if not clients:
            return

        st.divider()
        st.subheader("Current Clients")
        for client in clients:
            with st.expander(client["name"], expanded=False):
                with st.form(f"edit_client_{client['id']}"):
                    e_name = st.text_input("Client Name", value=client.get("name", ""))
                    e_type = st.text_input("Client Type", value=client.get("client_type", "Law Firm"))
                    e_email = st.text_input("Contact Email", value=client.get("contact_email", "") or "")
                    e_desc = st.text_area("Description / Notes", value=client.get("description", "") or "")

                    if st.form_submit_button("Save Changes"):
                        db.update_client(client["id"], e_name, e_type, e_email, e_desc)
                        st.success("Client updated.")
                        st.rerun()

                col1, col2 = st.columns(2)
                if col1.button("Set Active", key=f"active_client_{client['id']}"):
                    st.session_state.active_client_id = client["id"]
                    st.session_state.nav = "Manage Cases"
                    st.rerun()
                if col2.button("Delete Client", key=f"delete_client_{client['id']}"):
                    db.delete_client(client["id"])
                    st.success("Client deleted.")
                    st.rerun()

    render_manage_clients()
