import streamlit as st
from database.db import add_user
from utils.auth import ph

def show_setup():
    st.title("Osint First-Time Setup")
    st.write("Welcome to Osint Report Engine. Since there are no users in the system, you must create the initial Administrator account.")
    
    with st.form("setup_form"):
        username = st.text_input("Administrator Username")
        password = st.text_input("Passphrase", type="password")
        password_confirm = st.text_input("Confirm Passphrase", type="password")
        
        if st.form_submit_button("Create Administrator"):
            if password != password_confirm:
                st.error("Passphrases do not match.")
            elif len(password) < 12:
                st.error("Passphrase must be at least 12 characters.")
            else:
                try:
                    hash_pw = ph.hash(password)
                    add_user(username, hash_pw)
                    st.success("Administrator account created! Please log in.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
                except RuntimeError as e:
                    st.error("Could not create the administrator account.")
                    st.caption(str(e))
