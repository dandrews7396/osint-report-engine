from pathlib import Path

import streamlit as st

from views.login import show_login

if st.session_state.get('logged_in'):
    st.switch_page(Path("pages/dashboard.py"))

show_login()
