import streamlit as st

from database import operations as db
from utils.auth import get_current_user, require_page_auth, user_has_role


CLIENT_TYPES = ("Law Firm", "Corporate Security", "Financial Institution", "Private Client", "Government")


def show_manage_clients() -> None:
    require_page_auth()
    user = get_current_user()
    if not user:
        return
    if user_has_role(user, "administrator"):
        st.error("Administrators do not have access to operational client records.")
        return
    can_manage = user_has_role(user, "manager")
    st.title("Clients")
    if not can_manage:
        st.info("Client records are read-only for investigators.")

    clients = db.get_clients()
    edit_client_id = st.session_state.get("edit_client_id")
    if not clients:
        st.info("No clients found.")
    for client in sorted(
        clients,
        key=lambda client: client["id"] == edit_client_id,
    ):
        with st.expander(f"**{client['name']}**", expanded=edit_client_id == client["id"]):
            if can_manage and edit_client_id == client["id"]:
                type_index = CLIENT_TYPES.index(client.get("client_type")) if client.get("client_type") in CLIENT_TYPES else 0
                with st.form(f"edit_client_{client['id']}"):
                    name = st.text_input("Client name", value=client["name"])
                    client_type = st.selectbox("Client type", CLIENT_TYPES, index=type_index)
                    email = st.text_input("Contact email", value=client.get("contact_email") or "")
                    description = st.text_area("Description / notes", value=client.get("description") or "")
                    if st.form_submit_button("Save changes"):
                        db.update_client(client["id"], name, client_type, email, description)
                        st.session_state.pop("edit_client_id", None)
                        st.rerun()
                if st.button("Cancel", key=f"cancel_client_{client['id']}"):
                    st.session_state.pop("edit_client_id", None)
                    st.rerun()
            else:
                st.caption(f"{client.get('client_type', 'Unspecified')}")
                if client.get("contact_email"):
                    st.write(client["contact_email"])
                if client.get("description"):
                    st.write(client["description"])
                if can_manage:
                    edit, activate, delete = st.columns(3)
                    if edit.button("Edit", key=f"edit_client_{client['id']}", use_container_width=True):
                        st.session_state.edit_client_id = client["id"]
                        st.rerun()
                    if activate.button("View cases", key=f"client_cases_{client['id']}", use_container_width=True):
                        st.session_state.active_client_id = client["id"]
                        st.session_state.nav = "Manage Cases"
                        st.rerun()
                    if delete.button("Delete", key=f"delete_client_{client['id']}", use_container_width=True):
                        db.delete_client(client["id"])
                        st.rerun()

    if st.session_state.get("edit_client_id") is not None:
        return

    if can_manage:
        st.divider()
        st.subheader("Add Client")
        with st.form("add_client", clear_on_submit=True):
            name = st.text_input("Client name")
            client_type = st.selectbox("Client type", CLIENT_TYPES)
            email = st.text_input("Contact email")
            description = st.text_area("Description / notes")
            if st.form_submit_button("Add client"):
                if not name.strip():
                    st.error("Client name is required.")
                else:
                    db.add_client(name.strip(), client_type, email, description)
                    st.rerun()
