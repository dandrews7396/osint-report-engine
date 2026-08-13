import streamlit as st
from pathlib import Path

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
    st.switch_page(Path("pages/login.py"))

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

    pages = [
        st.Page(Path("pages/dashboard.py"), title="Dashboard", icon="📊", default=True),
        st.Page(Path("pages/manage_clients.py"), title="Manage Clients", icon="👥"),
        st.Page(Path("pages/manage_cases.py"), title="Manage Cases", icon="📁"),
        st.Page(Path("pages/manage_findings.py"), title="Case Findings", icon="🧠"),
        st.Page(Path("pages/risk_library.py"), title="Risk Library", icon="📚"),
        st.Page(Path("pages/generate_report.py"), title="Generate Report", icon="📝"),
        st.Page(Path("pages/templates.py"), title="Templates", icon="🧩"),
        st.Page(Path("pages/settings.py"), title="Settings", icon="⚙️"),
        st.Page(Path("pages/profile.py"), title="Profile", icon="🔐"),
        st.Page(Path("pages/admin.py"), title="Admin: Users", icon="🛡️"),
        st.Page(logout_page, title="Logout", icon="🚪"),
    ]
    nav = st.navigation(pages, position="sidebar")
    nav.run()

if __name__ == "__main__":
    main()