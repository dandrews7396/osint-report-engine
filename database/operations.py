import json
import sqlite3
import uuid
from datetime import date, datetime, timedelta
import streamlit as st
from database.db import get_connection, synchronize_investigator_directory
from database.subjects import (
    decode_subject_data,
    encode_subject_data,
    subject_display_name,
    subject_summary_lines,
)
from database.findings import (
    decode_finding_data,
    encode_finding_data,
    finding_summary_lines,
)
from utils.helpers import format_lifecycle_status

def _clear_read_caches():
    st.cache_data.clear()

# --- System ---
def cleanup_deleted_items():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM case_findings WHERE deleted_at IS NOT NULL AND datetime(deleted_at) <= datetime('now', '-30 days')")
        cursor.execute("DELETE FROM case_subjects WHERE deleted_at IS NOT NULL AND datetime(deleted_at) <= datetime('now', '-30 days')")
        cursor.execute("DELETE FROM cases WHERE deleted_at IS NOT NULL AND datetime(deleted_at) <= datetime('now', '-30 days')")
        cursor.execute("DELETE FROM clients WHERE deleted_at IS NOT NULL AND datetime(deleted_at) <= datetime('now', '-30 days')")
        conn.commit()
        _clear_read_caches()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] cleanup_deleted_items: {e}")
    finally:
        conn.close()

# --- Settings ---
@st.cache_data(show_spinner=False)
def get_settings() -> dict:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        return {row['key']: row['value'] for row in cursor.fetchall()}
    except sqlite3.Error as e:
        print(f"[DB ERROR] get_settings: {e}")
        return {}
    finally:
        conn.close()

def update_setting(key: str, value: str):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
        _clear_read_caches()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] update_setting: {e}")
    finally:
        conn.close()

# --- Clients ---
@st.cache_data(show_spinner=False)
def get_clients() -> list[dict]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM clients WHERE deleted_at IS NULL")
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"[DB ERROR] get_clients: {e}")
        return []
    finally:
        conn.close()

@st.cache_data(show_spinner=False)
def get_deleted_clients() -> list[dict]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM clients WHERE deleted_at IS NOT NULL")
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"[DB ERROR] get_deleted_clients: {e}")
        return []
    finally:
        conn.close()

def add_client(name: str, client_type: str = 'Law Firm', contact_email: str = '', description: str = ''):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO clients (name, client_type, contact_email, description) 
            VALUES (?, ?, ?, ?)
        """, (name, client_type, contact_email, description))
        conn.commit()
        _clear_read_caches()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] add_client: {e}")
    finally:
        conn.close()

def update_client(client_id: int, name: str, client_type: str = 'Law Firm', contact_email: str = '', description: str = ''):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE clients
            SET name = ?, client_type = ?, contact_email = ?, description = ?
            WHERE id = ? AND deleted_at IS NULL
        """, (name, client_type, contact_email, description, client_id))
        conn.commit()
        _clear_read_caches()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] update_client: {e}")
    finally:
        conn.close()

def delete_client(client_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE clients SET deleted_at = CURRENT_TIMESTAMP WHERE id = ?", (client_id,))
        cursor.execute("UPDATE cases SET deleted_at = CURRENT_TIMESTAMP WHERE client_id = ? AND deleted_at IS NULL", (client_id,))
        cursor.execute("UPDATE case_subjects SET deleted_at = CURRENT_TIMESTAMP WHERE case_id IN (SELECT id FROM cases WHERE client_id = ?) AND deleted_at IS NULL", (client_id,))
        cursor.execute("""
            UPDATE case_findings SET deleted_at = CURRENT_TIMESTAMP 
            WHERE case_id IN (SELECT id FROM cases WHERE client_id = ?) 
            AND deleted_at IS NULL
        """, (client_id,))
        conn.commit()
        _clear_read_caches()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] delete_client: {e}")
    finally:
        conn.close()

def restore_client(client_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE clients SET deleted_at = NULL WHERE id = ?", (client_id,))
        cursor.execute("UPDATE cases SET deleted_at = NULL WHERE client_id = ?", (client_id,))
        cursor.execute("UPDATE case_subjects SET deleted_at = NULL WHERE case_id IN (SELECT id FROM cases WHERE client_id = ?)", (client_id,))
        cursor.execute("UPDATE case_findings SET deleted_at = NULL WHERE case_id IN (SELECT id FROM cases WHERE client_id = ?)", (client_id,))
        conn.commit()
        _clear_read_caches()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] restore_client: {e}")
    finally:
        conn.close()

def hard_delete_client(client_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM case_findings WHERE case_id IN (SELECT id FROM cases WHERE client_id = ?)", (client_id,))
        cursor.execute("DELETE FROM case_subjects WHERE case_id IN (SELECT id FROM cases WHERE client_id = ?)", (client_id,))
        cursor.execute("DELETE FROM cases WHERE client_id = ?", (client_id,))
        cursor.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        conn.commit()
        _clear_read_caches()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] hard_delete_client: {e}")
    finally:
        conn.close()

# --- Cases (Formerly Projects) ---
@st.cache_data(show_spinner=False)
def get_cases() -> list[dict]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                c.id, c.case_ref, c.case_name, c.case_type, c.client_id, c.start_date, c.end_date, c.report_date,
                c.lead_investigator_id, i.name AS investigator_name,
                i.bio AS investigator_description, c.target_scope,
                c.legitimate_interest_assessment AS legitimate_interest, c.executive_assessment AS executive_summary,
                c.key_findings_summary AS key_findings_summary, c.covert_persona_reference AS covert_persona_reference,
                c.tools_and_sources_used AS tools_used, c.deleted_at, cl.name as client_name
            FROM cases c 
            JOIN clients cl ON c.client_id = cl.id
            LEFT JOIN investigators i ON i.user_id = c.lead_investigator_id
            WHERE c.deleted_at IS NULL AND cl.deleted_at IS NULL
        """)
        rows = [dict(row) for row in cursor.fetchall()]
        return rows
    except sqlite3.Error as e:
        print(f"[DB ERROR] get_cases: {e}")
        return []
    finally:
        conn.close()

@st.cache_data(show_spinner=False)
def get_deleted_cases() -> list[dict]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.*, cl.name as client_name 
            FROM cases c 
            JOIN clients cl ON c.client_id = cl.id
            WHERE c.deleted_at IS NOT NULL
        """)
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"[DB ERROR] get_deleted_cases: {e}")
        return []
    finally:
        conn.close()

def add_case(
    case_ref: str,
    case_name: str,
    client_id: int,
    case_type: str = 'Enhanced Due Diligence',
    start_date: str = '',
    end_date: str = '',
    report_date: str = '',
    target_scope: str = '',
    legitimate_interest_assessment: str = '',
    executive_assessment: str = '',
    key_findings_summary: str = '',
    covert_persona_reference: str = '',
    tools_and_sources_used: str = ''
) -> int:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO cases (
                case_ref, case_name, client_id, case_type, start_date, end_date, report_date,
                target_scope,
                legitimate_interest_assessment,
                executive_assessment, key_findings_summary, covert_persona_reference, tools_and_sources_used
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            case_ref, case_name, client_id, case_type, start_date, end_date, report_date,
            target_scope,
            legitimate_interest_assessment, executive_assessment, key_findings_summary,
            covert_persona_reference, tools_and_sources_used
        ))
        new_id = cursor.lastrowid
        conn.commit()
        _clear_read_caches()
        return new_id
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] add_case: {e}")
        raise e
    finally:
        conn.close()

