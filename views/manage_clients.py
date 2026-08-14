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
        edit_client_id = st.session_state.get("edit_client_id")

        st.divider()
        st.subheader("Current Clients")
        if not clients:
            st.info("No clients found. Add one below to get started.")
        else:
            active_client_id = st.session_state.get("active_client_id")
            for client in clients:
                is_active = active_client_id == client["id"]
                is_editing = edit_client_id == client["id"]
                label = f"{client['name']}{' (Active)' if is_active else ''}"
                if is_editing:
                    st.markdown(f"#### {label}")
                    st.caption("Editing is locked open until you save or cancel.")
                    item_container = st.container()
                else:
                    item_container = st.expander(label)

                with item_container:
                    if is_editing:
                        client_types = [
                            "Law Firm",
                            "Corporate Security",
                            "Financial Institution",
                            "Private Client",
                            "Government",
                        ]
                        current_type = client.get("client_type", "Law Firm")
                        type_index = client_types.index(current_type) if current_type in client_types else 0

                        with st.form(f"edit_client_{client['id']}"):
                            e_name = st.text_input("Client Name", value=client.get("name", ""))
                            e_type = st.selectbox("Client Type", client_types, index=type_index)
                            e_email = st.text_input("Contact Email", value=client.get("contact_email", "") or "")
                            e_desc = st.text_area("Description / Notes", value=client.get("description", "") or "")

                            if st.form_submit_button("Save Changes"):
                                db.update_client(client["id"], e_name, e_type, e_email, e_desc)
                                st.session_state.edit_client_id = None
                                st.success("Client updated.")
                                st.rerun()

                        if st.button("Cancel Edit", key=f"cancel_client_{client['id']}"):
                            st.session_state.edit_client_id = None
                            st.rerun()
                    else:
                        st.caption(f"Type: {client.get('client_type', 'Unspecified')}")
                        if client.get("contact_email"):
                            st.write(f"**Contact Email:** {client['contact_email']}")
                        if client.get("description"):
                            st.write(f"**Description / Notes:** {client['description']}")

                        col1, col2, col3 = st.columns(3)
                        if col1.button("Edit Client", key=f"edit_client_btn_{client['id']}", use_container_width=True):
                            st.session_state.edit_client_id = client["id"]
                            st.rerun()
                        if col2.button("Set Active", key=f"active_client_{client['id']}", use_container_width=True):
                            st.session_state.active_client_id = client["id"]
                            st.session_state.nav = "Manage Cases"
                            st.rerun()
                        if col3.button("Delete Client", key=f"delete_client_{client['id']}", use_container_width=True):
                            db.delete_client(client["id"])
                            if st.session_state.get("edit_client_id") == client["id"]:
                                st.session_state.edit_client_id = None
                            st.success("Client deleted.")
                            st.rerun()

        if edit_client_id is None:
            st.divider()
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

    render_manage_clients()
