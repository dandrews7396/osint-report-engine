import streamlit as st

st.set_page_config(page_title="OSINT Intelligence Engine", page_icon="assets/DIILogo.png", layout="wide")

hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden;}
header {visibility: hidden;}
footer {visibility: hidden;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

from database.db import init_db, get_user_count
from utils.auth import get_cookie_controller
from views.setup import show_setup
from views.login import show_login

def ensure_db_initialized():
    if not st.session_state.get('_db_initialized'):
        init_db()
        st.session_state._db_initialized = True


def logout_page():
    get_cookie_controller().remove('kairos_auth_token')
    st.session_state.clear()
    st.session_state.logged_out = True
    st.rerun()

def main():
    ensure_db_initialized()

    if st.session_state.get('trigger_logout'):
        get_cookie_controller().remove('kairos_auth_token')
        st.session_state.clear()
        st.session_state.logged_out = True
        st.info("Securely logging you out...")
        st.markdown('<meta http-equiv="refresh" content="1">', unsafe_allow_html=True)
        return

    auth_token = get_cookie_controller().get('kairos_auth_token')
    if auth_token and not st.session_state.get('logged_in') and not st.session_state.get('logged_out'):
        from utils.auth import verify_token
        verified_username = verify_token(auth_token)
        if verified_username:
            st.session_state.logged_in = True
            st.session_state.username = verified_username
        else:
            get_cookie_controller().remove('kairos_auth_token')
        
    if not st.session_state.get('logged_in'):
        if get_user_count() == 0:
            show_setup()
        else:
            show_login()
        return

    menu = ["Dashboard", "Manage Clients", "Manage Cases", "Manage Subjects", "Case Findings", "Risk Library", "Generate Report", "Templates", "Settings", "Profile", "Admin: Users", "Logout"]
    if "nav" not in st.session_state or st.session_state.nav not in menu:
        st.session_state.nav = "Dashboard"

    if st.sidebar.button("Logout"):
        logout_page()
        return

    choice = st.sidebar.radio("Navigation", menu[:-1], index=menu[:-1].index(st.session_state.nav))
    if choice != st.session_state.nav:
        st.session_state.nav = choice
        st.rerun()

    if st.session_state.nav == "Dashboard":
        from views.dashboard import show_dashboard
        show_dashboard()
    elif st.session_state.nav == "Manage Clients":
        from views.manage_clients import show_manage_clients
        show_manage_clients()
    elif st.session_state.nav == "Manage Cases":
        from views.manage_cases import show_manage_cases
        show_manage_cases()
    elif st.session_state.nav == "Manage Subjects":
        from views.manage_subjects import show_manage_subjects
        show_manage_subjects()
    elif st.session_state.nav == "Case Findings":
        from views.manage_findings import show_manage_findings
        show_manage_findings()
    elif st.session_state.nav == "Risk Library":
        from views.risk_library import show_risk_library
        show_risk_library()
    elif st.session_state.nav == "Generate Report":
        from views.generate_report import show_generate_report
        show_generate_report()
    elif st.session_state.nav == "Templates":
        from views.templates import show_templates
        show_templates()
    elif st.session_state.nav == "Settings":
        from views.settings import show_settings
        show_settings()
    elif st.session_state.nav == "Profile":
        from views.profile import show_profile
        show_profile()
    elif st.session_state.nav == "Admin: Users":
        from views.admin import show_admin_users
        show_admin_users()

if __name__ == "__main__":
    main()