def update_case(
    case_id: int,
    case_ref: str,
    case_name: str,
    case_type: str,
    start_date: str,
    end_date: str,
    report_date: str,
    target_scope: str,
    legitimate_interest_assessment: str,
    executive_assessment: str,
    key_findings_summary: str,
    covert_persona_reference: str,
    tools_and_sources_used: str
):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE cases
            SET case_ref = ?, case_name = ?, case_type = ?, start_date = ?, end_date = ?, report_date = ?, 
                target_scope = ?,
                legitimate_interest_assessment = ?, 
                executive_assessment = ?, key_findings_summary = ?, covert_persona_reference = ?, tools_and_sources_used = ?
            WHERE id = ?
        """, (
            case_ref, case_name, case_type, start_date, end_date, report_date,
            target_scope,
            legitimate_interest_assessment,
            executive_assessment, key_findings_summary, covert_persona_reference, tools_and_sources_used, case_id
        ))
        conn.commit()
        _clear_read_caches()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] update_case: {e}")
    finally:
        conn.close()


def _normalize_persona_reference(reference: str) -> str:
    normalized = reference.strip().upper()
    if not normalized:
        raise ValueError("Persona references cannot be empty.")
    return normalized


def add_case_persona_references(case_id: int, references: list[str]) -> list[dict]:
    """Permanently allocate unique persona references to a case."""
    normalized_references = list(dict.fromkeys(_normalize_persona_reference(reference) for reference in references))
    if not normalized_references:
        return []

    conn = get_connection()
    try:
        case = conn.execute(
            "SELECT id FROM cases WHERE id = ? AND deleted_at IS NULL",
            (case_id,),
        ).fetchone()
        if not case:
            raise ValueError("Case not found.")

        placeholders = ", ".join("?" for _ in normalized_references)
        existing_rows = conn.execute(
            f"""SELECT persona_reference FROM case_persona_references
                WHERE case_id = ? AND persona_reference IN ({placeholders}) COLLATE NOCASE""",
            [case_id, *normalized_references],
        ).fetchall()
        existing = {row["persona_reference"].upper() for row in existing_rows}
        duplicates = [reference for reference in normalized_references if reference in existing]
        if duplicates:
            raise ValueError(
                "Persona reference already allocated to this case: "
                + ", ".join(duplicates)
            )

        conn.executemany(
            "INSERT INTO case_persona_references (case_id, persona_reference) VALUES (?, ?)",
            [(case_id, reference) for reference in normalized_references],
        )
        rows = [
            dict(row)
            for row in conn.execute(
                f"""SELECT persona_reference, allocated_at FROM case_persona_references
                    WHERE case_id = ? AND persona_reference IN ({placeholders}) COLLATE NOCASE
                    ORDER BY id ASC""",
                [case_id, *normalized_references],
            ).fetchall()
        ]
        conn.commit()
    except sqlite3.Error as exc:
        conn.rollback()
        raise RuntimeError(f"Unable to allocate persona references: {exc}") from exc
    finally:
        conn.close()
    _clear_read_caches()
    return rows


@st.cache_data(show_spinner=False)
def get_case_persona_references(case_id: int) -> list[dict]:
    conn = get_connection()
    try:
        return [
            dict(row)
            for row in conn.execute(
                """SELECT persona_reference, allocated_at
                   FROM case_persona_references
                   WHERE case_id = ?
                   ORDER BY allocated_at ASC, id ASC""",
                (case_id,),
            ).fetchall()
        ]
    finally:
        conn.close()


@st.cache_data(show_spinner=False)
def get_persona_reference_usage(year: int) -> list[dict]:
    if not isinstance(year, int) or isinstance(year, bool):
        raise ValueError("year must be an integer.")
    conn = get_connection()
    try:
        return [
            dict(row)
            for row in conn.execute(
                """SELECT p.persona_reference, p.allocated_at, cl.name AS client_name,
                          c.case_ref, c.case_name, c.lifecycle_status
                   FROM case_persona_references AS p
                   JOIN cases AS c ON c.id = p.case_id
                   JOIN clients AS cl ON cl.id = c.client_id
                   WHERE c.deleted_at IS NULL
                     AND cl.deleted_at IS NULL
                     AND strftime('%Y', p.allocated_at) = ?
                   ORDER BY p.allocated_at DESC, p.id DESC""",
                (str(year),),
            ).fetchall()
        ]
    finally:
        conn.close()


def delete_case(case_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE cases SET deleted_at = CURRENT_TIMESTAMP WHERE id = ?", (case_id,))
        cursor.execute("UPDATE case_subjects SET deleted_at = CURRENT_TIMESTAMP WHERE case_id = ? AND deleted_at IS NULL", (case_id,))
        cursor.execute("UPDATE case_findings SET deleted_at = CURRENT_TIMESTAMP WHERE case_id = ? AND deleted_at IS NULL", (case_id,))
        conn.commit()
        _clear_read_caches()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] delete_case: {e}")
    finally:
        conn.close()

def restore_case(case_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE cases SET deleted_at = NULL WHERE id = ?", (case_id,))
        cursor.execute("UPDATE case_subjects SET deleted_at = NULL WHERE case_id = ?", (case_id,))
        cursor.execute("UPDATE case_findings SET deleted_at = NULL WHERE case_id = ?", (case_id,))
        conn.commit()
        _clear_read_caches()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] restore_case: {e}")
    finally:
        conn.close()

def hard_delete_case(case_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM case_findings WHERE case_id = ?", (case_id,))
        cursor.execute("DELETE FROM case_subjects WHERE case_id = ?", (case_id,))
        cursor.execute("DELETE FROM cases WHERE id = ?", (case_id,))
        conn.commit()
        _clear_read_caches()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] hard_delete_case: {e}")
    finally:
        conn.close()

# --- Case Subjects ---
def _map_case_subject_row(row: dict) -> dict:
    subject_type = row.get("subject_type", "Other Subject")
    subject_data = decode_subject_data(subject_type, row.get("subject_data_json"))
    display_name = row.get("display_name") or subject_display_name(subject_type, subject_data, fallback="Subject")
    return {
        "id": row.get("id"),
        "case_id": row.get("case_id"),
        "subject_type": subject_type,
        "relationship_to_case": row.get("relationship_to_case", ""),
        "display_name": display_name,
        "subject_data": subject_data,
        "notes": row.get("notes", "") or "",
        "deleted_at": row.get("deleted_at"),
        "finding_count": row.get("finding_count", 0),
        "linked_subject_count": row.get("linked_subject_count", 0),
        "summary_lines": subject_summary_lines(subject_type, subject_data),
    }


@st.cache_data(show_spinner=False)
def get_case_subject(subject_id: int) -> dict | None:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM case_subjects WHERE id = ? AND deleted_at IS NULL", (subject_id,))
        row = cursor.fetchone()
        return _map_case_subject_row(dict(row)) if row else None
    except sqlite3.Error as e:
        print(f"[DB ERROR] get_case_subject: {e}")
        return None
    finally:
        conn.close()


@st.cache_data(show_spinner=False)
def get_case_subjects(case_id: int) -> list[dict]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.*, COUNT(f.id) AS finding_count
            FROM case_subjects s
            LEFT JOIN case_findings f ON f.subject_id = s.id AND f.deleted_at IS NULL
            WHERE s.case_id = ? AND s.deleted_at IS NULL
            GROUP BY s.id
            ORDER BY s.id ASC
        """, (case_id,))
        subjects = [_map_case_subject_row(dict(row)) for row in cursor.fetchall()]
        for subject in subjects:
            linked_subject_ids = {
                other["id"]
                for other in subjects
                if other["id"] != subject["id"]
                and (
                    other["relationship_to_case"] == subject["display_name"]
                    or subject["relationship_to_case"] == other["display_name"]
                )
            }
            subject["linked_subject_count"] = len(linked_subject_ids)
        return subjects
    except sqlite3.Error as e:
        print(f"[DB ERROR] get_case_subjects: {e}")
        return []
    finally:
        conn.close()


@st.cache_data(show_spinner=False)
def get_deleted_case_subjects() -> list[dict]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.*, c.case_name, cl.name AS client_name
            FROM case_subjects s
            JOIN cases c ON s.case_id = c.id
            JOIN clients cl ON c.client_id = cl.id
            WHERE s.deleted_at IS NOT NULL
        """)
        return [_map_case_subject_row(dict(row)) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"[DB ERROR] get_deleted_case_subjects: {e}")
        return []
    finally:
        conn.close()


def add_case_subject(
    case_id: int,
    subject_type: str,
    relationship_to_case: str,
    display_name: str,
    subject_data: dict,
    notes: str = '',
) -> int:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO case_subjects (
                case_id, subject_type, relationship_to_case, display_name, subject_data_json, notes
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (case_id, subject_type, relationship_to_case, display_name, encode_subject_data(subject_type, subject_data), notes))
        new_id = cursor.lastrowid
        conn.commit()
        _clear_read_caches()
        return new_id
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] add_case_subject: {e}")
        raise e
    finally:
        conn.close()


def update_case_subject(
    subject_id: int,
    subject_type: str,
    relationship_to_case: str,
    display_name: str,
    subject_data: dict,
    notes: str = '',
):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE case_subjects
            SET subject_type = ?, relationship_to_case = ?, display_name = ?, subject_data_json = ?, notes = ?
            WHERE id = ? AND deleted_at IS NULL
        """, (subject_type, relationship_to_case, display_name, encode_subject_data(subject_type, subject_data), notes, subject_id))
        conn.commit()
        _clear_read_caches()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] update_case_subject: {e}")
    finally:
        conn.close()


def delete_case_subject(subject_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE case_subjects SET deleted_at = CURRENT_TIMESTAMP WHERE id = ?", (subject_id,))
        cursor.execute("UPDATE case_findings SET deleted_at = CURRENT_TIMESTAMP WHERE subject_id = ? AND deleted_at IS NULL", (subject_id,))
        conn.commit()
        _clear_read_caches()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] delete_case_subject: {e}")
    finally:
        conn.close()


def restore_case_subject(subject_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE case_subjects SET deleted_at = NULL WHERE id = ?", (subject_id,))
        cursor.execute("UPDATE case_findings SET deleted_at = NULL WHERE subject_id = ?", (subject_id,))
        conn.commit()
        _clear_read_caches()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] restore_case_subject: {e}")
    finally:
        conn.close()


def hard_delete_case_subject(subject_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM case_findings WHERE subject_id = ?", (subject_id,))
        cursor.execute("DELETE FROM case_subjects WHERE id = ?", (subject_id,))
        conn.commit()
        _clear_read_caches()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] hard_delete_case_subject: {e}")
    finally:
        conn.close()

# --- Risk Library (Formerly Vulnerability Library) ---
@st.cache_data(show_spinner=False)
def get_risk_library() -> list[dict]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM risk_library WHERE retired_at IS NULL")
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"[DB ERROR] get_risk_library: {e}")
        return []
    finally:
        conn.close()

