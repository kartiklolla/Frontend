import streamlit as st
import base64, json, sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "modules", "module_24_prescription_audit", "frontend"))
import api_client

# Map backend role → frontend role for routing
ROLE_MAP = {
    "doctor": "Doctor",
    "admin": "Admin",
    "hospital_staff": "Doctor",  # Staff uses doctor dashboard with limited access
}


def _decode_jwt_user_id(token):
    """Extract user_id from JWT payload without signature verification."""
    try:
        payload_b64 = token.split(".")[1]
        # Restore base64 padding
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload.get("user_id", "")
    except Exception:
        return ""


def login_page():
    st.title("🏥 MediCare Login")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Login", use_container_width=True):
        if not email or not password:
            st.error("Please enter email and password")
            return

        with st.spinner("Authenticating..."):
            # After _unwrap, data is {"token": "...", "role": "...", "name": "..."}
            data, status = api_client.login(email, password)

        if status == 200:
            token = data.get("token", "")
            backend_role = data.get("role", "doctor")
            user_name = data.get("name", email)
            frontend_role = ROLE_MAP.get(backend_role, "Doctor")

            # Decode JWT locally to get user_id (no secret needed, just reading payload)
            user_id = _decode_jwt_user_id(token)

            st.session_state.logged_in = True
            st.session_state.role = frontend_role
            st.session_state.backend_role = backend_role
            st.session_state.token = token
            st.session_state.user_id = user_id
            st.session_state.user_name = user_name
            st.session_state.user_email = email
            st.session_state.page = "dashboard"
            st.rerun()
        else:
            msg = data.get("message") or data.get("error", "Invalid credentials")
            st.error(f"Login failed: {msg}")

    st.markdown("---")
    st.markdown("Don't have an account?")
    if st.button("Sign Up"):
        st.session_state.page = "signup"
        st.rerun()

    with st.expander("Demo credentials"):
        st.code("""Doctor:  priya@hospital.com  / password123
Doctor:  rahul@hospital.com  / password123
Admin:   admin@hospital.com  / password123
Staff:   anjali@hospital.com / password123""")
