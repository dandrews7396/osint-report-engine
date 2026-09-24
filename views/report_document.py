"""Shared, verified report document controls."""

import base64
from pathlib import Path

import streamlit as st

from reporting.versioning import ReportIntegrityError, verify_file_sha256


def read_verified_report(version: dict) -> tuple[bytes | None, str | None]:
    """Read a report only after its recorded SHA-256 digest has been verified."""
    try:
        storage_reference = version["storage_reference"]
        content_hash = version["content_hash"]
        if not storage_reference or not content_hash:
            return None, "Document validation failed."
        path = Path(storage_reference)
        verify_file_sha256(path, content_hash)
        return path.read_bytes(), None
    except (KeyError, OSError, ReportIntegrityError, TypeError):
        return None, "Document validation failed."


def render_report_document_actions(version: dict, *, key_prefix: str) -> bool:
    """Render verified View and Download controls and return the validation result."""
    pdf_data, error = read_verified_report(version)
    if error:
        st.error(error)
        return False

    view_button_key = f"{key_prefix}_view"
    view_state_key = f"{key_prefix}_view_open"
    controls = st.columns((1, 1, 6), vertical_alignment="center")
    if controls[0].button("View", key=view_button_key):
        st.session_state[view_state_key] = not st.session_state.get(view_state_key, False)
    controls[1].download_button(
        "Download",
        data=pdf_data,
        file_name=Path(version["storage_reference"]).name,
        mime="application/pdf",
        key=f"{key_prefix}_download",
    )
    if st.session_state.get(view_state_key, False):
        encoded_pdf = base64.b64encode(pdf_data).decode("ascii")
        with st.expander("Preview Report", expanded=True):
            st.markdown(
                f'<iframe src="data:application/pdf;base64,{encoded_pdf}" '
                'width="100%" height="800px" type="application/pdf"></iframe>',
                unsafe_allow_html=True,
            )
    return True
