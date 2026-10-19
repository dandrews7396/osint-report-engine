"""Selected-operation workspace for manager updates."""

import streamlit as st

from database import operations as db
from utils.auth import get_current_user, require_page_auth, user_has_role

OPERATION_STATUSES = ("open", "on_hold", "closed")
OPERATION_STATUS_LABELS = {
    "open": "Open",
    "on_hold": "On Hold",
    "closed": "Closed",
}


def show_operation_workspace() -> None:
    require_page_auth()
    user = get_current_user()
    if not user:
        return
    if not user_has_role(user, "manager"):
        st.error("Only managers can update operations.")
        return

    operation_id = st.session_state.get("active_operation_id")
    operation = next(
        (item for item in db.get_operations() if item["id"] == operation_id),
        None,
    )
    if not operation:
        st.error("The selected operation is no longer available.")
        return

    heading, back = st.columns((6, 1), vertical_alignment="center")
    heading.title(operation["operation_name"])
    if back.button("Back", use_container_width=True):
        st.session_state.pop("show_operation_workspace", None)
        st.session_state.pop("active_operation_id", None)
        st.rerun()

    contact = operation.get("client_contact_email") or "No contact email"
    st.caption(f"{operation['client_name']} · {contact}")

    with st.form(f"operation_workspace_{operation['id']}"):
        name = st.text_input("Operation name", value=operation["operation_name"])
        status = st.selectbox(
            "Operation status",
            OPERATION_STATUSES,
            index=OPERATION_STATUSES.index(operation["operation_status"]),
            format_func=OPERATION_STATUS_LABELS.__getitem__,
        )
        description = st.text_area(
            "Operation context",
            value=operation.get("description") or "",
        )
        if st.form_submit_button("Save Operation"):
            try:
                db.update_operation(
                    operation["id"],
                    operation_name=name,
                    operation_status=status,
                    description=description,
                    actor_user_id=user["id"],
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.rerun()
