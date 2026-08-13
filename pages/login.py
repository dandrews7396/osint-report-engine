from pathlib import Path

import streamlit as st

st.set_page_config(page_title="OSINT Intelligence Engine", page_icon="assets/DIILogo.png", layout="centered", initial_sidebar_state="collapsed")
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] { display: none; }
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

from database.db import init_db
from views.login import show_login

init_db()

if st.session_state.get('logged_in'):
    st.switch_page(Path("pages/dashboard.py"))

show_login()
