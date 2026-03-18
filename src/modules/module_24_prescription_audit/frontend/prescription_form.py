"""
Prescription Entry Form — creates a new prescription in the database
and optionally triggers an audit immediately.
"""

import streamlit as st
from . import api_client


def prescription_form_page():
    st.markdown("## New Prescription")
    st.markdown("Fill in the patient and medication details. The record will be saved to the database and an automated audit can be run immediately.")
    st.divider()

    # ── Patient Information ───────────────────────────────────────────────────
    st.markdown("### Patient Information")
    col1, col2, col3 = st.columns(3)
    with col1:
        patient_name = st.text_input("Patient Name *", placeholder="e.g. Aarav Patel")
    with col2:
        patient_age = st.number_input("Age *", min_value=0, max_value=120, step=1, value=30)
    with col3:
        patient_gender = st.selectbox("Gender *", ["Male", "Female", "Other"])

    patient_id = st.text_input("Patient ID", placeholder="e.g. PT-2024-001 (optional, auto-generated if blank)")
    diagnosis = st.text_area("Diagnosis *", placeholder="e.g. Type 2 Diabetes Mellitus, Hypertension")
    notes = st.text_area("Clinical Notes", placeholder="Any additional notes for the pharmacist or record")
    is_legible = st.checkbox("Prescription is legible / entered electronically", value=True)

    st.divider()

    # ── Medications ───────────────────────────────────────────────────────────
    st.markdown("### Medications")
    st.caption("Add one or more medications to this prescription.")

    if "rx_medications" not in st.session_state:
        st.session_state.rx_medications = [_blank_med()]

    for i, med in enumerate(st.session_state.rx_medications):
        with st.expander(f"Medication {i + 1}: {med.get('drug_name', '(unnamed)')}", expanded=True):
            mc1, mc2 = st.columns(2)
            with mc1:
                st.session_state.rx_medications[i]["drug_name"] = st.text_input(
                    "Drug Name *", value=med.get("drug_name", ""), key=f"drug_{i}",
                    placeholder="e.g. Metformin"
                )
                st.session_state.rx_medications[i]["dosage"] = st.text_input(
                    "Dosage *", value=med.get("dosage", ""), key=f"dosage_{i}",
                    placeholder="e.g. 500mg"
                )
                st.session_state.rx_medications[i]["frequency"] = st.text_input(
                    "Frequency *", value=med.get("frequency", ""), key=f"freq_{i}",
                    placeholder="e.g. twice daily"
                )
            with mc2:
                st.session_state.rx_medications[i]["duration"] = st.text_input(
                    "Duration *", value=med.get("duration", ""), key=f"dur_{i}",
                    placeholder="e.g. 7 days"
                )
                st.session_state.rx_medications[i]["route"] = st.selectbox(
                    "Route *", ["oral", "intravenous", "intramuscular", "subcutaneous", "topical", "inhaled", "other"],
                    index=["oral", "intravenous", "intramuscular", "subcutaneous", "topical", "inhaled", "other"].index(
                        med.get("route", "oral")
                    ),
                    key=f"route_{i}"
                )

            if len(st.session_state.rx_medications) > 1:
                if st.button("Remove", key=f"remove_med_{i}"):
                    st.session_state.rx_medications.pop(i)
                    st.rerun()

    if st.button("+ Add Another Medication"):
        st.session_state.rx_medications.append(_blank_med())
        st.rerun()

    st.divider()

    # ── Submit ────────────────────────────────────────────────────────────────
    run_audit_now = st.checkbox("Run automated audit immediately after saving", value=True)

    col_save, col_clear = st.columns([3, 1])
    with col_save:
        submitted = st.button("Save Prescription", type="primary", use_container_width=True)
    with col_clear:
        if st.button("Clear Form", use_container_width=True):
            st.session_state.rx_medications = [_blank_med()]
            st.rerun()

    if submitted:
        _submit(patient_name, patient_id, patient_age, patient_gender,
                diagnosis, notes, is_legible, run_audit_now)


def _blank_med():
    return {"drug_name": "", "dosage": "", "frequency": "", "duration": "", "route": "oral"}


def _submit(patient_name, patient_id, patient_age, patient_gender,
            diagnosis, notes, is_legible, run_audit_now):
    errors = []
    if not patient_name.strip():
        errors.append("Patient Name is required.")
    if not diagnosis.strip():
        errors.append("Diagnosis is required.")
    meds = [m for m in st.session_state.rx_medications if m.get("drug_name", "").strip()]
    if not meds:
        errors.append("At least one medication with a drug name is required.")
    for i, m in enumerate(meds):
        for field in ("dosage", "frequency", "duration"):
            if not m.get(field, "").strip():
                errors.append(f"Medication {i + 1}: '{field}' is required.")

    if errors:
        for e in errors:
            st.error(e)
        return

    payload = {
        "patient_name": patient_name.strip(),
        "patient_id": patient_id.strip() if patient_id.strip() else None,
        "patient_age": int(patient_age),
        "patient_gender": patient_gender,
        "diagnosis": diagnosis.strip(),
        "notes": notes.strip(),
        "is_legible": is_legible,
        "medications": meds,
        "doctor_id": st.session_state.get("user_id", ""),
    }

    with st.spinner("Saving prescription..."):
        data, status = api_client.create_prescription(payload)

    if status not in (200, 201):
        msg = data.get("message", "Unknown error")
        st.error(f"Failed to save prescription: {msg}")
        return

    prescription_id = str(data.get("_id") or data.get("id") or data.get("prescription_id", ""))
    st.success(f"Prescription saved! ID: {prescription_id}")

    if run_audit_now and prescription_id:
        with st.spinner("Running automated audit..."):
            audit_data, audit_status = api_client.run_audit(prescription_id)

        if audit_status in (200, 201):
            score = audit_data.get("overall_score", 0)
            audit_status_str = audit_data.get("status", "unknown")
            status_icon = {"pass": "✅", "warning": "⚠️", "fail": "❌"}.get(audit_status_str, "📋")
            st.info(f"{status_icon} Audit complete — Overall Score: **{score:.1f}/100** | Status: **{audit_status_str.upper()}**")

            # Store audit ID for navigation
            audit_id = str(audit_data.get("_id") or audit_data.get("audit_id") or audit_data.get("id", ""))
            if audit_id:
                if st.button("View Full Audit Report →"):
                    st.session_state.pa_view = "audit_detail"
                    st.session_state.pa_audit_id = audit_id
                    st.rerun()
        else:
            msg = audit_data.get("message", "Audit failed")
            st.warning(f"Prescription saved but audit failed: {msg}")

    # Reset form
    st.session_state.rx_medications = [_blank_med()]
