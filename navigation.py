from functools import lru_cache

import streamlit as st


@lru_cache
def get_navigation_pages():
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

    return [
        st.Page(show_dashboard, title="Dashboard", default=True),
        st.Page(show_manage_clients, title="Manage Clients"),
        st.Page(show_manage_cases, title="Manage Cases"),
        st.Page(show_manage_findings, title="Case Findings"),
        st.Page(show_risk_library, title="Risk Library"),
        st.Page(show_generate_report, title="Generate Report"),
        st.Page(show_templates, title="Templates"),
        st.Page(show_settings, title="Settings"),
        st.Page(show_profile, title="Profile"),
        st.Page(show_admin_users, title="Admin: Users"),
    ]


def switch_to(page_title: str) -> None:
    pages = {page.title: page for page in get_navigation_pages()}
    st.switch_page(pages[page_title])
