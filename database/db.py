"""SQLite schema and account primitives for Kairos."""

import os
import re
import sqlite3
import time

import streamlit as st

DB_PATH = "data/kairos_osint.db"
ROLES = frozenset({"administrator", "manager", "investigator"})


def normalize_username(username: str) -> str:
    return (username or "").strip().lower()


def validate_username(username: str) -> str | None:
    username = normalize_username(username)
    if not username:
        return "Username is required."
    if not re.fullmatch(r"[a-z]{3,12}", username):
        return "Username must be 3-12 letters long and contain letters only."
    return None


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _clear_read_caches():
    st.cache_data.clear()


def init_db():
    """Create the complete fresh-install schema.

    This intentionally contains no schema migration logic. Existing databases
    must be migrated separately before this application version is deployed.
    """
    schema = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL COLLATE NOCASE UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'investigator'
            CHECK (role IN ('administrator', 'manager', 'investigator')),
        active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
        display_name TEXT,
        title TEXT,
        is_admin INTEGER NOT NULL DEFAULT 0 CHECK (is_admin IN (0, 1)),
        mfa_secret TEXT,
        mfa_enabled INTEGER NOT NULL DEFAULT 0 CHECK (mfa_enabled IN (0, 1)),
        failed_login_attempts INTEGER NOT NULL DEFAULT 0,
        lockout_until REAL NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS investigator_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        completion_status TEXT NOT NULL DEFAULT 'incomplete'
            CHECK (completion_status IN ('incomplete', 'complete')),
        credentials TEXT,
        professional_bio TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS investigators (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        name TEXT NOT NULL,
        title TEXT,
        credentials TEXT,
        bio TEXT,
        available INTEGER NOT NULL DEFAULT 0 CHECK (available IN (0, 1)),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
        client_type TEXT DEFAULT 'Law Firm', contact_email TEXT, description TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, deleted_at TEXT
    );
    CREATE TABLE IF NOT EXISTS cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT, case_ref TEXT NOT NULL UNIQUE,
        case_name TEXT NOT NULL, case_type TEXT DEFAULT 'Enhanced Due Diligence',
        client_id INTEGER NOT NULL, lifecycle_status TEXT NOT NULL DEFAULT 'preparation'
            CHECK (lifecycle_status IN ('preparation', 'in_progress', 'submitted', 'rejected', 'completed')),
        lead_investigator_id INTEGER,
        start_date TEXT, end_date TEXT,
        report_date TEXT, target_scope TEXT, legitimate_interest_assessment TEXT,
        executive_assessment TEXT, key_findings_summary TEXT, covert_persona_reference TEXT,
        tools_and_sources_used TEXT, investigation_started_at TEXT,
        investigation_started_by_user_id INTEGER, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        created_by_user_id INTEGER, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_by_user_id INTEGER, deleted_at TEXT,
        FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
        FOREIGN KEY (lead_investigator_id) REFERENCES users(id) ON DELETE SET NULL,
        FOREIGN KEY (investigation_started_by_user_id) REFERENCES users(id) ON DELETE SET NULL,
        FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL,
        FOREIGN KEY (updated_by_user_id) REFERENCES users(id) ON DELETE SET NULL
    );
    CREATE TABLE IF NOT EXISTS case_persona_references (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL,
        persona_reference TEXT NOT NULL COLLATE NOCASE,
        allocated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (case_id, persona_reference),
        FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS case_subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT, case_id INTEGER NOT NULL,
        subject_type TEXT NOT NULL, relationship_to_case TEXT NOT NULL,
        display_name TEXT NOT NULL, subject_data_json TEXT NOT NULL DEFAULT '{}', notes TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, created_by_user_id INTEGER,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_by_user_id INTEGER,
        deleted_at TEXT, FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE,
        FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL,
        FOREIGN KEY (updated_by_user_id) REFERENCES users(id) ON DELETE SET NULL
    );
    CREATE TABLE IF NOT EXISTS case_findings (
        id INTEGER PRIMARY KEY AUTOINCREMENT, case_id INTEGER NOT NULL, subject_id INTEGER,
        domain_category TEXT NOT NULL, title TEXT NOT NULL, risk_level TEXT NOT NULL,
        source_confidence TEXT DEFAULT 'High Confidence', summary TEXT, detailed_findings TEXT,
        source TEXT, category_data_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, created_by_user_id INTEGER,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_by_user_id INTEGER,
        deleted_at TEXT, FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE,
        FOREIGN KEY (subject_id) REFERENCES case_subjects(id) ON DELETE SET NULL,
        FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL,
        FOREIGN KEY (updated_by_user_id) REFERENCES users(id) ON DELETE SET NULL
    );
    CREATE TABLE IF NOT EXISTS risk_library (
        id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, title TEXT NOT NULL,
        default_risk_level TEXT NOT NULL, description TEXT, investigative_guidance TEXT,
        source_confidence TEXT DEFAULT 'High Confidence', refs TEXT,
        provenance TEXT, retired_at TEXT, retired_by_user_id INTEGER,
        revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, created_by_user_id INTEGER,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_by_user_id INTEGER,
        FOREIGN KEY (retired_by_user_id) REFERENCES users(id) ON DELETE SET NULL,
        FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL,
        FOREIGN KEY (updated_by_user_id) REFERENCES users(id) ON DELETE SET NULL
    );
    CREATE TABLE IF NOT EXISTS audit_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        actor_user_id INTEGER, event_type TEXT NOT NULL, entity_type TEXT NOT NULL,
        entity_id TEXT, details_json TEXT NOT NULL DEFAULT '{}',
        FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE SET NULL
    );
    CREATE TABLE IF NOT EXISTS report_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, case_id INTEGER NOT NULL,
        version_number INTEGER NOT NULL CHECK (version_number > 0),
        status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'final')),
        content_hash TEXT, storage_reference TEXT, case_start_date TEXT,
        approval_data_json TEXT, approved_at TEXT, approved_by TEXT,
        review_status TEXT NOT NULL DEFAULT 'draft'
            CHECK (review_status IN ('draft', 'submitted', 'approved', 'rejected')),
        reviewed_at TEXT, reviewed_by_user_id INTEGER, rejection_reason TEXT, reviewer_notes TEXT,
        reservation_status TEXT NOT NULL DEFAULT 'finalized'
            CHECK (reservation_status IN ('reserved', 'finalized', 'abandoned')),
        reservation_token TEXT UNIQUE, reserved_at TEXT, reserved_by_user_id INTEGER,
        assigned_manager_user_id INTEGER, response_required_by_user_id INTEGER,
        integrity_verified_at TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        created_by_user_id INTEGER, UNIQUE(case_id, version_number),
        FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE,
        FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL,
        FOREIGN KEY (reviewed_by_user_id) REFERENCES users(id) ON DELETE SET NULL,
        FOREIGN KEY (reserved_by_user_id) REFERENCES users(id) ON DELETE SET NULL,
        FOREIGN KEY (assigned_manager_user_id) REFERENCES users(id) ON DELETE SET NULL,
        FOREIGN KEY (response_required_by_user_id) REFERENCES users(id) ON DELETE SET NULL
    );
    CREATE TABLE IF NOT EXISTS report_review_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_version_id INTEGER NOT NULL,
        sender_user_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (report_version_id) REFERENCES report_versions(id) ON DELETE CASCADE,
        FOREIGN KEY (sender_user_id) REFERENCES users(id) ON DELETE RESTRICT
    );
    CREATE TABLE IF NOT EXISTS annual_management_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT, metric_year INTEGER NOT NULL,
        metric_name TEXT NOT NULL, metric_value REAL NOT NULL, dimensions_json TEXT NOT NULL DEFAULT '{}',
        calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, calculated_by_user_id INTEGER,
        UNIQUE(metric_year, metric_name, dimensions_json),
        FOREIGN KEY (calculated_by_user_id) REFERENCES users(id) ON DELETE SET NULL
    );
    CREATE TABLE IF NOT EXISTS management_report_configurations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        manager_user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        configuration_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(manager_user_id, name),
        FOREIGN KEY (manager_user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS login_attempts (
        username TEXT PRIMARY KEY, failed_attempts INTEGER NOT NULL DEFAULT 0, last_attempt REAL
    );
    CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(lifecycle_status);
    CREATE INDEX IF NOT EXISTS idx_case_persona_references_usage
        ON case_persona_references(persona_reference, allocated_at);
    CREATE INDEX IF NOT EXISTS idx_case_subjects_case_id ON case_subjects(case_id);
    CREATE INDEX IF NOT EXISTS idx_case_findings_case_id ON case_findings(case_id);
    CREATE INDEX IF NOT EXISTS idx_audit_events_entity ON audit_events(entity_type, entity_id);
    CREATE INDEX IF NOT EXISTS idx_report_versions_review_queue
        ON report_versions(review_status, assigned_manager_user_id, response_required_by_user_id);
    CREATE INDEX IF NOT EXISTS idx_report_review_messages_version
        ON report_review_messages(report_version_id, id);
    CREATE INDEX IF NOT EXISTS idx_management_report_configurations_owner
        ON management_report_configurations(manager_user_id, name);
    """
    conn = get_connection()
    try:
        conn.executescript(schema)
        conn.executemany(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            [
                ("firm_name", "Corporate Intelligence Advisory Group"),
                ("ico_registration_no", "ZB123456"),
                ("gdpr_lawful_basis", "Article 6(1)(f) UK GDPR — Legitimate Interest for corporate risk mitigation and legal disputes."),
                ("executive_summary_template", "This Enhanced Due Diligence report provides an objective risk assessment based on open-source intelligence..."),
                ("default_report_include_risk_graphs", "true"),
            ],
        )
        conn.commit()
    except sqlite3.Error as exc:
        conn.rollback()
        raise RuntimeError(f"Database initialization failed: {exc}") from exc
    finally:
        conn.close()


@st.cache_data(show_spinner=False)
def get_user_count():
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def add_user(username, password_hash, *, created_by_username=None, is_admin=False,
             role=None, active=True, display_name=None, title=None):
    username = normalize_username(username)
    error = validate_username(username)
    if error:
        raise ValueError(error)
    role = role or ("administrator" if is_admin else "investigator")
    if role not in ROLES:
        raise ValueError("Invalid role.")
    creator = normalize_username(created_by_username) if created_by_username else None
    conn = get_connection()
    try:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count and not creator:
            raise PermissionError("Only an administrator can create additional users.")
        if count:
            row = conn.execute("SELECT role FROM users WHERE username = ?", (creator,)).fetchone()
            if not row or row["role"] != "administrator":
                raise PermissionError("Only an administrator can create additional users.")
        if not count:
            role, is_admin = "administrator", True
        cursor = conn.execute(
            """INSERT INTO users (username, password_hash, role, active, display_name, title, is_admin)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (username, password_hash, role, int(active), display_name, title, int(role == "administrator" or is_admin)),
        )
        conn.commit()
        _clear_read_caches()
        return cursor.lastrowid
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        raise ValueError("Username already exists") from exc
    finally:
        conn.close()


