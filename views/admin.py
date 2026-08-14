import streamlit as st
from database.db import add_user, delete_user, get_user, get_users, normalize_username, update_user_password, validate_username
from argon2.exceptions import VerifyMismatchError
from utils.auth import ph, require_admin_page_auth

def show_admin_users():
    @st.fragment
    def render_admin_page():
        admin_user = require_admin_page_auth()
        clear_mode = st.session_state.pop("admin_clear_fields_mode", None)
        if clear_mode == "create":
            st.session_state["admin_new_username"] = ""
            st.session_state["admin_new_user_passphrase"] = ""
            st.session_state["admin_current_password"] = ""
        elif clear_mode == "update":
            st.session_state["admin_reset_user_passphrase"] = ""
            st.session_state["admin_reset_user_passphrase_confirm"] = ""
            st.session_state["admin_current_password"] = ""

        st.title("User Management")
        st.write("Create additional non-administrator accounts or update an existing user's password.")
        if success_message := st.session_state.pop("admin_create_user_success", None):
            st.success(success_message)

        manageable_users = [user for user in get_users() if user["username"] != admin_user["username"]]
        action_options = ["Create New User"]
        if manageable_users:
            action_options.append("Update Existing User")

        action = st.selectbox("Action", action_options, key="admin_user_action")
        admin_pw = st.text_input("Your Current Password (Admin)", type="password", key="admin_current_password")
        st.divider()

        if action == "Create New User":
            username = st.text_input(
                "New Username",
                key="admin_new_username",
                help="3-12 letters only. Usernames are saved in lowercase.",
            )
            normalized_username = normalize_username(username)
            username_error = validate_username(normalized_username) if username else None
            st.caption("Usernames must be 3-12 letters only and are saved in lowercase.")
            if username:
                if username_error:
                    st.warning(username_error)
                else:
                    st.success(f"Username will be saved as '{normalized_username}'.")

            password = st.text_input("New User Passphrase", type="password", key="admin_new_user_passphrase")

            if st.button("Create User", key="admin_create_user_submit"):
                user = get_user(admin_user['username'])
                try:
                    ph.verify(user['password_hash'], admin_pw)
                    if username_error:
                        st.error(username_error)
                    elif len(password) < 12:
                        st.error("Passphrase must be at least 12 characters.")
                    else:
                        try:
                            hash_pw = ph.hash(password)
                            add_user(normalized_username, hash_pw, created_by_username=admin_user['username'])
                            st.session_state["admin_create_user_success"] = f"User {normalized_username} created!"
                            st.session_state["admin_clear_fields_mode"] = "create"
                            st.rerun()
                        except PermissionError as e:
                            st.error(str(e))
                        except ValueError as e:
                            st.error(str(e))
                except VerifyMismatchError:
                    st.error("Incorrect admin password.")
        else:
            user_options = {user["username"]: user["username"] for user in manageable_users}
            target_username = st.selectbox("User to Update", list(user_options.keys()), key="admin_target_username")
            new_password = st.text_input("New User Passphrase", type="password", key="admin_reset_user_passphrase")
            confirm_password = st.text_input(
                "Confirm New User Passphrase",
                type="password",
                key="admin_reset_user_passphrase_confirm",
            )
            action_col, delete_col = st.columns(2)

            with action_col:
                if st.button("Update Password", key="admin_update_user_password_submit", use_container_width=True):
                    user = get_user(admin_user['username'])
                    try:
                        ph.verify(user['password_hash'], admin_pw)
                        if len(new_password) < 12:
                            st.error("Passphrase must be at least 12 characters.")
                        elif new_password != confirm_password:
                            st.error("Passphrases do not match.")
                        else:
                            new_hash = ph.hash(new_password)
                            update_user_password(target_username, new_hash)
                            st.session_state["admin_create_user_success"] = f"Password reset for {target_username}."
                            st.session_state["admin_clear_fields_mode"] = "update"
                            st.rerun()
                    except VerifyMismatchError:
                        st.error("Incorrect admin password.")

            with delete_col:
                if st.button("Delete User", key="admin_delete_user_submit", use_container_width=True):
                    user = get_user(admin_user['username'])
                    try:
                        ph.verify(user['password_hash'], admin_pw)
                        delete_user(target_username)
                        st.session_state["admin_create_user_success"] = f"User {target_username} deleted."
                        st.session_state["admin_clear_fields_mode"] = "update"
                        st.rerun()
                    except VerifyMismatchError:
                        st.error("Incorrect admin password.")
                    except (PermissionError, RuntimeError, ValueError) as e:
                        st.error(str(e))

    render_admin_page()