def add_risk_library_item(
    category: str,
    title: str,
    default_risk_level: str,
    description: str = '',
    investigative_guidance: str = '',
    source_confidence: str = 'High Confidence',
    refs: str = '',
    *,
    provenance: str = '',
    actor_user_id: int | None = None,
):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO risk_library
            (category, title, default_risk_level, description, investigative_guidance, source_confidence, refs, provenance, created_by_user_id, updated_by_user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (category, title, default_risk_level, description, investigative_guidance, source_confidence, refs,
              provenance, actor_user_id, actor_user_id))
        conn.commit()
        _clear_read_caches()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] add_risk_library_item: {e}")
    finally:
        conn.close()


def add_to_risk_library(
    category: str,
    title: str,
    default_risk_level: str,
    description: str = '',
    investigative_guidance: str = '',
    source_confidence: str = 'High Confidence',
    refs: str = ''
):
    return add_risk_library_item(
        category=category,
        title=title,
        default_risk_level=default_risk_level,
        description=description,
        investigative_guidance=investigative_guidance,
        source_confidence=source_confidence,
        refs=refs,
    )


def delete_risk_library_item(risk_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM risk_library WHERE id = ?", (risk_id,))
        conn.commit()
        _clear_read_caches()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] delete_risk_library_item: {e}")
    finally:
        conn.close()


def delete_from_risk_library(risk_id: int):
    return delete_risk_library_item(risk_id)


def update_risk_library_item(
    risk_id: int,
    category: str,
    title: str,
    default_risk_level: str,
    description: str,
    investigative_guidance: str,
    source_confidence: str,
    refs: str,
    expected_revision: int | None = None,
    actor_user_id: int | None = None,
):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
            UPDATE risk_library 
            SET category = ?, title = ?, default_risk_level = ?, description = ?, investigative_guidance = ?,
                source_confidence = ?, refs = ?, revision = revision + 1, updated_at = CURRENT_TIMESTAMP,
                updated_by_user_id = ?
            WHERE id = ? AND retired_at IS NULL
        """
        params = [category, title, default_risk_level, description, investigative_guidance,
                  source_confidence, refs, actor_user_id, risk_id]
        if expected_revision is not None:
            query += " AND revision = ?"
            params.append(expected_revision)
        cursor.execute(query, params)
        if expected_revision is not None and cursor.rowcount != 1:
            raise ValueError("Risk library item was changed or retired by another user.")
        conn.commit()
        _clear_read_caches()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] update_risk_library_item: {e}")
    finally:
        conn.close()


def update_in_risk_library(
    risk_id: int,
    category: str,
    title: str,
    default_risk_level: str,
    description: str,
    investigative_guidance: str,
    source_confidence: str,
    refs: str
):
    return update_risk_library_item(
        risk_id=risk_id,
        category=category,
        title=title,
        default_risk_level=default_risk_level,
        description=description,
        investigative_guidance=investigative_guidance,
        source_confidence=source_confidence,
        refs=refs,
    )


def _manager_actor_id(conn, username: str) -> int:
    row = conn.execute(
        """SELECT id FROM users
           WHERE username = ? AND active = 1 AND role IN ('administrator', 'manager')""",
        (username.strip().lower(),),
    ).fetchone()
    if not row:
        raise PermissionError("An active administrator or manager is required.")
    return row["id"]


def get_risk_library_entries(include_retired: bool = False) -> list[dict]:
    """Return active templates, optionally including retired history."""
    conn = get_connection()
    try:
        query = "SELECT * FROM risk_library"
        if not include_retired:
            query += " WHERE retired_at IS NULL"
        return [dict(row) for row in conn.execute(query + " ORDER BY category, title, id")]
    finally:
        conn.close()


def retire_risk_library_item(
    risk_id: int,
    username: str | None = None,
    *,
    expected_revision: int | None = None,
    actor_user_id: int | None = None,
) -> None:
    """Retire, rather than delete, a risk definition with optimistic locking."""
    conn = get_connection()
    try:
        if actor_user_id is None:
            if not username:
                raise ValueError("A manager username or actor_user_id is required.")
            actor_user_id = _manager_actor_id(conn, username)
        if expected_revision is None:
            row = conn.execute("SELECT revision FROM risk_library WHERE id = ? AND retired_at IS NULL", (risk_id,)).fetchone()
            if not row:
                raise ValueError("Risk library item is retired or not found.")
            expected_revision = row["revision"]
        cursor = conn.execute(
            """UPDATE risk_library SET retired_at = CURRENT_TIMESTAMP, retired_by_user_id = ?,
               revision = revision + 1, updated_at = CURRENT_TIMESTAMP, updated_by_user_id = ?
               WHERE id = ? AND retired_at IS NULL AND revision = ?""",
            (actor_user_id, actor_user_id, risk_id, expected_revision),
        )
        if cursor.rowcount != 1:
            raise ValueError("Risk library item was changed, retired, or not found.")
        conn.commit()
    finally:
        conn.close()
    log_audit_event(actor_user_id, "risk.retired", "risk_library", risk_id)
    _clear_read_caches()


def restore_risk_library_item(risk_id: int, username: str) -> None:
    """Restore a retired template. The caller must be an active manager/admin."""
    conn = get_connection()
    try:
        actor_user_id = _manager_actor_id(conn, username)
        cursor = conn.execute(
            """UPDATE risk_library SET retired_at = NULL, retired_by_user_id = NULL, revision = revision + 1,
               updated_at = CURRENT_TIMESTAMP, updated_by_user_id = ?
               WHERE id = ? AND retired_at IS NOT NULL""",
            (actor_user_id, risk_id),
        )
        if cursor.rowcount != 1:
            raise ValueError("Risk library item is not retired or was not found.")
        conn.commit()
    finally:
        conn.close()
    log_audit_event(actor_user_id, "risk.restored", "risk_library", risk_id)
    _clear_read_caches()

# --- Case Findings (Formerly Project Findings) ---
def _map_case_finding_row(r: dict, include_details: bool = True) -> dict:
    category = r.get('domain_category', '')
    mapped = {
        'id': r.get('id'),
        'case_id': r.get('case_id'),
        'subject_id': r.get('subject_id'),
        'subject_name': r.get('subject_name'),
        'category': category,
        'title': r.get('title'),
        'risk_level': r.get('risk_level'),
        'confidence_level': r.get('source_confidence'),
        'summary': r.get('summary'),
        'source': r.get('source', ''),
        'category_data': decode_finding_data(category, r.get('category_data_json')),
        'category_summary_lines': finding_summary_lines(
            category,
            r.get('category_data_json'),
        ),
        'deleted_at': r.get('deleted_at')
    }
    if include_details:
        mapped['description'] = r.get('detailed_findings') or ''
    return mapped

@st.cache_data(show_spinner=False)
def get_case_finding(finding_id: int) -> dict | None:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT f.*, s.display_name AS subject_name
            FROM case_findings f
            LEFT JOIN case_subjects s ON f.subject_id = s.id
            WHERE f.id = ? AND f.deleted_at IS NULL
        """, (finding_id,))
        row = cursor.fetchone()
        return _map_case_finding_row(dict(row), include_details=True) if row else None
    except sqlite3.Error as e:
        print(f"[DB ERROR] get_case_finding: {e}")
        return None
    finally:
        conn.close()

@st.cache_data(show_spinner=False)
def get_case_findings(case_id: int) -> list[dict]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT f.*, s.display_name AS subject_name
            FROM case_findings f
            LEFT JOIN case_subjects s ON f.subject_id = s.id
            WHERE f.case_id = ? AND f.deleted_at IS NULL
        """, (case_id,))
        rows = [dict(row) for row in cursor.fetchall()]
        return [_map_case_finding_row(r, include_details=True) for r in rows]
    except sqlite3.Error as e:
        print(f"[DB ERROR] get_case_findings: {e}")
        return []
    finally:
        conn.close()

@st.cache_data(show_spinner=False)
def get_case_findings_overview(case_id: int) -> list[dict]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT f.id, f.case_id, f.subject_id, s.display_name AS subject_name, f.domain_category, f.title, f.risk_level, f.source_confidence,
                   f.summary, f.source, f.category_data_json, f.deleted_at
            FROM case_findings f
            LEFT JOIN case_subjects s ON f.subject_id = s.id
            WHERE f.case_id = ? AND f.deleted_at IS NULL
        """, (case_id,))
        rows = [dict(row) for row in cursor.fetchall()]
        return [_map_case_finding_row(r, include_details=False) for r in rows]
    except sqlite3.Error as e:
        print(f"[DB ERROR] get_case_findings_overview: {e}")
        return []
    finally:
        conn.close()

