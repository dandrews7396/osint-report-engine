from pathlib import Path

import streamlit as st
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from database import operations as db
from database.db import init_db
import secrets
import hmac
import hashlib
import time
from database.db import get_user

# Server-side token lifetime; kept in sync with the cookie max_age in login.py.
# Because the expiry is part of the signed payload, a leaked token stops working
# after this window instead of being valid forever.
TOKEN_TTL_SECONDS = 6 * 3600

ph = PasswordHasher()
VALID_ROLES = frozenset({"administrator", "manager", "investigator"})


def clear_authenticated_session() -> None:
    st.session_state.logged_in = False
    st.session_state.pop('username', None)
    st.session_state.pop('is_admin', None)
    st.session_state.pop('role', None)


def hydrate_authenticated_session(username: str) -> bool:
    user = get_user(username)
    if not user or not bool(user.get("active", True)):
        clear_authenticated_session()
        return False

    st.session_state.logged_in = True
    st.session_state.username = user['username']
    st.session_state.role = user.get("role", "administrator" if user.get("is_admin") else "investigator")
    st.session_state.is_admin = st.session_state.role == "administrator"
    return True


def get_current_user():
    username = st.session_state.get('username')
    if not username:
        return None

    user = get_user(username)
    if not user or not bool(user.get("active", True)):
        clear_authenticated_session()
        return None

    st.session_state.role = user.get("role", "administrator" if user.get("is_admin") else "investigator")
    st.session_state.is_admin = st.session_state.role == "administrator"
    return user


def current_user_is_admin() -> bool:
    user = get_current_user()
    return bool(user and user.get("role", "administrator" if user.get("is_admin") else "") == "administrator")


def user_has_role(user: dict | None, *roles: str) -> bool:
    """Return whether an active user has any requested role."""
    if not user or not bool(user.get("active", True)):
        return False
    if not set(roles).issubset(VALID_ROLES):
        raise ValueError("Unknown role requested.")
    role = user.get("role", "administrator" if user.get("is_admin") else "investigator")
    return role in roles


def current_user_has_role(*roles: str) -> bool:
    return user_has_role(get_current_user(), *roles)


def require_role_page_auth(*roles: str):
    require_page_auth()
    user = get_current_user()
    if not user_has_role(user, *roles):
        st.error("You do not have permission to access this page.")
        st.stop()
    return user


def validate_password_confirmation(password: str, confirmation: str) -> str | None:
    """Validate a password entry pair without exposing either value."""
    if not password:
        return "Password is required."
    if password != confirmation:
        return "Password confirmation does not match."
    return None


def password_confirmation_matches(password: str, confirmation: str) -> bool:
    return validate_password_confirmation(password, confirmation) is None


def verify_current_password(user: dict, password: str) -> bool:
    """Verify a re-authentication password without exposing verification failures."""
    if not user or not password:
        return False
    try:
        return ph.verify(user["password_hash"], password)
    except (KeyError, VerifyMismatchError):
        return False

def get_cookie_controller():
    if 'cookie_controller' not in st.session_state:
        from streamlit_cookies_controller import CookieController
        st.session_state.cookie_controller = CookieController()
    return st.session_state.cookie_controller

def get_hmac_secret():
    settings = db.get_settings()
    secret = settings.get('session_secret')
    if not secret:
        secret = secrets.token_hex(32)
        db.update_setting('session_secret', secret)
    return secret

def sign_token(username: str) -> str:
    secret = get_hmac_secret().encode()
    expiry = str(int(time.time()) + TOKEN_TTL_SECONDS)
    payload = f"{username}:{expiry}"
    mac = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{mac}"

def verify_token(token: str) -> str:
    # Expected format: username:expiry:mac  (username may itself contain ':')
    if not token or token.count(":") < 2:
        return None
    try:
        payload, mac = token.rsplit(":", 1)
        username, expiry = payload.rsplit(":", 1)
        expected_mac = hmac.new(get_hmac_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mac, expected_mac):
            return None
        if int(expiry) < int(time.time()):
            return None  # token expired
        return username
    except Exception:
        return None

def require_page_auth() -> bool:
    init_db()

    if st.session_state.get('logged_in') and st.session_state.get('username'):
        if not get_current_user():
            st.warning("Please log in to access this page.")
            st.stop()
        return True

    auth_token = get_cookie_controller().get('kairos_auth_token')
    if auth_token:
        verified_username = verify_token(auth_token)
        if verified_username:
            if hydrate_authenticated_session(verified_username):
                return True

    clear_authenticated_session()
    st.warning("Please log in to access this page.")
    st.stop()
    return False


def require_admin_page_auth():
    require_page_auth()
    user = get_current_user()
    if not user or not bool(user.get('is_admin')):
        st.session_state.nav = "Dashboard"
        st.switch_page(Path("streamlit_pages/dashboard.py"))
        st.stop()
    return user
