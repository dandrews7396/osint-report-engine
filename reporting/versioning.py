"""Pure helpers for versioned, integrity-checked report artefacts."""

from __future__ import annotations

import hashlib
import hmac
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping


class ReportIntegrityError(RuntimeError):
    """Raised when a generated report does not match its recorded digest."""


def build_versioned_output_path(
    output_directory: str | Path,
    case_reference: str,
    version: int,
    *,
    status: str,
    extension: str = ".pdf",
) -> Path:
    """Return a deterministic artefact path without creating or overwriting it."""
    if version < 1:
        raise ValueError("version must be at least 1")
    if not case_reference:
        raise ValueError("case_reference is required for versioned output")
    if status not in {"draft", "final"}:
        raise ValueError("status must be either 'draft' or 'final'")
    if not extension.startswith("."):
        extension = f".{extension}"

    safe_reference = re.sub(r"[^A-Za-z0-9._-]+", "_", case_reference).strip("._")
    if not safe_reference:
        raise ValueError("case_reference must contain a filename-safe character")
    return Path(output_directory) / f"{safe_reference}_v{version:04d}_{status}{extension}"


def sha256_file(file_path: str | Path) -> str:
    """Return the SHA-256 digest for a file, propagating all read errors."""
    digest = hashlib.sha256()
    with Path(file_path).open("rb") as report_file:
        for chunk in iter(lambda: report_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_file_sha256(file_path: str | Path, expected_digest: str) -> bool:
    """Verify a report digest or raise ReportIntegrityError on a mismatch."""
    actual_digest = sha256_file(file_path)
    if not hmac.compare_digest(actual_digest.lower(), expected_digest.lower()):
        raise ReportIntegrityError(
            f"SHA-256 mismatch for {file_path}: expected {expected_digest}, got {actual_digest}"
        )
    return True


def approval_end_date(approval_data: Mapping[str, Any]) -> str:
    """Extract the approval timestamp used as a final report's end date."""
    for field in (
        "approved_at",
        "approved_date",
        "approved_on",
        "approval_date",
        "approval_timestamp",
        "finalized_at",
        "end_date",
    ):
        value = approval_data.get(field)
        if value:
            if isinstance(value, (date, datetime)):
                return value.isoformat()
            return str(value)
    raise ValueError("approval_data must include an approval date")


def approval_signoff(approval_data: Mapping[str, Any]) -> dict[str, str]:
    """Normalize explicitly supplied approval data for the final signoff block."""
    approved_by = (
        approval_data.get("approved_by")
        or approval_data.get("approver_name")
        or approval_data.get("signed_by")
        or approval_data.get("name")
    )
    if not approved_by:
        raise ValueError("approval_data must include approved_by")
    return {
        "approved_by": str(approved_by),
        "approved_at": approval_end_date(approval_data),
        "title": str(approval_data.get("approver_title") or approval_data.get("title") or ""),
        "signature": str(approval_data.get("signature") or ""),
    }
