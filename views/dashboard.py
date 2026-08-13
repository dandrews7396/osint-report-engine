import streamlit as st
from database import operations as db

try:
    fragment = st.fragment
except AttributeError:
    def fragment(func):
        return func


def show_dashboard():
    @fragment
    def render_dashboard():
        st.title("OSINT Intelligence Engine")
        st.write("Use the dashboard as a lightweight overview of your active workspace.")

        clients = db.get_clients()
        cases = db.get_cases()
        risks = db.get_risk_library()

        col1, col2, col3 = st.columns(3)
        col1.metric("Active Clients", len(clients))
        col2.metric("Total Cases", len(cases))
        col3.metric("Risk Templates", len(risks))

        st.divider()
        st.subheader("Quick Navigation")
        nav1, nav2 = st.columns(2)
        if nav1.button("Manage Clients", use_container_width=True):
            st.switch_page("pages/manage_clients.py")
        if nav2.button("Settings", use_container_width=True):
            st.switch_page("pages/settings.py")

    render_dashboard()
