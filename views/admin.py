import streamlit as st
from database.db import add_user, get_user
from argon2.exceptions import VerifyMismatchError
from utils.auth import ph, require_admin_page_auth

def show_admin_users():
    @st.fragment
    def render_admin_page():
        admin_user = require_admin_page_auth()
        st.title("User Management")
        st.write("Create additional non-administrator accounts for your team.")

        with st.form("add_user_form", clear_on_submit=True):
            admin_pw = st.text_input("Your Current Password (Admin)", type="password")
            st.divider()
            username = st.text_input("New Username")
            password = st.text_input("New User Passphrase", type="password")

            if st.form_submit_button("Create User"):
                user = get_user(admin_user['username'])
                try:
                    ph.verify(user['password_hash'], admin_pw)
                    if len(password) < 12:
                        st.error("Passphrase must be at least 12 characters.")
                    else:
                        try:
                            hash_pw = ph.hash(password)
                            add_user(username, hash_pw, created_by_username=admin_user['username'])
                            st.success(f"User {username} created!")
                        except PermissionError as e:
                            st.error(str(e))
                        except ValueError as e:
                            st.error(str(e))
                except VerifyMismatchError:
                    st.error("Incorrect admin password.")

    render_admin_page()