@st.cache_data(show_spinner=False)
def get_user(username):
    username = normalize_username(username)
    if not username:
        return None
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None


def update_user_mfa(username, mfa_secret, mfa_enabled):
    _update_user(username, "mfa_secret = ?, mfa_enabled = ?", (mfa_secret, int(mfa_enabled)))


def update_user_password(username, new_password_hash):
    _update_user(username, "password_hash = ?", (new_password_hash,))


def synchronize_investigator_directory(conn, user_id):
    """Refresh the purpose-limited investigator directory entry for one account."""
    row = conn.execute(
        """SELECT u.id, u.username, u.role, u.active, u.display_name, u.title,
                  p.completion_status, p.credentials, p.professional_bio
           FROM users u
           LEFT JOIN investigator_profiles p ON p.user_id = u.id
           WHERE u.id = ?""",
        (user_id,),
    ).fetchone()
    if not row or row["role"] != "investigator" or not row["completion_status"]:
        conn.execute("DELETE FROM investigators WHERE user_id = ?", (user_id,))
        return

    conn.execute(
        """INSERT INTO investigators (
               user_id, name, title, credentials, bio, available
           ) VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(user_id) DO UPDATE SET
               name = excluded.name,
               title = excluded.title,
               credentials = excluded.credentials,
               bio = excluded.bio,
               available = excluded.available,
               updated_at = CURRENT_TIMESTAMP""",
        (
            row["id"],
            row["display_name"] or row["username"],
            row["title"],
            row["credentials"],
            row["professional_bio"],
            int(bool(row["active"]) and row["completion_status"] == "complete"),
        ),
    )


