import streamlit as st
from argon2.exceptions import VerifyMismatchError

from database import operations as operations
from database.db import (
    add_user,
    get_user,
    get_users,
    normalize_username,
    set_user_active,
    update_user_password,
    validate_username,
)
from utils.auth import ph, require_role_page_auth

ROLES = ("administrator", "manager", "investigator")


def _admin_password_is_valid(admin_user: dict, password: str) -> bool:
    try:
        ph.verify(admin_user["password_hash"], password)
    except VerifyMismatchError:
        return False
    return True


def show_admin_users():
    require_role_page_auth("administrator")
    admin_user = get_user(st.session_state.username)
    st.title("Users & Accounts")
    st.caption("Create accounts, reset passwords, manage account activation, and review roles.")

    users = get_users()
    st.subheader("Role Overview")
    st.table(
        [
            {
                "Username": user["username"],
                "Role": user["role"].title(),
                "Status": "Active" if user["active"] else "Inactive",
                "MFA": "Enabled" if user["mfa_enabled"] else "Not enabled",
                "Name": user.get("display_name") or "",
                "Title": user.get("title") or "",
            }
            for user in users
        ],
    )

    with st.expander("Create Account", expanded=False):
        with st.form("create_user_account", clear_on_submit=True):
            username = st.text_input("Username", help="3-12 letters; saved in lowercase.")
            role = st.selectbox("Role", ROLES, index=2)
            password = st.text_input("Initial Passphrase", type="password", autocomplete="new-password")
            confirm_password = st.text_input("Confirm Initial Passphrase", type="password", autocomplete="new-password")
            admin_password = st.text_input("Your Current Password", type="password", autocomplete="current-password")
            if st.form_submit_button("Create Account"):
                normalized_username = normalize_username(username)
                username_error = validate_username(normalized_username)
                if not _admin_password_is_valid(admin_user, admin_password):
                    st.error("Incorrect administrator password.")
                elif username_error:
                    st.error(username_error)
                elif len(password) < 12:
                    st.error("Passphrase must be at least 12 characters.")
                elif password != confirm_password:
                    st.error("Passphrases do not match.")
                else:
                    try:
                        user_id = add_user(
                            normalized_username,
                            ph.hash(password),
                            created_by_username=admin_user["username"],
                            role=role,
                        )
                    except ValueError as error:
                        st.error(str(error))
                    else:
                        operations.log_audit_event(
                            admin_user["id"],
                            "account.created",
                            "user",
                            user_id,
                            {"username": normalized_username, "role": role},
                        )
                        st.success(f"{role.title()} account '{normalized_username}' created.")
                        st.rerun()

    manageable_users = [user for user in users if user["username"] != admin_user["username"]]
    if not manageable_users:
        return

    st.subheader("Account Administration")
    target_username = st.selectbox("Account", [user["username"] for user in manageable_users])
    target = next(user for user in manageable_users if user["username"] == target_username)
    action = st.radio("Action", ("Reset Password", "Change Account Status"), horizontal=True)
    with st.form("manage_user_account"):
        admin_password = st.text_input("Your Current Password", type="password", autocomplete="current-password")
        if action == "Reset Password":
            new_password = st.text_input("New Passphrase", type="password", autocomplete="new-password")
            confirmation = st.text_input("Confirm New Passphrase", type="password", autocomplete="new-password")
            submitted = st.form_submit_button("Reset Password")
            if submitted:
                if not _admin_password_is_valid(admin_user, admin_password):
                    st.error("Incorrect administrator password.")
                elif len(new_password) < 12:
                    st.error("Passphrase must be at least 12 characters.")
                elif new_password != confirmation:
                    st.error("Passphrases do not match.")
                else:
                    update_user_password(target_username, ph.hash(new_password))
                    operations.log_audit_event(
                        admin_user["id"],
                        "account.password_reset",
                        "user",
                        target["id"],
                        {"username": target_username},
                    )
                    st.success(f"Password reset for {target_username}.")
        else:
            desired_active = st.checkbox("Account active", value=bool(target["active"]))
            submitted = st.form_submit_button("Save Account Status")
            if submitted:
                if not _admin_password_is_valid(admin_user, admin_password):
                    st.error("Incorrect administrator password.")
                elif desired_active == bool(target["active"]):
                    st.info("No account status change was requested.")
                else:
                    set_user_active(target_username, desired_active, actor_user_id=admin_user["id"])
                    st.success(f"{target_username} has been {'activated' if desired_active else 'deactivated'}.")
                    st.rerun()
