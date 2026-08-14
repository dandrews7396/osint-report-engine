import sqlite3
import streamlit as st
from database.db import get_connection
from database.subjects import (
    decode_subject_data,
    encode_subject_data,
    subject_display_name,
    subject_summary_lines,
)

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
                c.lead_investigator AS investigator_name, c.investigator_description, c.target_scope,
                c.legitimate_interest_assessment AS legitimate_interest, c.executive_assessment AS executive_summary,
                c.key_findings_summary AS key_findings_summary, c.covert_persona_reference AS covert_persona_reference,
                c.tools_and_sources_used AS tools_used, c.deleted_at, cl.name as client_name
            FROM cases c 
            JOIN clients cl ON c.client_id = cl.id
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
    lead_investigator: str = '',
    investigator_description: str = '',
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
                lead_investigator, investigator_description, target_scope,
                legitimate_interest_assessment,
                executive_assessment, key_findings_summary, covert_persona_reference, tools_and_sources_used
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            case_ref, case_name, client_id, case_type, start_date, end_date, report_date,
            lead_investigator, investigator_description, target_scope,
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
    lead_investigator: str,
    investigator_description: str,
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
                lead_investigator = ?, investigator_description = ?, target_scope = ?, 
                legitimate_interest_assessment = ?, 
                executive_assessment = ?, key_findings_summary = ?, covert_persona_reference = ?, tools_and_sources_used = ?
            WHERE id = ?
        """, (
            case_ref, case_name, case_type, start_date, end_date, report_date,
            lead_investigator, investigator_description, target_scope,
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
            ORDER BY s.id DESC
        """, (case_id,))
        return [_map_case_subject_row(dict(row)) for row in cursor.fetchall()]
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
        cursor.execute("SELECT * FROM risk_library")
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
    refs: str = ''
):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO risk_library (category, title, default_risk_level, description, investigative_guidance, source_confidence, refs)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (category, title, default_risk_level, description, investigative_guidance, source_confidence, refs))
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
    refs: str
):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE risk_library 
            SET category = ?, title = ?, default_risk_level = ?, description = ?, investigative_guidance = ?, source_confidence = ?, refs = ?
            WHERE id = ?
        """, (category, title, default_risk_level, description, investigative_guidance, source_confidence, refs, risk_id))
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

# --- Case Findings (Formerly Project Findings) ---
def _map_case_finding_row(r: dict, include_details: bool = True) -> dict:
    mapped = {
        'id': r.get('id'),
        'case_id': r.get('case_id'),
        'subject_id': r.get('subject_id'),
        'subject_name': r.get('subject_name'),
        'category': r.get('domain_category'),
        'title': r.get('title'),
        'risk_level': r.get('risk_level'),
        'confidence_level': r.get('source_confidence'),
        'summary': r.get('summary'),
        'evidence_url': r.get('evidence_url'),
        'evidence_hash_sha256': r.get('evidence_hash_sha256'),
        'source_citation': r.get('source_citation'),
        'refs': r.get('source_citation') or (r.get('evidence_url') or ''),
        'deleted_at': r.get('deleted_at')
    }
    if include_details:
        mapped['description'] = r.get('detailed_findings') or r.get('summary') or ''
        mapped['evidence'] = r.get('evidence_url') or r.get('source_citation') or ''
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
                   f.summary, f.evidence_url, f.evidence_hash_sha256, f.source_citation, f.deleted_at
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
    evidence_url: str = '',
    evidence_hash_sha256: str = '',
    source_citation: str = '',
    subject_id: int | None = None,
):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO case_findings (
                case_id, subject_id, domain_category, title, risk_level, source_confidence, 
                summary, detailed_findings, evidence_url, evidence_hash_sha256, source_citation
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (case_id, subject_id, domain_category, title, risk_level, source_confidence, summary, detailed_findings, evidence_url, evidence_hash_sha256, source_citation))
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
    evidence_url: str,
    evidence_hash_sha256: str,
    source_citation: str,
    subject_id: int | None = None,
):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE case_findings 
            SET subject_id = ?, domain_category = ?, title = ?, risk_level = ?, source_confidence = ?, 
                summary = ?, detailed_findings = ?, evidence_url = ?, evidence_hash_sha256 = ?, source_citation = ?
            WHERE id = ?
        """, (subject_id, domain_category, title, risk_level, source_confidence, summary, detailed_findings, evidence_url, evidence_hash_sha256, source_citation, finding_id))
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

# --- Investigators (Formerly Testers) ---
@st.cache_data(show_spinner=False)
def get_investigators() -> list[dict]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM investigators")
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"[DB ERROR] get_investigators: {e}")
        return []
    finally:
        conn.close()

def add_investigator(name: str, title: str, credentials: str, bio: str):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO investigators (name, title, credentials, bio) VALUES (?, ?, ?, ?)", (name, title, credentials, bio))
        conn.commit()
        _clear_read_caches()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] add_investigator: {e}")
    finally:
        conn.close()

def delete_investigator(investigator_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM investigators WHERE id = ?", (investigator_id,))
        conn.commit()
        _clear_read_caches()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] delete_investigator: {e}")
    finally:
        conn.close()

def update_investigator(investigator_id: int, name: str, title: str, credentials: str, bio: str):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE investigators SET name = ?, title = ?, credentials = ?, bio = ? WHERE id = ?", (name, title, credentials, bio, investigator_id))
        conn.commit()
        _clear_read_caches()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] update_investigator: {e}")
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