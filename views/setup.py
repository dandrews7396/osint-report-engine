import streamlit as st
from database.db import add_user, normalize_username, validate_username
from utils.auth import ph

_HIDE_SIDEBAR_STYLE = """
<style>
[data-testid="stSidebar"] { display: none !important; }
[data-testid="stSidebarNav"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
#MainMenu { visibility: hidden; }
header { visibility: hidden; }
footer { visibility: hidden; }
</style>
"""

def show_setup():
    st.markdown(_HIDE_SIDEBAR_STYLE, unsafe_allow_html=True)
    st.title("Osint First-Time Setup")
    st.write("Welcome to Osint Report Engine. Since there are no users in the system, you must create the initial Administrator account.")

    username = st.text_input(
        "Administrator Username",
        key="setup_admin_username",
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

    password = st.text_input("Passphrase", type="password", key="setup_admin_password")
    password_confirm = st.text_input("Confirm Passphrase", type="password", key="setup_admin_password_confirm")

    if st.button("Create Administrator", key="setup_create_admin"):
        if password != password_confirm:
            st.error("Passphrases do not match.")
        elif username_error:
            st.error(username_error)
        elif len(password) < 12:
            st.error("Passphrase must be at least 12 characters.")
        else:
            try:
                hash_pw = ph.hash(password)
                add_user(normalized_username, hash_pw, is_admin=True)
                st.success(f"Administrator account '{normalized_username}' created. Please log in.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))
            except PermissionError as e:
                st.error(str(e))
            except RuntimeError as e:
                st.error("Could not create the administrator account.")
                st.caption(str(e))
