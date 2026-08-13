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
from utils.helpers import get_image_base64

# Updated OSINT View Imports
from views.dashboard import show_dashboard
from views.manage_clients import show_manage_clients
from views.manage_cases import show_manage_cases
from views.manage_findings import show_manage_findings
from views.risk_library import show_risk_library
from views.generate_report import show_generate_report
from views.templates import show_templates
from views.settings import show_settings
from views.profile import show_profile
from views.admin import show_admin_users
from views.setup import show_setup
from views.login import show_login

def ensure_db_initialized():
    if not st.session_state.get('_db_initialized'):
        init_db()
        st.session_state._db_initialized = True

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

    logo_b64 = get_image_base64("assets/DIILogo.png")
    st.sidebar.markdown(f'<a href="https://osint-sec.com" target="_blank"><img src="data:image/png;base64,{logo_b64}" alt="DII" width="75%" style="margin-bottom: 20px;"></a>', unsafe_allow_html=True)
    st.sidebar.title("OSINT Intelligence Engine")
    
    # Navigation menu reflecting OSINT domain views
    menu = [
        "Dashboard", 
        "Manage Clients",
        "Manage Cases", 
        "Case Findings", 
        "Risk Library", 
        "Generate Report", 
        "Templates", 
        "Settings",
        "Profile", 
        "Admin: Users", 
        "Logout"
    ]
    
    # Fallback sanity check for active nav state
    if "nav" not in st.session_state or st.session_state.nav not in menu:
        st.session_state.nav = "Dashboard"
        
    choice = st.sidebar.radio("Navigation", menu, index=menu.index(st.session_state.nav))
    if choice != st.session_state.nav:
        if choice == "Logout":
            st.session_state.trigger_logout = True
            st.rerun()
        else:
            st.session_state.nav = choice
            st.rerun()

    # View Routing
    if st.session_state.nav == "Dashboard":
        show_dashboard()
    elif st.session_state.nav == "Manage Clients":
        show_manage_clients()
    elif st.session_state.nav == "Manage Cases":
        show_manage_cases()
    elif st.session_state.nav == "Case Findings":
        show_manage_findings()
    elif st.session_state.nav == "Risk Library":
        show_risk_library()
    elif st.session_state.nav == "Generate Report":
        show_generate_report()
    elif st.session_state.nav == "Templates":
        show_templates()
    elif st.session_state.nav == "Settings":
        show_settings()
    elif st.session_state.nav == "Profile":
        show_profile()
    elif st.session_state.nav == "Admin: Users":
        show_admin_users()

if __name__ == "__main__":
    main()