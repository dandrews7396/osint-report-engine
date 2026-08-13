import streamlit as st

st.set_page_config(page_title="OSINT Intelligence Engine", page_icon="assets/DIILogo.png", layout="centered", initial_sidebar_state="collapsed")
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
