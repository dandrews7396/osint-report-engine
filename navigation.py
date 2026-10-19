import streamlit as st

from utils.auth import get_current_user


def get_navigation_pages(role: str | None = None):
    from views.dashboard import show_dashboard
    from views.manage_clients import show_manage_clients
    from views.manage_operations import show_manage_operations
    from views.manage_tasks import show_manage_tasks
    from views.manage_findings import show_manage_findings
    from views.manage_subjects import show_manage_subjects
    from views.task_evidence import render_manager_evidence_browser
    from views.risk_library import show_risk_library
    from views.generate_report import show_generate_report
    from views.review_reports import show_review_reports
    from views.profile import show_profile
    from views.admin import show_admin_users
    from views.audit_log import show_audit_log
    from views.settings import show_settings
    from views.templates import show_templates

    common_pages = {
        "Dashboard": st.Page(show_dashboard, title="Dashboard", default=True),
        "Manage Clients": st.Page(show_manage_clients, title="Manage Clients"),
        "Operations": st.Page(show_manage_operations, title="Operations"),
        "Manage Tasks": st.Page(show_manage_tasks, title="Manage Tasks"),
        "Manage Subjects": st.Page(show_manage_subjects, title="Manage Subjects"),
        "Task Findings": st.Page(show_manage_findings, title="Task Findings"),
        "Risk Library": st.Page(show_risk_library, title="Risk Library"),
        "Generate Report": st.Page(show_generate_report, title="Generate Report"),
        "Report Review": st.Page(show_review_reports, title="Report Review"),
        "Profile": st.Page(show_profile, title="Profile"),
    }
    role = role or (get_current_user() or {}).get("role", "investigator")
    if role == "administrator":
        return [
            common_pages["Dashboard"],
            st.Page(show_admin_users, title="Users & Accounts"),
            st.Page(show_audit_log, title="Audit Log"),
            st.Page(show_settings, title="Application Settings"),
            st.Page(show_templates, title="Templates"),
            common_pages["Profile"],
        ]
    if role == "manager":
        return [
            common_pages["Dashboard"], common_pages["Manage Clients"], common_pages["Operations"], common_pages["Manage Tasks"],
            st.Page(render_manager_evidence_browser, title="Task Evidence"), common_pages["Risk Library"],
            common_pages["Report Review"], common_pages["Profile"],
        ]
    return [
        common_pages["Dashboard"],
        st.Page(show_manage_tasks, title="Tasks"),
        common_pages["Manage Subjects"], common_pages["Task Findings"], common_pages["Risk Library"],
        common_pages["Generate Report"], common_pages["Profile"],
    ]


def switch_to(page_title: str) -> None:
    pages = {page.title: page for page in get_navigation_pages()}
    st.switch_page(pages[page_title])
