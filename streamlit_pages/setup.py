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
from views.setup import show_setup

init_db()

show_setup()
