from pathlib import Path

import streamlit as st

_PAGE_CONFIG = {
    "page_title": "OSINT Intelligence Engine",
    "layout": "wide",
}
_OPTIONAL_LOGO_PATH = Path("assets/logo.png")
if _OPTIONAL_LOGO_PATH.exists():
    _PAGE_CONFIG["page_icon"] = str(_OPTIONAL_LOGO_PATH)

st.set_page_config(**_PAGE_CONFIG)

hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden;}
header {visibility: hidden;}
footer {visibility: hidden;}
[data-testid="stSelectbox"] input {
    caret-color: transparent;
    cursor: pointer;
}
[data-testid="InputInstructions"] {
    display: none;
}
[data-testid="stTextArea"] textarea {
    height: 120px !important;
    resize: none;
    overflow-y: auto;
}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

from database.db import init_db, get_user_count
from utils.auth import get_cookie_controller, hydrate_authenticated_session
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


ROLE_NAVIGATION = {
    "administrator": [
        "Administrator Dashboard", "Users & Accounts", "Audit Log", "Application Settings", "Templates", "Profile",
    ],
    "manager": [
        "Manager Dashboard", "Manage Clients", "Manage Cases", "Case Evidence", "Risk Library",
        "Report Review", "Management Summary", "Profile",
    ],
    "investigator": [
        "Investigator Dashboard", "Clients", "My Cases", "Manage Subjects", "Case Findings",
        "Risk Library", "Generate Report", "Profile",
    ],
}


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
            if not hydrate_authenticated_session(verified_username):
                get_cookie_controller().remove('kairos_auth_token')
        else:
            get_cookie_controller().remove('kairos_auth_token')
        
    if not st.session_state.get('logged_in'):
        if get_user_count() == 0:
            show_setup()
        else:
            show_login()
        return

    role = st.session_state.get("role", "investigator")
    menu = ROLE_NAVIGATION.get(role, ROLE_NAVIGATION["investigator"])
    if "nav" not in st.session_state or st.session_state.nav not in menu:
        st.session_state.nav = menu[0]

    if st.sidebar.button("Logout"):
        logout_page()
        return

    choice = st.sidebar.radio("Navigation", menu, index=menu.index(st.session_state.nav))
    if choice != st.session_state.nav:
        st.session_state.nav = choice
        st.rerun()

    if st.session_state.nav in {"Administrator Dashboard", "Manager Dashboard", "Investigator Dashboard"}:
        from views.dashboard import show_dashboard
        show_dashboard()
    elif st.session_state.nav in {"Manage Clients", "Clients"}:
        from views.manage_clients import show_manage_clients
        show_manage_clients()
    elif st.session_state.nav in {"Manage Cases", "My Cases"}:
        from views.manage_cases import show_manage_cases
        show_manage_cases()
    elif st.session_state.nav == "Manage Subjects":
        from views.manage_subjects import show_manage_subjects
        show_manage_subjects()
    elif st.session_state.nav == "Case Evidence":
        from views.case_evidence import render_manager_evidence_browser
        render_manager_evidence_browser()
    elif st.session_state.nav == "Case Findings":
        from views.manage_findings import show_manage_findings
        show_manage_findings()
    elif st.session_state.nav == "Risk Library":
        from views.risk_library import show_risk_library
        show_risk_library()
    elif st.session_state.nav == "Generate Report":
        from views.generate_report import show_generate_report
        show_generate_report()
    elif st.session_state.nav == "Report Review":
        from views.review_reports import show_review_reports
        show_review_reports()
    elif st.session_state.nav == "Management Summary":
        from views.management_summary import show_management_summary
        show_management_summary()
    elif st.session_state.nav == "Application Settings":
        from views.settings import show_settings
        show_settings()
    elif st.session_state.nav == "Templates":
        from views.templates import show_templates
        show_templates()
    elif st.session_state.nav == "Profile":
        from views.profile import show_profile
        show_profile()
    elif st.session_state.nav == "Users & Accounts":
        from views.admin import show_admin_users
        show_admin_users()
    elif st.session_state.nav == "Audit Log":
        from views.audit_log import show_audit_log
        show_audit_log()

if __name__ == "__main__":
    main()