@st.cache_data(show_spinner=False)
def get_deleted_case_findings() -> list[dict]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT f.*, c.case_name as case_name, s.display_name AS subject_name
            FROM case_findings f 
            JOIN cases c ON f.case_id = c.id 
            LEFT JOIN case_subjects s ON f.subject_id = s.id
            WHERE f.deleted_at IS NOT NULL
        """)
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"[DB ERROR] get_deleted_case_findings: {e}")
        return []
    finally:
        conn.close()

def add_case_finding(
    case_id: int,
    domain_category: str,
    title: str,
    risk_level: str,
    source_confidence: str = 'High Confidence',
    summary: str = '',
    detailed_findings: str = '',
    source: str = '',
    category_data: dict[str, str] | None = None,
    subject_id: int | None = None,
):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO case_findings (
                case_id, subject_id, domain_category, title, risk_level, source_confidence, 
                summary, detailed_findings, source, category_data_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            case_id, subject_id, domain_category, title, risk_level, source_confidence,
            summary, detailed_findings, source, encode_finding_data(domain_category, category_data),
        ))
        conn.commit()
        _clear_read_caches()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] add_case_finding: {e}")
    finally:
        conn.close()

def update_case_finding(
    finding_id: int,
    domain_category: str,
    title: str,
    risk_level: str,
    source_confidence: str,
    summary: str,
    detailed_findings: str,
    source: str,
    category_data: dict[str, str] | None,
    subject_id: int | None = None,
):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE case_findings 
            SET subject_id = ?, domain_category = ?, title = ?, risk_level = ?, source_confidence = ?, 
                summary = ?, detailed_findings = ?, source = ?, category_data_json = ?
            WHERE id = ?
        """, (
            subject_id, domain_category, title, risk_level, source_confidence, summary,
            detailed_findings, source, encode_finding_data(domain_category, category_data), finding_id,
        ))
        conn.commit()
        _clear_read_caches()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] update_case_finding: {e}")
    finally:
        conn.close()

def delete_case_finding(finding_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE case_findings SET deleted_at = CURRENT_TIMESTAMP WHERE id = ?", (finding_id,))
        conn.commit()
        _clear_read_caches()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] delete_case_finding: {e}")
    finally:
        conn.close()

def restore_case_finding(finding_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE case_findings SET deleted_at = NULL WHERE id = ?", (finding_id,))
        conn.commit()
        _clear_read_caches()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] restore_case_finding: {e}")
    finally:
        conn.close()

def hard_delete_case_finding(finding_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM case_findings WHERE id = ?", (finding_id,))
        conn.commit()
        _clear_read_caches()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] hard_delete_case_finding: {e}")
    finally:
        conn.close()

# --- Investigator Directory ---
@st.cache_data(show_spinner=False)
def get_investigators() -> list[dict]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, user_id, name, title, credentials, bio
               FROM investigators
               WHERE available = 1
               ORDER BY name COLLATE NOCASE"""
        )
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"[DB ERROR] get_investigators: {e}")
        return []
    finally:
        conn.close()

@st.cache_data(show_spinner=False)
def get_client_with_most_recent_finding():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.client_id
            FROM case_findings f
            JOIN cases c ON f.case_id = c.id
            WHERE f.deleted_at IS NULL AND c.deleted_at IS NULL
            ORDER BY f.id DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        return row['client_id'] if row else None
    except sqlite3.Error as e:
        print(f"[DB ERROR] get_client_with_most_recent_finding: {e}")
        return None
    finally:
        conn.close()


# --- Three-role foundation APIs ---
def upsert_investigator_profile(
    user_id: int,
    *,
    completion_status: str = "incomplete",
    credentials: str = "",
    professional_bio: str = "",
) -> int:
    """Create or update the one-to-one professional profile for an investigator."""
    if completion_status not in {"incomplete", "complete"}:
        raise ValueError("Invalid profile completion status.")
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO investigator_profiles
               (user_id, completion_status, credentials, professional_bio)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
               completion_status = excluded.completion_status, credentials = excluded.credentials,
               professional_bio = excluded.professional_bio,
               updated_at = CURRENT_TIMESTAMP""",
            (user_id, completion_status, credentials, professional_bio),
        )
        synchronize_investigator_directory(conn, user_id)
        conn.commit()
        _clear_read_caches()
        return cursor.lastrowid or user_id
    finally:
        conn.close()


def get_investigator_profile(user_id: int) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT p.*, u.username, u.display_name, u.title, u.active
               FROM investigator_profiles p JOIN users u ON u.id = p.user_id
               WHERE p.user_id = ? AND u.role = 'investigator'""",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_case_evidence_access(username: str, case_id: int) -> dict:
    """Return the assignment and lifecycle facts used by the evidence UI."""
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT c.lifecycle_status, c.lead_investigator_id, u.id AS user_id, u.active, u.role
               FROM cases c
               LEFT JOIN users u ON u.username = ?
               WHERE c.id = ? AND c.deleted_at IS NULL""",
            (username.strip().lower(), case_id),
        ).fetchone()
        if not row:
            return {"assigned": False, "is_in_progress": False, "case_state": "Unknown"}
        assigned = bool(
            row["user_id"]
            and row["active"]
            and row["role"] == "investigator"
            and row["lead_investigator_id"] == row["user_id"]
        )
        return {
            "assigned": assigned,
            "is_in_progress": row["lifecycle_status"] == "in_progress",
            "case_state": row["lifecycle_status"],
        }
    finally:
        conn.close()


