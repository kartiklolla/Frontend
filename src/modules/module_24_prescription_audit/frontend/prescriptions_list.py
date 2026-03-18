"""
Prescriptions List and Detail View
"""

import streamlit as st
from . import api_client


def prescriptions_list_page():
    st.markdown("## Prescriptions")

    # ── Filters ───────────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        filter_patient = st.text_input("Filter by Patient ID", placeholder="PT-2024-001")
    with col2:
        filter_page = st.number_input("Page", min_value=1, step=1, value=1)
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        refresh = st.button("Refresh", use_container_width=True)

    # Doctor sees only own prescriptions; admin sees all
    doctor_id = None
    if st.session_state.get("backend_role") == "doctor":
        doctor_id = st.session_state.get("user_id")

    with st.spinner("Loading prescriptions..."):
        data, status = api_client.list_prescriptions(
            doctor_id=doctor_id,
            patient_id=filter_patient.strip() if filter_patient.strip() else None,
            page=int(filter_page),
        )

    if status != 200:
        st.error(data.get("message", "Failed to load prescriptions."))
        return

    prescriptions = data.get("prescriptions", data.get("data", []))
    total = data.get("total", len(prescriptions))
    st.caption(f"Showing {len(prescriptions)} of {total} prescriptions")

    if not prescriptions:
        st.info("No prescriptions found. Use **New Prescription** to add one.")
        return

    # ── Prescription cards ────────────────────────────────────────────────────
    for rx in prescriptions:
        rx_id = str(rx.get("_id") or rx.get("id", ""))
        with st.container():
            hcol1, hcol2, hcol3 = st.columns([3, 2, 1])
            with hcol1:
                st.markdown(f"**{rx.get('patient_name', 'Unknown')}** &nbsp;|&nbsp; {rx.get('diagnosis', '')}")
                st.caption(f"Age: {rx.get('patient_age', '?')} | Gender: {rx.get('patient_gender', '?')} | ID: {rx_id[:8]}...")
            with hcol2:
                meds = rx.get("medications", [])
                med_names = ", ".join(m.get("drug_name", "") for m in meds[:3])
                if len(meds) > 3:
                    med_names += f" +{len(meds) - 3} more"
                st.markdown(f"💊 {med_names or 'No medications'}")
                created = rx.get("created_at", "")[:10] if rx.get("created_at") else "N/A"
                st.caption(f"Created: {created}")
            with hcol3:
                if st.button("View →", key=f"rx_view_{rx_id}", use_container_width=True):
                    st.session_state.pa_view = "prescription_detail"
                    st.session_state.pa_prescription_id = rx_id
                    st.rerun()
            st.divider()


def prescription_detail_page():
    rx_id = st.session_state.get("pa_prescription_id", "")

    if st.button("⬅ Back to Prescriptions"):
        st.session_state.pa_view = "prescriptions"
        st.rerun()

    if not rx_id:
        st.error("No prescription selected.")
        return

    with st.spinner("Loading prescription..."):
        data, status = api_client.get_prescription(rx_id)

    if status != 200:
        st.error(data.get("message", "Failed to load prescription."))
        return

    rx = data if "patient_name" in data else data.get("prescription", data)

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown(f"## {rx.get('patient_name', 'Unknown')} — Prescription Detail")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Age:** {rx.get('patient_age', '?')}")
        st.markdown(f"**Gender:** {rx.get('patient_gender', '?')}")
        st.markdown(f"**Patient ID:** {rx.get('patient_id', 'N/A')}")
        legible = "Yes ✅" if rx.get("is_legible") else "No ❌"
        st.markdown(f"**Legible:** {legible}")
    with col2:
        st.markdown(f"**Diagnosis:** {rx.get('diagnosis', 'N/A')}")
        st.markdown(f"**Notes:** {rx.get('notes', '—')}")
        created = rx.get("created_at", "")[:10] if rx.get("created_at") else "N/A"
        st.markdown(f"**Created:** {created}")

    st.divider()

    # ── Medications ───────────────────────────────────────────────────────────
    st.markdown("### Medications")
    meds = rx.get("medications", [])
    if meds:
        rows = []
        for m in meds:
            rows.append({
                "Drug": m.get("drug_name", ""),
                "Dosage": m.get("dosage", ""),
                "Frequency": m.get("frequency", ""),
                "Duration": m.get("duration", ""),
                "Route": m.get("route", ""),
            })
        st.table(rows)
    else:
        st.info("No medications recorded.")

    st.divider()

    # ── Audit History ─────────────────────────────────────────────────────────
    st.markdown("### Audit History")
    with st.spinner("Loading audits..."):
        audit_data, audit_status = api_client.get_prescription_audits(rx_id)

    audits = []
    if audit_status == 200:
        audits = audit_data if isinstance(audit_data, list) else audit_data.get("audits", [])

    if audits:
        for aud in audits:
            aud_id = str(aud.get("_id") or aud.get("id", ""))
            score = aud.get("overall_score", 0)
            st_str = aud.get("status", "unknown")
            icon = {"pass": "✅", "warning": "⚠️", "fail": "❌"}.get(st_str, "📋")
            acol1, acol2 = st.columns([4, 1])
            with acol1:
                st.markdown(f"{icon} **Score: {score:.1f}/100** — {st_str.upper()}")
                aud_date = aud.get("audit_date", aud.get("created_at", ""))[:10]
                st.caption(f"Date: {aud_date} | Violations: {aud.get('violations_count', '?')}")
            with acol2:
                if st.button("Details", key=f"aud_{aud_id}"):
                    st.session_state.pa_view = "audit_detail"
                    st.session_state.pa_audit_id = aud_id
                    st.rerun()
            st.divider()
    else:
        st.info("No audits yet for this prescription.")
        if st.button("Run Audit Now", type="primary"):
            with st.spinner("Running audit..."):
                result, r_status = api_client.run_audit(rx_id)
            if r_status in (200, 201):
                st.success(f"Audit complete — Score: {result.get('overall_score', 0):.1f}/100")
                st.rerun()
            else:
                st.error(result.get("message", "Audit failed"))
