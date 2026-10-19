"""Operation portfolio for manager and investigator workflows."""

import streamlit as st

from database import operations as db
from utils.auth import get_current_user, require_page_auth, user_has_role


OPERATION_STATUSES = ("open", "on_hold", "closed")
STATUS_DOTS = {
    "open": "🟢",
    "on_hold": "🟠",
    "closed": "🔵",
}

def _render_operation(
    operation: dict,
    *,
    manager: bool,
    investigator_task_count: int | None = None,
) -> None:
    task_count = operation["task_count"] if manager else investigator_task_count
    task_label = "Task" if task_count == 1 else "Tasks"
    title = (
        f"{operation['operation_name']} — {operation['client_name']} · "
        f"{STATUS_DOTS[operation['operation_status']]} "
        f"{operation['operation_status'].replace('_', ' ').title()} · "
        f"{task_count} {task_label}"
    )
    with st.expander(title):
        if operation.get("client_contact_email"):
            st.caption(
                f"{operation['client_name']} · {operation['client_contact_email']}"
            )
        else:
            st.caption(operation["client_name"])
        if operation.get("description"):
            st.write(operation["description"])

        if manager:
            if st.button("Manage", key=f"manage_operation_{operation['id']}", use_container_width=True):
                st.session_state.active_operation_id = operation["id"]
                st.session_state.show_operation_workspace = True
                st.rerun()


def _create_operation_form(clients: list[dict], user: dict) -> None:
    st.divider()
    st.subheader("Create Operation")
    choices = {client["name"]: client["id"] for client in clients}
    with st.form("create_operation", clear_on_submit=True):
        client_name = st.selectbox("Client", list(choices))
        name = st.text_input("Operation name")
        description = st.text_area("Operation context")
        if st.form_submit_button("Create operation"):
            try:
                db.add_operation(
                    choices[client_name],
                    name,
                    description=description,
                    actor_user_id=user["id"],
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.rerun()


def show_manage_operations() -> None:
    require_page_auth()
    user = get_current_user()
    if not user:
        return
    if user_has_role(user, "administrator"):
        st.error("Administrators do not have access to operational work.")
        return

    manager = user_has_role(user, "manager")
    st.title("Operations")
    if not manager:
        st.caption("Only Operations containing Tasks assigned to you are shown.")

    operations = db.get_operations(st.session_state.get("active_client_id"))
    investigator_task_counts: dict[int, int] = {}
    if not manager:
        for task in db.get_tasks_with_workflow(user["username"], user["role"]):
            operation_id = task["operation_id"]
            investigator_task_counts[operation_id] = investigator_task_counts.get(operation_id, 0) + 1
        operations = [
            operation for operation in operations if operation["id"] in investigator_task_counts
        ]

    if not operations:
        st.info("No operations are available.")
    for operation in operations:
        _render_operation(
            operation,
            manager=manager,
            investigator_task_count=investigator_task_counts.get(operation["id"]),
        )

    if manager:
        _create_operation_form(db.get_clients(), user)
