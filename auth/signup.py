import streamlit as st
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "modules", "module_24_prescription_audit", "frontend"))
import api_client


def signup_page():
    st.title("🏥 Create Account")

    name = st.text_input("Full Name")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    confirm = st.text_input("Confirm Password", type="password")
    role = st.selectbox("Role", ["doctor", "hospital_staff"], format_func=lambda r: r.replace("_", " ").title())

    if st.button("Create Account", use_container_width=True):
        if not name or not email or not password:
            st.error("All fields are required.")
            return
        if password != confirm:
            st.error("Passwords do not match.")
            return

        with st.spinner("Creating account..."):
            data, status = api_client.register(name, email, password, role)

        if status in (200, 201):
            st.success("Account created successfully! Please log in.")
            st.session_state.page = "login"
            st.rerun()
        else:
            msg = data.get("message") or data.get("error", "Registration failed")
            st.error(f"Error: {msg}")

    st.markdown("---")
    st.markdown("Already have an account?")
    if st.button("Login"):
        st.session_state.page = "login"
        st.rerun()
