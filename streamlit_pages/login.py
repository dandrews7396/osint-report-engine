from pathlib import Path

import streamlit as st

_PAGE_CONFIG = {
    "page_title": "OSINT Intelligence Engine",
    "layout": "centered",
    "initial_sidebar_state": "collapsed",
}
_OPTIONAL_LOGO_PATH = Path("assets/logo.png")
if _OPTIONAL_LOGO_PATH.exists():
    _PAGE_CONFIG["page_icon"] = str(_OPTIONAL_LOGO_PATH)

st.set_page_config(**_PAGE_CONFIG)
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="stSidebarNav"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }
    #MainMenu { visibility: hidden; }
    header { visibility: hidden; }
    footer { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

from database.db import init_db
from views.login import show_login

init_db()

if st.session_state.get('logged_in'):
    st.switch_page(Path("streamlit_pages/dashboard.py"))

show_login()