def get_cases_with_workflow(username: str | None = None, role: str | None = None) -> list[dict]:
    """Return workflow-ready cases, limited to assignments for investigators."""
    conn = get_connection()
    try:
        params: list[object] = []
        where = ["c.deleted_at IS NULL", "cl.deleted_at IS NULL"]
        if username is not None:
            user = conn.execute(
                "SELECT id, role, active FROM users WHERE username = ?", (username.strip().lower(),)
            ).fetchone()
            if not user or not user["active"]:
                return []
            if role is not None and role != user["role"]:
                raise PermissionError("Requested role does not match the active account.")
            if user["role"] == "investigator":
                where.append("c.lead_investigator_id = ?")
                params.append(user["id"])
            elif user["role"] not in {"administrator", "manager"}:
                raise PermissionError("Unknown workflow role.")
        rows = conn.execute(
            f"""SELECT c.*, cl.name AS client_name, i.name AS investigator_name,
                       i.bio AS investigator_description
                FROM cases c JOIN clients cl ON cl.id = c.client_id
                LEFT JOIN investigators i ON i.user_id = c.lead_investigator_id
                WHERE {' AND '.join(where)}
                ORDER BY CASE c.lifecycle_status
                    WHEN 'in_progress' THEN 0 WHEN 'submitted' THEN 1 WHEN 'rejected' THEN 2
                    WHEN 'preparation' THEN 3 ELSE 4 END, c.updated_at DESC, c.id DESC""",
            params,
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def create_assigned_case(
    case_ref: str,
    case_name: str,
    client_id: int,
    *,
    actor_user_id: int,
    case_type: str = "Enhanced Due Diligence",
) -> int:
    """Create a Preparation case assigned to its active investigator creator."""
    case_ref, case_name = case_ref.strip(), case_name.strip()
    if not case_ref or not case_name:
        raise ValueError("Case reference and case name are required.")
    conn = get_connection()
    try:
        actor = conn.execute(
            "SELECT id FROM users WHERE id = ? AND role = 'investigator' AND active = 1",
            (actor_user_id,),
        ).fetchone()
        if not actor:
            raise PermissionError("Only an active investigator can create an assigned case.")
        client = conn.execute(
            "SELECT id FROM clients WHERE id = ? AND deleted_at IS NULL", (client_id,)
        ).fetchone()
        if not client:
            raise ValueError("Client not found.")
        cursor = conn.execute(
            """INSERT INTO cases
               (case_ref, case_name, case_type, client_id, lifecycle_status, lead_investigator_id,
                created_by_user_id, updated_by_user_id)
               VALUES (?, ?, ?, ?, 'preparation', ?, ?, ?)""",
            (case_ref, case_name, case_type, client_id, actor_user_id, actor_user_id, actor_user_id),
        )
        conn.commit()
        case_id = cursor.lastrowid
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        raise ValueError("Case reference already exists.") from exc
    finally:
        conn.close()
    log_audit_event(actor_user_id, "case.created_assigned", "case", case_id, {"client_id": client_id})
    _clear_read_caches()
    return case_id


def _require_management_role(conn, actor_username: str | None, actor_role: str | None) -> None:
    """Validate an active manager/admin, using the Streamlit session for legacy callers."""
    if actor_username is None:
        actor_username = st.session_state.get("username")
    if not actor_username:
        raise PermissionError("Administrator or manager access is required.")
    row = conn.execute(
        "SELECT role, active FROM users WHERE username = ?", (actor_username.strip().lower(),)
    ).fetchone()
    if (
        not row
        or not row["active"]
        or row["role"] not in {"administrator", "manager"}
        or (actor_role is not None and row["role"] != actor_role)
    ):
        raise PermissionError("Administrator or manager access is required.")


def _month_bounds(month: str) -> tuple[str, str]:
    """Accept YYYY-MM or an ISO date and return the containing calendar month."""
    try:
        month_start = datetime.strptime(month[:7], "%Y-%m").date().replace(day=1)
    except (TypeError, ValueError) as exc:
        raise ValueError("month must start with YYYY-MM.") from exc
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return month_start.isoformat(), next_month.isoformat()


def get_management_activity(
    month: str,
    investigator_id: int | None = None,
    *,
    actor_username: str | None = None,
    actor_role: str | None = None,
) -> list[dict]:
    """Return raw case drilldown for a selected calendar month (or start date)."""
    start, end = _month_bounds(month)
    return get_management_activity_range(
        start,
        end,
        investigator_id,
        actor_username=actor_username,
        actor_role=actor_role,
    )


def get_management_activity_range(
    start_date: str,
    end_date: str,
    investigator_id: int | None = None,
    *,
    actor_username: str | None = None,
    actor_role: str | None = None,
) -> list[dict]:
    """Return raw case drilldown for an inclusive-start, exclusive-end date range."""
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except (TypeError, ValueError) as exc:
        raise ValueError("start_date and end_date must use YYYY-MM-DD.") from exc
    if start >= end:
        raise ValueError("end_date must be later than start_date.")
    conn = get_connection()
    try:
        _require_management_role(conn, actor_username, actor_role)
        where = ["c.deleted_at IS NULL", "c.updated_at >= ?", "c.updated_at < ?"]
        params: list[object] = [start.isoformat(), end.isoformat()]
        if investigator_id is not None:
            where.append("c.lead_investigator_id = ?")
            params.append(investigator_id)
        rows = conn.execute(
            f"""SELECT c.id AS case_id, c.case_ref, c.case_name, c.lifecycle_status, c.created_at,
                       c.updated_at, c.investigation_started_at, cl.name AS client_name,
                       c.lead_investigator_id, i.name AS investigator_name
                FROM cases c JOIN clients cl ON cl.id = c.client_id
                LEFT JOIN investigators i ON i.user_id = c.lead_investigator_id
                WHERE {' AND '.join(where)} ORDER BY c.updated_at DESC, c.id DESC""",
            params,
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_management_lifecycle_metrics(
    start_date: str | None = None,
    end_date: str | None = None,
    *,
    actor_username: str | None = None,
    actor_role: str | None = None,
) -> dict[str, int]:
    """Count lifecycle transitions by their destination status within an optional date range."""
    if (start_date is None) != (end_date is None):
        raise ValueError("start_date and end_date must be provided together.")
    if start_date is not None and end_date is not None:
        try:
            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)
        except ValueError as exc:
            raise ValueError("start_date and end_date must use YYYY-MM-DD.") from exc
        if start >= end:
            raise ValueError("end_date must be later than start_date.")
    else:
        start = end = None

    conn = get_connection()
    try:
        _require_management_role(conn, actor_username, actor_role)
        where = ["event_type = 'case.lifecycle_changed'"]
        params: list[object] = []
        if start and end:
            where.extend(("occurred_at >= ?", "occurred_at < ?"))
            params.extend((start.isoformat(), end.isoformat()))
        rows = conn.execute(
            f"""SELECT details_json FROM audit_events
                WHERE {' AND '.join(where)}""",
            params,
        ).fetchall()
    finally:
        conn.close()

    metrics = {status: 0 for status in ("in_progress", "submitted", "rejected", "completed")}
    for row in rows:
        try:
            status = json.loads(row["details_json"]).get("status")
        except (TypeError, json.JSONDecodeError):
            continue
        if status in metrics:
            metrics[status] += 1
    return metrics


def get_management_lifecycle_activity_by_month(
    start_date: str,
    end_date: str,
    *,
    actor_username: str | None = None,
    actor_role: str | None = None,
) -> dict[str, dict[str, int]]:
    """Count lifecycle transitions by destination status for each calendar month in a date range."""
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError as exc:
        raise ValueError("start_date and end_date must use YYYY-MM-DD.") from exc
    if start >= end:
        raise ValueError("end_date must be later than start_date.")

    conn = get_connection()
    try:
        _require_management_role(conn, actor_username, actor_role)
        rows = conn.execute(
            """SELECT occurred_at, details_json FROM audit_events
               WHERE event_type = 'case.lifecycle_changed'
                 AND occurred_at >= ? AND occurred_at < ?""",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
    finally:
        conn.close()

    activity: dict[str, dict[str, int]] = {}
    for row in rows:
        try:
            status = json.loads(row["details_json"]).get("status")
        except (TypeError, json.JSONDecodeError):
            continue
        if status not in {"in_progress", "submitted", "rejected", "completed"}:
            continue
        month = row["occurred_at"][:7]
        activity.setdefault(
            month,
            {"in_progress": 0, "submitted": 0, "rejected": 0, "completed": 0},
        )[status] += 1
    return activity


_MANAGEMENT_REPORT_SECTIONS = frozenset(
    {
        "throughput",
        "case_flow",
        "workload",
        "durations",
        "complexity",
        "personas",
        "difficult_cases",
    }
)
_MANAGEMENT_REPORT_PRESETS = frozenset(
    {"week", "fortnight", "month", "quarter", "six_months", "year", "custom"}
)


def _validate_management_report_configuration(configuration: dict) -> dict:
    if not isinstance(configuration, dict):
        raise ValueError("Report configuration must be an object.")
    preset = configuration.get("preset")
    if preset not in _MANAGEMENT_REPORT_PRESETS:
        raise ValueError("Report configuration has an invalid timeframe preset.")
    scope = configuration.get("scope")
    if scope not in {"team", "investigator"}:
        raise ValueError("Report configuration has an invalid scope.")
    investigator_id = configuration.get("investigator_id")
    if scope == "investigator" and (
        not isinstance(investigator_id, int) or isinstance(investigator_id, bool)
    ):
        raise ValueError("An investigator report configuration requires an investigator.")
    if configuration.get("complexity_mode", "totals") not in {"totals", "average"}:
        raise ValueError("Report configuration has an invalid complexity mode.")
    sections = configuration.get("sections", [])
    if not isinstance(sections, list) or not set(sections).issubset(_MANAGEMENT_REPORT_SECTIONS):
        raise ValueError("Report configuration contains invalid sections.")
    if preset == "custom":
        try:
            start = date.fromisoformat(configuration["start_date"])
            end = date.fromisoformat(configuration["end_date"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Custom report configurations require valid start and end dates.") from exc
        if start > end:
            raise ValueError("Report end date must not be before start date.")
    return {
        "preset": preset,
        "scope": scope,
        "investigator_id": investigator_id if scope == "investigator" else None,
        "complexity_mode": configuration.get("complexity_mode", "totals"),
        "sections": sorted(set(sections)),
        **(
            {
                "start_date": configuration["start_date"],
                "end_date": configuration["end_date"],
            }
            if preset == "custom"
            else {}
        ),
    }


def list_management_report_configurations(
    manager_user_id: int,
    *,
    actor_username: str | None = None,
    actor_role: str | None = None,
) -> list[dict]:
    conn = get_connection()
    try:
        _require_management_role(conn, actor_username, actor_role)
        rows = conn.execute(
            """SELECT id, name, configuration_json, created_at, updated_at
               FROM management_report_configurations
               WHERE manager_user_id = ? ORDER BY name COLLATE NOCASE""",
            (manager_user_id,),
        ).fetchall()
    finally:
        conn.close()
    result = []
    for row in rows:
        item = dict(row)
        item["configuration"] = json.loads(item.pop("configuration_json"))
        result.append(item)
    return result


def save_management_report_configuration(
    manager_user_id: int,
    name: str,
    configuration: dict,
    *,
    configuration_id: int | None = None,
    actor_username: str | None = None,
    actor_role: str | None = None,
) -> dict:
    name = name.strip()
    if not name:
        raise ValueError("Configuration name is required.")
    if len(name) > 100:
        raise ValueError("Configuration name must not exceed 100 characters.")
    payload = _validate_management_report_configuration(configuration)
    conn = get_connection()
    try:
        _require_management_role(conn, actor_username, actor_role)
        if configuration_id is None:
            cursor = conn.execute(
                """INSERT INTO management_report_configurations
                   (manager_user_id, name, configuration_json)
                   VALUES (?, ?, ?)""",
                (manager_user_id, name, json.dumps(payload, sort_keys=True)),
            )
            configuration_id = cursor.lastrowid
        else:
            cursor = conn.execute(
                """UPDATE management_report_configurations
                   SET name = ?, configuration_json = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE id = ? AND manager_user_id = ?""",
                (name, json.dumps(payload, sort_keys=True), configuration_id, manager_user_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("Report configuration not found.")
        conn.commit()
        row = conn.execute(
            """SELECT id, name, configuration_json, created_at, updated_at
               FROM management_report_configurations WHERE id = ?""",
            (configuration_id,),
        ).fetchone()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        raise ValueError("A report configuration with that name already exists.") from exc
    finally:
        conn.close()
    _clear_read_caches()
    result = dict(row)
    result["configuration"] = json.loads(result.pop("configuration_json"))
    return result


def delete_management_report_configuration(
    manager_user_id: int,
    configuration_id: int,
    *,
    actor_username: str | None = None,
    actor_role: str | None = None,
) -> None:
    conn = get_connection()
    try:
        _require_management_role(conn, actor_username, actor_role)
        cursor = conn.execute(
            "DELETE FROM management_report_configurations WHERE id = ? AND manager_user_id = ?",
            (configuration_id, manager_user_id),
        )
        if cursor.rowcount != 1:
            raise ValueError("Report configuration not found.")
        conn.commit()
    finally:
        conn.close()
    _clear_read_caches()


def get_management_reporting_facts(
    start_date: str,
    end_date: str,
    *,
    actor_username: str | None = None,
    actor_role: str | None = None,
) -> dict[str, list[dict]]:
    """Return immutable facts needed to assemble a management report.

    ``end_date`` is exclusive. Case-related facts are limited to records that
    existed by that cutoff so historical report totals do not change later.
    """
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except (TypeError, ValueError) as exc:
        raise ValueError("start_date and end_date must use YYYY-MM-DD.") from exc
    if start >= end:
        raise ValueError("end_date must be later than start_date.")

    conn = get_connection()
    try:
        _require_management_role(conn, actor_username, actor_role)
        cases = [
            dict(row)
            for row in conn.execute(
                """SELECT c.id, c.case_ref, c.case_name, c.created_at, c.deleted_at,
                          c.lifecycle_status, c.lead_investigator_id, c.updated_at,
                          u.display_name AS current_investigator_name, u.username AS current_investigator_username
                   FROM cases c LEFT JOIN users u ON u.id = c.lead_investigator_id
                   WHERE c.created_at < ?""",
                (end.isoformat(),),
            )
        ]
        case_ids = [case["id"] for case in cases]
        if not case_ids:
            return {"cases": [], "events": [], "subjects": [], "findings": [], "personas": [], "investigators": []}
        placeholders = ", ".join("?" for _ in case_ids)
        events = [
            dict(row)
            for row in conn.execute(
                f"""SELECT id, occurred_at, actor_user_id, event_type, entity_id, details_json
                    FROM audit_events
                    WHERE entity_type = 'case' AND entity_id IN ({placeholders})
                      AND occurred_at < ?
                    ORDER BY occurred_at, id""",
                [*(str(case_id) for case_id in case_ids), end.isoformat()],
            )
        ]
        subjects = [
            dict(row)
            for row in conn.execute(
                f"""SELECT id, case_id, created_at, deleted_at FROM case_subjects
                    WHERE case_id IN ({placeholders}) AND created_at < ?
                      AND (deleted_at IS NULL OR deleted_at >= ?)""",
                [*case_ids, end.isoformat(), end.isoformat()],
            )
        ]
        findings = [
            dict(row)
            for row in conn.execute(
                f"""SELECT id, case_id, created_at, deleted_at FROM case_findings
                    WHERE case_id IN ({placeholders}) AND created_at < ?
                      AND (deleted_at IS NULL OR deleted_at >= ?)""",
                [*case_ids, end.isoformat(), end.isoformat()],
            )
        ]
        personas = [
            dict(row)
            for row in conn.execute(
                f"""SELECT case_id, persona_reference, allocated_at
                    FROM case_persona_references
                    WHERE case_id IN ({placeholders}) AND allocated_at < ?""",
                [*case_ids, end.isoformat()],
            )
        ]
        investigators = [
            dict(row)
            for row in conn.execute(
                """SELECT id, username, display_name, active
                   FROM users WHERE role = 'investigator' ORDER BY COALESCE(display_name, username)"""
            )
        ]
        return {
            "cases": cases,
            "events": events,
            "subjects": subjects,
            "findings": findings,
            "personas": personas,
            "investigators": investigators,
        }
    finally:
        conn.close()


def get_annual_management_summary(
    year: int,
    investigator_id: int | None = None,
    *,
    actor_username: str | None = None,
    actor_role: str | None = None,
) -> list[dict]:
    """Return selected-year case counts by workflow state for management reporting."""
    if not isinstance(year, int) or isinstance(year, bool) or not 2000 <= year <= 9999:
        raise ValueError("year must be a four-digit integer.")
    conn = get_connection()
    try:
        _require_management_role(conn, actor_username, actor_role)
        where = ["c.deleted_at IS NULL", "c.created_at >= ?", "c.created_at < ?"]
        params: list[object] = [f"{year:04d}-01-01", f"{year + 1:04d}-01-01"]
        if investigator_id is not None:
            where.append("c.lead_investigator_id = ?")
            params.append(investigator_id)
        rows = conn.execute(
            f"""SELECT c.lifecycle_status AS metric_name, COUNT(*) AS metric_value
                FROM cases c WHERE {' AND '.join(where)}
                GROUP BY c.lifecycle_status ORDER BY c.lifecycle_status""",
            params,
        ).fetchall()
        summary = [{"metric_name": "cases_total", "metric_value": sum(row["metric_value"] for row in rows)}]
        summary.extend(dict(row) for row in rows)
        return summary
    finally:
        conn.close()


@st.cache_data(show_spinner=False)
def get_management_report_years(
    *,
    actor_username: str | None = None,
    actor_role: str | None = None,
) -> list[int]:
    """Return years with case or persona-allocation data for management reporting."""
    conn = get_connection()
    try:
        _require_management_role(conn, actor_username, actor_role)
        rows = conn.execute(
            """SELECT report_year FROM (
                   SELECT CAST(strftime('%Y', c.created_at) AS INTEGER) AS report_year
                   FROM cases AS c
                   WHERE c.deleted_at IS NULL
                   UNION
                   SELECT CAST(strftime('%Y', p.allocated_at) AS INTEGER) AS report_year
                   FROM case_persona_references AS p
                   JOIN cases AS c ON c.id = p.case_id
                   JOIN clients AS cl ON cl.id = c.client_id
                   WHERE c.deleted_at IS NULL AND cl.deleted_at IS NULL
               )
               WHERE report_year IS NOT NULL
               ORDER BY report_year DESC"""
        ).fetchall()
        return [row["report_year"] for row in rows]
    finally:
        conn.close()


def log_audit_event(actor_user_id: int | None, event_type: str, entity_type: str,
                    entity_id: int | str | None = None, details: dict | None = None) -> int:
    """Append an immutable audit record; no update/delete API is exposed."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """INSERT INTO audit_events (actor_user_id, event_type, entity_type, entity_id, details_json)
               VALUES (?, ?, ?, ?, ?)""",
            (actor_user_id, event_type, entity_type, str(entity_id) if entity_id is not None else None,
             json.dumps(details or {}, sort_keys=True)),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_audit_events(limit: int = 100) -> list[dict]:
    """Return newest audit events for administrator-facing history views."""
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1000:
        raise ValueError("limit must be an integer between 1 and 1000.")
    conn = get_connection()
    try:
        return [dict(row) for row in conn.execute(
            """SELECT a.*, u.username AS actor_username, u.display_name AS actor_display_name
               FROM audit_events a LEFT JOIN users u ON u.id = a.actor_user_id
               ORDER BY a.id DESC LIMIT ?""",
            (limit,),
        )]
    finally:
        conn.close()


def transition_case_lifecycle(case_id: int, lifecycle_status: str, *, actor_user_id: int) -> None:
    """Move a case through allowed states and assign immutable lifecycle dates server-side."""
    transitions = {
        "preparation": {"in_progress"},
        "in_progress": {"submitted"},
        "submitted": {"rejected", "completed"},
        "rejected": {"in_progress"},
        "completed": set(),
    }
    conn = get_connection()
    try:
        row = conn.execute("SELECT lifecycle_status FROM cases WHERE id = ? AND deleted_at IS NULL", (case_id,)).fetchone()
        if not row:
            raise ValueError("Case not found.")
        if lifecycle_status not in transitions.get(row["lifecycle_status"], set()):
            raise ValueError(
                "Cannot transition case from "
                f"{format_lifecycle_status(row['lifecycle_status'])} to "
                f"{format_lifecycle_status(lifecycle_status)}."
            )
        if lifecycle_status == "in_progress":
            conn.execute(
                """UPDATE cases SET lifecycle_status = ?, start_date = COALESCE(start_date, DATE('now')),
                   investigation_started_at = COALESCE(investigation_started_at, CURRENT_TIMESTAMP),
                   investigation_started_by_user_id = COALESCE(investigation_started_by_user_id, ?),
                   updated_at = CURRENT_TIMESTAMP, updated_by_user_id = ? WHERE id = ?""",
                (lifecycle_status, actor_user_id, actor_user_id, case_id),
            )
        elif lifecycle_status == "submitted":
            conn.execute(
                """UPDATE cases SET lifecycle_status = ?, end_date = COALESCE(end_date, DATE('now')),
                   updated_at = CURRENT_TIMESTAMP, updated_by_user_id = ? WHERE id = ?""",
                (lifecycle_status, actor_user_id, case_id),
            )
        elif lifecycle_status == "completed":
            conn.execute(
                """UPDATE cases SET lifecycle_status = ?, report_date = COALESCE(report_date, DATE('now')),
                   updated_at = CURRENT_TIMESTAMP, updated_by_user_id = ? WHERE id = ?""",
                (lifecycle_status, actor_user_id, case_id),
            )
        else:
            conn.execute(
                "UPDATE cases SET lifecycle_status = ?, updated_at = CURRENT_TIMESTAMP, updated_by_user_id = ? WHERE id = ?",
                (lifecycle_status, actor_user_id, case_id),
            )
        conn.commit()
    finally:
        conn.close()
    log_audit_event(actor_user_id, "case.lifecycle_changed", "case", case_id, {"status": lifecycle_status})
    _clear_read_caches()


def assign_case_lead_investigator(
    case_id: int,
    investigator_user_id: int | None,
    *,
    actor_user_id: int,
) -> None:
    conn = get_connection()
    try:
        if investigator_user_id is None:
            cursor = conn.execute(
                """UPDATE cases
                   SET lead_investigator_id = NULL, updated_at = CURRENT_TIMESTAMP, updated_by_user_id = ?
                   WHERE id = ?""",
                (actor_user_id, case_id),
            )
            event_type = "case.lead_unassigned"
            details = {}
        else:
            investigator = conn.execute(
                """SELECT user_id FROM investigators
                   WHERE user_id = ? AND available = 1""",
                (investigator_user_id,),
            ).fetchone()
            if not investigator:
                raise ValueError("Lead investigator must be available in the investigator directory.")
            cursor = conn.execute(
                """UPDATE cases
                   SET lead_investigator_id = ?, updated_at = CURRENT_TIMESTAMP, updated_by_user_id = ?
                   WHERE id = ?""",
                (investigator_user_id, actor_user_id, case_id),
            )
            event_type = "case.lead_assigned"
            details = {"investigator_user_id": investigator_user_id}
        if cursor.rowcount != 1:
            raise ValueError("Case not found.")
        conn.commit()
    finally:
        conn.close()
    log_audit_event(actor_user_id, event_type, "case", case_id, details)
    _clear_read_caches()


def add_case_evidence(case_id: int, subject_id: int | None, domain_category: str, title: str,
                      risk_level: str, *, actor_user_id: int, summary: str = "",
                      detailed_findings: str = "", source: str = "", category_data: dict | None = None) -> int:
    """Actor-aware foundation API for evidence/finding creation."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """INSERT INTO case_findings
               (case_id, subject_id, domain_category, title, risk_level, summary, detailed_findings, source,
                category_data_json, created_by_user_id, updated_by_user_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (case_id, subject_id, domain_category, title, risk_level, summary, detailed_findings, source,
             json.dumps(category_data or {}, sort_keys=True), actor_user_id, actor_user_id),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def create_report_version(
    case_id: int,
    version_number: int,
    *,
    actor_user_id: int,
    status: str = "draft",
    content_hash: str | None = None,
    storage_reference: str | None = None,
    case_start_date: str | None = None,
    approval_data: dict | None = None,
) -> int:
    """Record a draft/final generated artefact and its immutable integrity data."""
    if version_number < 1:
        raise ValueError("version_number must be at least 1.")
    if status not in {"draft", "final"}:
        raise ValueError("status must be 'draft' or 'final'.")
    approval_json = None
    approved_at = None
    approved_by = None
    if status == "final":
        if not approval_data:
            raise ValueError("approval_data is required for a final report version.")
        from reporting.versioning import approval_signoff
        signoff = approval_signoff(approval_data)
        approval_json = json.dumps(approval_data, sort_keys=True, default=str)
        approved_at = signoff["approved_at"]
        approved_by = signoff["approved_by"]
    if storage_reference and not content_hash:
        from reporting.versioning import sha256_file
        content_hash = sha256_file(storage_reference)
    conn = get_connection()
    try:
        review_status = "approved" if status == "final" else "draft"
        if status == "final":
            reviewer = conn.execute(
                """SELECT id FROM users WHERE id = ? AND active = 1
                   AND role IN ('administrator', 'manager')""",
                (actor_user_id,),
            ).fetchone()
            if not reviewer:
                raise PermissionError("Final reports require an active administrator or manager.")
        cursor = conn.execute(
            """INSERT INTO report_versions
               (case_id, version_number, status, content_hash, storage_reference, case_start_date,
                approval_data_json, approved_at, approved_by, review_status, reviewed_at, reviewed_by_user_id,
                integrity_verified_at, created_by_user_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CASE WHEN ? = 'approved' THEN CURRENT_TIMESTAMP END, ?,
                       CASE WHEN ? IS NULL THEN NULL ELSE CURRENT_TIMESTAMP END, ?)""",
            (case_id, version_number, status, content_hash, storage_reference, case_start_date,
             approval_json, approved_at, approved_by, review_status, review_status, actor_user_id,
             content_hash, actor_user_id),
        )
        conn.commit()
        report_version_id = cursor.lastrowid
    finally:
        conn.close()
    log_audit_event(
        actor_user_id, "report.version_created", "report_version", report_version_id,
        {"case_id": case_id, "version": version_number, "status": status, "content_hash": content_hash},
    )
    return report_version_id


def reserve_report_version(case_id: int, *, status: str, actor_user_id: int) -> dict:
    """Atomically reserve the next case-wide version before an artefact is written."""
    if status not in {"draft", "final"}:
        raise ValueError("status must be 'draft' or 'final'.")
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        actor = conn.execute("SELECT id FROM users WHERE id = ? AND active = 1", (actor_user_id,)).fetchone()
        if not actor:
            raise PermissionError("An active account is required to reserve a report version.")
        case = conn.execute("SELECT id FROM cases WHERE id = ? AND deleted_at IS NULL", (case_id,)).fetchone()
        if not case:
            raise ValueError("Case not found.")
        version_number = conn.execute(
            "SELECT COALESCE(MAX(version_number), 0) + 1 FROM report_versions WHERE case_id = ?", (case_id,)
        ).fetchone()[0]
        token = f"case-{case_id}-v{version_number:04d}-{status}-{uuid.uuid4().hex}"
        cursor = conn.execute(
            """INSERT INTO report_versions
               (case_id, version_number, status, review_status, reservation_status, reservation_token,
                reserved_at, reserved_by_user_id, created_by_user_id)
               VALUES (?, ?, ?, 'draft', 'reserved', ?, CURRENT_TIMESTAMP, ?, ?)""",
            (case_id, version_number, status, token, actor_user_id, actor_user_id),
        )
        conn.commit()
        result = {
            "reservation_id": cursor.lastrowid,
            "version_number": version_number,
            "status": status,
            "storage_safe_token": token,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    log_audit_event(actor_user_id, "report.version_reserved", "report_version", result["reservation_id"], result)
    return result


def finalize_report_version_reservation(
    reservation_id: int,
    *,
    actor_user_id: int,
    content_hash: str,
    storage_reference: str,
    case_start_date: str | None = None,
    approval_data: dict | None = None,
) -> dict:
    """Finalize a reservation once its unique artefact has been durably written."""
    if not content_hash or not storage_reference:
        raise ValueError("content_hash and storage_reference are required.")
    conn = get_connection()
    try:
        report = conn.execute(
            "SELECT * FROM report_versions WHERE id = ? AND reservation_status = 'reserved'", (reservation_id,)
        ).fetchone()
        if not report:
            raise ValueError("Active report-version reservation not found.")
        if report["reserved_by_user_id"] != actor_user_id:
            raise PermissionError("Only the reserving account may finalize this report version.")
        review_status, approval_json, approved_at, approved_by = "draft", None, None, None
        reviewer_id = None
        if report["status"] == "final":
            if not approval_data:
                raise ValueError("approval_data is required for a final report.")
            reviewer = conn.execute(
                """SELECT id FROM users WHERE id = ? AND active = 1
                   AND role IN ('administrator', 'manager')""",
                (actor_user_id,),
            ).fetchone()
            if not reviewer:
                raise PermissionError("Final reports require an active administrator or manager.")
            from reporting.versioning import approval_signoff
            signoff = approval_signoff(approval_data)
            review_status, reviewer_id = "approved", actor_user_id
            approval_json = json.dumps(approval_data, sort_keys=True, default=str)
            approved_at, approved_by = signoff["approved_at"], signoff["approved_by"]
        conn.execute(
            """UPDATE report_versions SET content_hash = ?, storage_reference = ?, case_start_date = ?,
               approval_data_json = ?, approved_at = ?, approved_by = ?, review_status = ?,
               reviewed_at = CASE WHEN ? = 'approved' THEN CURRENT_TIMESTAMP ELSE NULL END,
               reviewed_by_user_id = ?, integrity_verified_at = CURRENT_TIMESTAMP,
               reservation_status = 'finalized'
               WHERE id = ? AND reservation_status = 'reserved'""",
            (content_hash, storage_reference, case_start_date, approval_json, approved_at, approved_by,
             review_status, review_status, reviewer_id, reservation_id),
        )
        conn.commit()
        result = dict(conn.execute("SELECT * FROM report_versions WHERE id = ?", (reservation_id,)).fetchone())
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    log_audit_event(actor_user_id, "report.version_finalized", "report_version", reservation_id, {"status": result["status"]})
    return result


def abandon_report_version_reservation(reservation_id: int, *, actor_user_id: int) -> None:
    """Abandon a reservation permanently; its version remains consumed."""
    conn = get_connection()
    try:
        reservation = conn.execute(
            "SELECT reserved_by_user_id FROM report_versions WHERE id = ? AND reservation_status = 'reserved'",
            (reservation_id,),
        ).fetchone()
        if not reservation:
            raise ValueError("Active report-version reservation not found.")
        if reservation["reserved_by_user_id"] != actor_user_id:
            raise PermissionError("Only the reserving account may abandon this report version.")
        conn.execute(
            "UPDATE report_versions SET reservation_status = 'abandoned' WHERE id = ?",
            (reservation_id,),
        )
        conn.commit()
    finally:
        conn.close()
    log_audit_event(actor_user_id, "report.version_abandoned", "report_version", reservation_id)


def submit_report_version(report_version_id: int, *, actor_user_id: int) -> dict:
    """Mark a finalized draft as submitted for manager review."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """UPDATE report_versions
               SET review_status = 'submitted',
                   assigned_manager_user_id = NULL,
                   response_required_by_user_id = NULL
               WHERE id = ? AND reservation_status = 'finalized' AND status = 'draft'
               AND review_status IN ('draft', 'rejected')""",
            (report_version_id,),
        )
        if cursor.rowcount != 1:
            raise ValueError("Only finalized draft or rejected versions can be submitted.")
        conn.commit()
        result = dict(conn.execute("SELECT * FROM report_versions WHERE id = ?", (report_version_id,)).fetchone())
    finally:
        conn.close()
    log_audit_event(actor_user_id, "report.submitted", "report_version", report_version_id)
    return result


def get_submitted_report_versions() -> list[dict]:
    """Return finalized submitted drafts with the case and investigator context needed for review queues."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT r.*, c.case_ref, c.case_name, c.lead_investigator_id,
                      i.name AS investigator_name
               FROM report_versions r
               JOIN cases c ON c.id = r.case_id
               LEFT JOIN investigators i ON i.user_id = c.lead_investigator_id
               WHERE r.status = 'draft' AND r.reservation_status = 'finalized'
                 AND r.review_status = 'submitted' AND c.deleted_at IS NULL
               ORDER BY r.created_at, r.version_number"""
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def claim_report_review(report_version_id: int, *, manager_user_id: int) -> dict:
    """Atomically assign an available submitted report to one active manager."""
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        manager = conn.execute(
            """SELECT id FROM users
               WHERE id = ? AND active = 1 AND role IN ('administrator', 'manager')""",
            (manager_user_id,),
        ).fetchone()
        if not manager:
            raise PermissionError("An active manager is required to claim a report review.")
        cursor = conn.execute(
            """UPDATE report_versions
               SET assigned_manager_user_id = ?, response_required_by_user_id = ?
               WHERE id = ? AND status = 'draft' AND reservation_status = 'finalized'
                 AND review_status = 'submitted' AND assigned_manager_user_id IS NULL""",
            (manager_user_id, manager_user_id, report_version_id),
        )
        if cursor.rowcount != 1:
            raise ValueError("This report is no longer available for review.")
        conn.commit()
        result = dict(conn.execute("SELECT * FROM report_versions WHERE id = ?", (report_version_id,)).fetchone())
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    log_audit_event(manager_user_id, "report.review_claimed", "report_version", report_version_id)
    return result


def get_report_review_messages(report_version_id: int) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT m.*, COALESCE(u.display_name, u.username) AS sender_name
               FROM report_review_messages m
               JOIN users u ON u.id = m.sender_user_id
               WHERE m.report_version_id = ?
               ORDER BY m.id""",
            (report_version_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def add_report_review_message(report_version_id: int, *, sender_user_id: int, message: str) -> dict:
    """Record a review message and route the next action to the other assigned participant."""
    message = message.strip()
    if not message:
        raise ValueError("Feedback cannot be empty.")
    conn = get_connection()
    try:
        report = conn.execute(
            """SELECT r.*, c.lead_investigator_id
               FROM report_versions r JOIN cases c ON c.id = r.case_id
               WHERE r.id = ?""",
            (report_version_id,),
        ).fetchone()
        if not report or report["status"] != "draft" or report["reservation_status"] != "finalized" or report["review_status"] != "submitted":
            raise ValueError("Only finalized submitted drafts can receive feedback.")
        manager_id = report["assigned_manager_user_id"]
        investigator_id = report["lead_investigator_id"]
        if sender_user_id == manager_id:
            next_user_id = investigator_id
        elif sender_user_id == investigator_id and manager_id:
            next_user_id = manager_id
        else:
            raise PermissionError("Only the assigned manager or lead investigator may add feedback.")
        cursor = conn.execute(
            """INSERT INTO report_review_messages (report_version_id, sender_user_id, message)
               VALUES (?, ?, ?)""",
            (report_version_id, sender_user_id, message),
        )
        conn.execute(
            "UPDATE report_versions SET response_required_by_user_id = ? WHERE id = ?",
            (next_user_id, report_version_id),
        )
        conn.commit()
        result = dict(conn.execute(
            "SELECT * FROM report_review_messages WHERE id = ?", (cursor.lastrowid,)
        ).fetchone())
    finally:
        conn.close()
    log_audit_event(sender_user_id, "report.feedback_added", "report_version", report_version_id)
    return result


def accept_report_feedback(report_version_id: int, *, investigator_user_id: int) -> dict:
    """Let the lead investigator accept feedback and return the report to draft work."""
    conn = get_connection()
    try:
        report = conn.execute(
            """SELECT r.*, c.lead_investigator_id
               FROM report_versions r JOIN cases c ON c.id = r.case_id
               WHERE r.id = ?""",
            (report_version_id,),
        ).fetchone()
        if not report or report["lead_investigator_id"] != investigator_user_id:
            raise PermissionError("Only the lead investigator may accept report feedback.")
        if report["status"] != "draft" or report["reservation_status"] != "finalized" or report["review_status"] != "submitted":
            raise ValueError("Only finalized submitted drafts can be returned to draft work.")
        if report["response_required_by_user_id"] != investigator_user_id:
            raise ValueError("Feedback must be awaiting the investigator before it can be accepted.")
        conn.execute(
            """UPDATE report_versions
               SET review_status = 'rejected', response_required_by_user_id = NULL,
                   rejection_reason = 'Feedback accepted by investigator.'
               WHERE id = ?""",
            (report_version_id,),
        )
        conn.commit()
        result = dict(conn.execute("SELECT * FROM report_versions WHERE id = ?", (report_version_id,)).fetchone())
    finally:
        conn.close()
    log_audit_event(investigator_user_id, "report.feedback_accepted", "report_version", report_version_id)
    return result


def get_report_versions(case_id: int) -> list[dict]:
    conn = get_connection()
    try:
        return [dict(row) for row in conn.execute(
            """SELECT * FROM report_versions WHERE case_id = ?
               ORDER BY version_number DESC, CASE status WHEN 'final' THEN 0 ELSE 1 END""",
            (case_id,),
        )]
    finally:
        conn.close()


def get_case_report_versions(case_id: int) -> list[dict]:
    """Compatibility alias for case-scoped report version consumers."""
    return get_report_versions(case_id)


def review_report_version(
    report_version_id: int,
    decision: str,
    *,
    reviewer_user_id: int,
    rejection_reason: str | None = None,
    reviewer_notes: str | None = None,
) -> dict:
    """Approve or reject a draft/submitted report after caller-side password verification."""
    if decision not in {"approve", "reject"}:
        raise ValueError("decision must be 'approve' or 'reject'.")
    if decision == "reject" and not (rejection_reason or "").strip():
        raise ValueError("A rejection reason is required.")
    conn = get_connection()
    try:
        reviewer = conn.execute(
            """SELECT id FROM users WHERE id = ? AND active = 1
               AND role IN ('administrator', 'manager')""",
            (reviewer_user_id,),
        ).fetchone()
        if not reviewer:
            raise PermissionError("An active administrator or manager must review reports.")
        report = conn.execute(
            """SELECT review_status, reservation_status, assigned_manager_user_id
               FROM report_versions WHERE id = ?""",
            (report_version_id,)
        ).fetchone()
        if not report:
            raise ValueError("Report version not found.")
        if report["reservation_status"] != "finalized" or report["review_status"] != "submitted":
            raise ValueError("Only finalized submitted report versions may be reviewed.")
        if report["assigned_manager_user_id"] != reviewer_user_id:
            raise PermissionError("Only the assigned manager may approve this report.")
        review_status = "approved" if decision == "approve" else "rejected"
        conn.execute(
            """UPDATE report_versions
               SET review_status = ?, reviewed_at = CURRENT_TIMESTAMP, reviewed_by_user_id = ?,
                   rejection_reason = ?, reviewer_notes = ?, response_required_by_user_id = NULL
               WHERE id = ?""",
            (review_status, reviewer_user_id,
             None if decision == "approve" else rejection_reason.strip(),
             (reviewer_notes or "").strip() or None, report_version_id),
        )
        conn.commit()
        result = conn.execute("SELECT * FROM report_versions WHERE id = ?", (report_version_id,)).fetchone()
    finally:
        conn.close()
    log_audit_event(
        reviewer_user_id, f"report.review_{review_status}", "report_version", report_version_id,
        {"decision": decision, "rejection_reason": rejection_reason if decision == "reject" else None},
    )
    return dict(result)


def upsert_annual_management_metric(metric_year: int, metric_name: str, metric_value: float, *,
                                    actor_user_id: int | None = None, dimensions: dict | None = None) -> None:
    dimensions_json = json.dumps(dimensions or {}, sort_keys=True)
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO annual_management_metrics
               (metric_year, metric_name, metric_value, dimensions_json, calculated_by_user_id)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(metric_year, metric_name, dimensions_json) DO UPDATE SET
               metric_value = excluded.metric_value, calculated_at = CURRENT_TIMESTAMP,
               calculated_by_user_id = excluded.calculated_by_user_id""",
            (metric_year, metric_name, metric_value, dimensions_json, actor_user_id),
        )
        conn.commit()
    finally:
        conn.close()