def set_user_active(username, active, *, actor_user_id=None):
    normalized_username = normalize_username(username)
    with get_connection() as conn:
        user = conn.execute(
            "SELECT id FROM users WHERE username = ?", (normalized_username,)
        ).fetchone()
        if not user:
            raise ValueError("User not found.")
        conn.execute(
            "UPDATE users SET active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (int(active), user["id"]),
        )
        synchronize_investigator_directory(conn, user["id"])
        conn.execute(
            """INSERT INTO audit_events (actor_user_id, event_type, entity_type, entity_id, details_json)
               VALUES (?, ?, 'user', ?, ?)""",
            (actor_user_id, "account.active_changed", normalized_username, f'{{"active": {int(bool(active))}}}'),
        )
        conn.commit()
    _clear_read_caches()


def update_user_identity(username, display_name, title):
    """Update identity data for an active administrator or manager account."""
    normalized_username = normalize_username(username)
    display_name = (display_name or "").strip()
    title = (title or "").strip()
    if not display_name:
        raise ValueError("Display name is required.")
    with get_connection() as conn:
        user = conn.execute(
            "SELECT role, active FROM users WHERE username = ?", (normalized_username,)
        ).fetchone()
        if not user:
            raise ValueError("User not found.")
        if not user["active"]:
            raise PermissionError("Inactive accounts cannot update identity details.")
        if user["role"] not in {"administrator", "manager"}:
            raise PermissionError("Only administrator and manager accounts have account identity titles.")
        conn.execute(
            """UPDATE users SET display_name = ?, title = ?, updated_at = CURRENT_TIMESTAMP
               WHERE username = ?""",
            (display_name, title or None, normalized_username),
        )
        conn.commit()
    _clear_read_caches()


