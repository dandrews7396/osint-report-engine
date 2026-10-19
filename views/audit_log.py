import json

import streamlit as st

from database.db import get_connection
from utils.auth import require_role_page_auth


def _get_audit_events(limit: int = 250) -> list[dict]:
    """Read immutable audit events for the administrator-facing audit view."""
    with get_connection() as connection:
        rows = connection.execute(
            """SELECT a.occurred_at, COALESCE(u.username, 'System') AS actor,
                      a.event_type, a.entity_type, a.entity_id, a.details_json
               FROM audit_events AS a
               LEFT JOIN users AS u ON u.id = a.actor_user_id
               ORDER BY a.id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    events = []
    for row in rows:
        event = dict(row)
        event["details"] = json.loads(event.pop("details_json"))
        events.append(event)
    return events


def show_audit_log():
    require_role_page_auth("administrator")
    st.title("Audit Log")
    st.caption("Immutable account and application activity, newest first.")
    events = _get_audit_events()
    if not events:
        st.info("No audit events have been recorded.")
        return
    st.dataframe(events, use_container_width=True, hide_index=True)
