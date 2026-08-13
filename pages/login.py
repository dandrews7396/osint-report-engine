from pathlib import Path

import streamlit as st
from database.db import init_db
from views.login import show_login

init_db()

if st.session_state.get('logged_in'):
    st.switch_page(Path("pages/dashboard.py"))

show_login()
