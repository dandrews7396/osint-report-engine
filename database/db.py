import sqlite3
import os
import time
import streamlit as st

DB_PATH = 'data/kairos_osint.db'

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(cursor, table_name: str, column_name: str, column_definition: str):
    cursor.execute(f"PRAGMA table_info({table_name})")
    existing_columns = {row[1] for row in cursor.fetchall()}
    if column_name not in existing_columns:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")

def _clear_read_caches():
    st.cache_data.clear()

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 1. Users Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                mfa_secret TEXT,
                mfa_enabled BOOLEAN DEFAULT 0,
                failed_login_attempts INTEGER DEFAULT 0,
                lockout_until REAL DEFAULT 0
            )
        ''')

        # 2. Settings Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('firm_name', 'Corporate Intelligence Advisory Group')")
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('ico_registration_no', 'ZB123456')")
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('gdpr_lawful_basis', 'Article 6(1)(f) UK GDPR — Legitimate Interest for corporate risk mitigation and legal disputes.')")
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('executive_summary_template', 'This Enhanced Due Diligence report provides an objective risk assessment based on open-source intelligence...')")

        # 3. Investigators Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS investigators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                title TEXT,
                credentials TEXT,
                bio TEXT
            )
        ''')

        # 4. Clients Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                client_type TEXT DEFAULT 'Law Firm',
                contact_email TEXT,
                description TEXT,
                deleted_at TEXT
            )
        ''')

        # 5. Cases Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_ref TEXT NOT NULL UNIQUE,
                case_name TEXT NOT NULL,
                case_type TEXT DEFAULT 'Enhanced Due Diligence',
                client_id INTEGER NOT NULL,
                start_date TEXT,
                end_date TEXT,
                report_date TEXT,
                lead_investigator TEXT,
                investigator_description TEXT,
                target_scope TEXT,
                legitimate_interest_assessment TEXT,
                executive_assessment TEXT,
                key_findings_summary TEXT,
                tools_and_sources_used TEXT,
                deleted_at TEXT,
                FOREIGN KEY (client_id) REFERENCES clients (id) ON DELETE CASCADE
            )
        ''')

        # 6. Case Subjects Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS case_subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                subject_type TEXT NOT NULL,
                relationship_to_case TEXT NOT NULL,
                display_name TEXT NOT NULL,
                subject_data_json TEXT NOT NULL DEFAULT '{}',
                notes TEXT,
                deleted_at TEXT,
                FOREIGN KEY (case_id) REFERENCES cases (id) ON DELETE CASCADE
            )
        ''')

        # 7. OSINT Risk Library Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS risk_library (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                title TEXT NOT NULL,
                default_risk_level TEXT NOT NULL,
                description TEXT,
                investigative_guidance TEXT,
                source_confidence TEXT DEFAULT 'High Confidence',
                refs TEXT
            )
        ''')

        # 8. Case Findings Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS case_findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                subject_id INTEGER,
                domain_category TEXT NOT NULL,
                title TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                source_confidence TEXT DEFAULT 'High Confidence',
                summary TEXT,
                detailed_findings TEXT,
                evidence_url TEXT,
                evidence_hash_sha256 TEXT,
                source_citation TEXT,
                deleted_at TEXT,
                FOREIGN KEY (case_id) REFERENCES cases (id) ON DELETE CASCADE
            )
        ''')

        _ensure_column(cursor, "case_findings", "subject_id", "INTEGER")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_case_subjects_case_id ON case_subjects (case_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_case_findings_subject_id ON case_findings (subject_id)")

        # 9. Login Attempts Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS login_attempts (
                username TEXT PRIMARY KEY,
                failed_attempts INTEGER DEFAULT 0,
                last_attempt REAL
            )
        ''')

        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        raise RuntimeError(f"Database initialization failed: {e}")
    finally:
        conn.close()

# User Management Functions with Defensive Error Handling
@st.cache_data(show_spinner=False)
def get_user_count():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        return cursor.fetchone()[0]
    except sqlite3.Error as e:
        print(f"[DB ERROR] get_user_count: {e}")
        return 0
    finally:
        conn.close()

def add_user(username, password_hash):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password_hash))
        conn.commit()
        _clear_read_caches()
    except sqlite3.IntegrityError:
        conn.rollback()
        raise ValueError("Username already exists")
    except sqlite3.Error as e:
        conn.rollback()
        raise RuntimeError(f"Database error while adding user: {e}")
    finally:
        conn.close()

@st.cache_data(show_spinner=False)
def get_user(username):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except sqlite3.Error as e:
        print(f"[DB ERROR] get_user: {e}")
        return None
    finally:
        conn.close()

def update_user_mfa(username, mfa_secret, mfa_enabled):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET mfa_secret = ?, mfa_enabled = ? WHERE username = ?", (mfa_secret, mfa_enabled, username))
        conn.commit()
        _clear_read_caches()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] update_user_mfa: {e}")
    finally:
        conn.close()

def update_user_password(username, new_password_hash):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET password_hash = ? WHERE username = ?", (new_password_hash, username))
        conn.commit()
        _clear_read_caches()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] update_user_password: {e}")
    finally:
        conn.close()

def record_failed_login(username):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO login_attempts (username, failed_attempts, last_attempt) 
            VALUES (?, 1, ?) 
            ON CONFLICT(username) DO UPDATE SET 
                failed_attempts = failed_attempts + 1, 
                last_attempt = ?
        ''', (username, time.time(), time.time()))
        conn.commit()
        _clear_read_caches()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] record_failed_login: {e}")
    finally:
        conn.close()

def reset_failed_logins(username):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM login_attempts WHERE username = ?", (username,))
        conn.commit()
        _clear_read_caches()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[DB ERROR] reset_failed_logins: {e}")
    finally:
        conn.close()

@st.cache_data(show_spinner=False)
def get_failed_logins(username):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT failed_attempts FROM login_attempts WHERE username = ?", (username,))
        row = cursor.fetchone()
        return row['failed_attempts'] if row else 0
    except sqlite3.Error as e:
        print(f"[DB ERROR] get_failed_logins: {e}")
        return 0
    finally:
        conn.close()

if __name__ == '__main__':
    init_db()