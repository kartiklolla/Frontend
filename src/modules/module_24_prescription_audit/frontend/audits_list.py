"""
Audits List — paginated list of all audits for the logged-in doctor or all doctors (admin)
"""

import streamlit as st
import api_client


def audits_list_page():
    st.markdown("## Audit Records")

    # ── Filters ───────────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        status_filter = st.selectbox("Filter by Status", ["All", "pass", "warning", "fail"])
    with col2:
        page_num = st.number_input("Page", min_value=1, step=1, value=1)
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        st.button("Refresh")

    doctor_id = None
    if st.session_state.get("backend_role") == "doctor":
        doctor_id = st.session_state.get("user_id")

    with st.spinner("Loading audits..."):
        data, status = api_client.list_audits(
            doctor_id=doctor_id,
            status=None if status_filter == "All" else status_filter,
            page=int(page_num),
        )

    if status != 200:
        st.error(data.get("message", "Failed to load audits."))
        return

    audits = data.get("audits", data.get("data", []))
    total = data.get("total", len(audits))
    st.caption(f"Showing {len(audits)} of {total} audits")

    if not audits:
        st.info("No audit records found.")
        return

    sev_icon = {"pass": "✅", "warning": "⚠️", "fail": "❌"}

    for aud in audits:
        aud_id = str(aud.get("_id") or aud.get("id", ""))
        score = aud.get("overall_score", 0)
        aud_status = aud.get("status", "unknown")
        icon = sev_icon.get(aud_status, "📋")

        with st.container():
            ac1, ac2, ac3 = st.columns([3, 3, 1])
            with ac1:
                st.markdown(f"{icon} **Score: {score:.1f}/100** — {aud_status.upper()}")
                aud_date = (aud.get("audit_date") or aud.get("created_at", ""))[:10]
                st.caption(f"Date: {aud_date}")
            with ac2:
                comp = aud.get("completeness_score", 0)
                safe = aud.get("safety_score", 0)
                appr = aud.get("appropriateness_score", 0)
                st.caption(f"Completeness: {comp:.0f} | Safety: {safe:.0f} | Appropriateness: {appr:.0f}")
                st.caption(f"Violations: {aud.get('violations_count', '?')}")
            with ac3:
                if st.button("View", key=f"aud_list_{aud_id}"):
                    st.session_state.pa_audit_id = aud_id
                    st.session_state.pa_audit_prev_view = "audits"
                    st.session_state.pa_view = "audit_detail"
                    st.rerun()
            st.divider()
