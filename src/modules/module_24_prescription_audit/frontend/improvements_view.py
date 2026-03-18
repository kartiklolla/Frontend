"""
Improvements View — list and update improvement suggestion statuses
"""

import streamlit as st
from . import api_client


def improvements_view_page():
    st.markdown("## Improvement Suggestions")

    # ── Filters ───────────────────────────────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        status_filter = st.selectbox("Status", ["All", "pending", "acknowledged", "resolved"])
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        st.button("Refresh")

    doctor_id = st.session_state.get("user_id") if st.session_state.get("backend_role") == "doctor" else None

    with st.spinner("Loading improvements..."):
        data, status = api_client.list_improvements(
            doctor_id=doctor_id,
            status=None if status_filter == "All" else status_filter,
        )

    if status != 200:
        st.error(data.get("message", "Failed to load improvements."))
        return

    improvements = data if isinstance(data, list) else data.get("improvements", [])
    st.caption(f"{len(improvements)} suggestions")

    if not improvements:
        st.info("No improvement suggestions found.")
        return

    status_options = ["pending", "acknowledged", "resolved"]
    priority_icon = {"low": "🔵", "medium": "🟡", "high": "🔴"}
    status_badge = {"pending": "🕐", "acknowledged": "👀", "resolved": "✅"}

    for imp in improvements:
        imp_id = str(imp.get("_id") or imp.get("id", ""))
        current_status = imp.get("status", "pending")
        priority = imp.get("priority", "low")
        suggestion = imp.get("education_suggestion", "")

        with st.container():
            icol1, icol2 = st.columns([5, 2])
            with icol1:
                st.markdown(
                    f"{priority_icon.get(priority, '⚪')} **{priority.upper()} priority** "
                    f"{status_badge.get(current_status, '')} {current_status.upper()}"
                )
                st.markdown(f"📋 {suggestion}")
                created = imp.get("created_at", "")[:10] if imp.get("created_at") else ""
                if created:
                    st.caption(f"Created: {created}")

            with icol2:
                new_status = st.selectbox(
                    "Update status", status_options,
                    index=status_options.index(current_status) if current_status in status_options else 0,
                    key=f"imp_sel_{imp_id}"
                )
                if new_status != current_status:
                    if st.button("Save", key=f"imp_btn_{imp_id}", type="primary"):
                        upd, upd_status = api_client.update_improvement_status(imp_id, new_status)
                        if upd_status == 200:
                            st.success("Status updated!")
                            st.rerun()
                        else:
                            st.error(upd.get("message", "Update failed"))

            st.divider()