def _update_user(username, assignments, values):
    with get_connection() as conn:
        conn.execute(f"UPDATE users SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE username = ?",
                     (*values, normalize_username(username)))
        conn.commit()
    _clear_read_caches()


def delete_user(username):
    username = normalize_username(username)
    with get_connection() as conn:
        user = conn.execute("SELECT role FROM users WHERE username = ?", (username,)).fetchone()
        if not user:
            raise ValueError("User not found.")
        if user["role"] == "administrator":
            raise PermissionError("Administrator accounts cannot be deleted.")
        conn.execute("DELETE FROM login_attempts WHERE username = ?", (username,))
        conn.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.commit()
    _clear_read_caches()


def record_failed_login(username):
    username = normalize_username(username)
    if not username:
        return
    with get_connection() as conn:
        conn.execute("""INSERT INTO login_attempts (username, failed_attempts, last_attempt) VALUES (?, 1, ?)
                     ON CONFLICT(username) DO UPDATE SET failed_attempts = failed_attempts + 1, last_attempt = excluded.last_attempt""",
                     (username, time.time()))
        conn.commit()
    _clear_read_caches()


def reset_failed_logins(username):
    with get_connection() as conn:
        conn.execute("DELETE FROM login_attempts WHERE username = ?", (normalize_username(username),))
        conn.commit()
    _clear_read_caches()


@st.cache_data(show_spinner=False)
def get_failed_logins(username):
    with get_connection() as conn:
        row = conn.execute("SELECT failed_attempts FROM login_attempts WHERE username = ?",
                           (normalize_username(username),)).fetchone()
        return row["failed_attempts"] if row else 0


@st.cache_data(show_spinner=False)
def get_users():
    with get_connection() as conn:
        return [dict(row) for row in conn.execute(
            "SELECT id, username, role, active, display_name, title, is_admin, mfa_enabled, created_at, updated_at FROM users ORDER BY username"
        )]
