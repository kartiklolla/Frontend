"""
Prescription Audit System — Module 24
Main entry point. Renders the full module UI inside the doctor/admin dashboard.

Views (controlled via st.session_state.pa_view):
  - dashboard        : Overview with KPIs and quick actions
  - new_prescription : Prescription entry form
  - prescriptions    : List of all prescriptions
  - prescription_detail : Single prescription detail + audit history
  - audits           : List of all audits
  - audit_detail     : Full audit report
  - violations       : Violations dashboard
  - improvements     : Improvement suggestions
  - quality_metrics  : Quality metrics and trends
  - reports          : Statistical reports
  - guidelines       : Clinical guidelines management (admin)
"""

import streamlit as st
import matplotlib.pyplot as plt

from prescription_form import prescription_form_page
from prescriptions_list import prescriptions_list_page, prescription_detail_page
from audits_list import audits_list_page
from audit_detail import audit_detail_page
from violations_view import violations_view_page
from improvements_view import improvements_view_page
from quality_metrics_view import quality_metrics_view_page
from reports_view import reports_view_page
from guidelines_view import guidelines_view_page
import api_client


# Navigation label → pa_view key
NAV_ITEMS = {
    "Dashboard": "dashboard",
    "New Prescription": "new_prescription",
    "Prescriptions": "prescriptions",
    "Audits": "audits",
    "Violations": "violations",
    "Improvements": "improvements",
    "Quality Metrics": "quality_metrics",
    "Reports": "reports",
    "Guidelines": "guidelines",
}


def prescription_audit_module():
    """Render the full Prescription Audit System module."""

    st.session_state.setdefault("pa_view", "dashboard")
    st.session_state.setdefault("pa_prescription_id", None)
    st.session_state.setdefault("pa_audit_id", None)
    st.session_state.setdefault("pa_audit_prev_view", "audits")

    _render_module_header()
    _render_module_nav()
    st.divider()
    _route()


def _render_module_header():
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown("# 💊 Prescription Audit System")
        st.caption("Automated prescription quality assessment — Module C6 / Module 24")
    with col2:
        # Backend health indicator
        _, hstatus = api_client.health_check()
        if hstatus == 200:
            st.success("Backend ✅")
        else:
            st.error("Backend ❌ (port 5000)")


def _render_module_nav():
    backend_role = st.session_state.get("backend_role", "doctor")
    nav_labels = list(NAV_ITEMS.keys())
    if backend_role not in ("admin",):
        nav_labels = [n for n in nav_labels if n != "Guidelines"]

    current_view = st.session_state.get("pa_view", "dashboard")
    # Map current view back to label for default selection
    view_to_label = {v: k for k, v in NAV_ITEMS.items()}
    current_label = view_to_label.get(current_view, "Dashboard")

    cols = st.columns(len(nav_labels))
    for col, label in zip(cols, nav_labels):
        is_active = (label == current_label)
        btn_type = "primary" if is_active else "secondary"
        with col:
            if st.button(label, use_container_width=True, type=btn_type, key=f"pa_nav_{label}"):
                st.session_state.pa_view = NAV_ITEMS[label]
                st.rerun()


def _route():
    view = st.session_state.get("pa_view", "dashboard")

    if view == "dashboard":
        _dashboard_view()
    elif view == "new_prescription":
        prescription_form_page()
    elif view == "prescriptions":
        prescriptions_list_page()
    elif view == "prescription_detail":
        prescription_detail_page()
    elif view == "audits":
        audits_list_page()
    elif view == "audit_detail":
        audit_detail_page()
    elif view == "violations":
        violations_view_page()
    elif view == "improvements":
        improvements_view_page()
    elif view == "quality_metrics":
        quality_metrics_view_page()
    elif view == "reports":
        reports_view_page()
    elif view == "guidelines":
        guidelines_view_page()
    else:
        _dashboard_view()


def _dashboard_view():
    st.markdown("## Overview")

    doctor_id = st.session_state.get("user_id")
    user_name = st.session_state.get("user_name", "Doctor")
    st.markdown(f"Welcome, **{user_name}**! Here's a quick overview of your prescription audit activity.")

    # ── Load summary data ─────────────────────────────────────────────────────
    audit_summary = {}
    violation_summary = {}
    quality_metrics = []

    with st.spinner("Loading dashboard data..."):
        as_data, as_status = api_client.get_audit_summary()
        if as_status == 200:
            audit_summary = as_data

        vs_data, vs_status = api_client.get_violation_summary()
        if vs_status == 200:
            violation_summary = vs_data

        qm_did = doctor_id if st.session_state.get("backend_role") == "doctor" else None
        qm_data, qm_status = api_client.list_quality_metrics(doctor_id=qm_did)
        if qm_status == 200:
            quality_metrics = qm_data if isinstance(qm_data, list) else qm_data.get("quality_metrics", [])

    # ── Derive KPI values from backend response shape ─────────────────────────
    total_audits = audit_summary.get("total_audits", 0)
    by_status_raw = audit_summary.get("by_status", {})
    pass_count = by_status_raw.get("pass", {}).get("count", 0) if isinstance(by_status_raw.get("pass"), dict) else by_status_raw.get("pass", 0)
    pass_rate = (pass_count / total_audits * 100) if total_audits else 0
    avg_scores = audit_summary.get("average_scores", {})
    avg_overall = avg_scores.get("avg_overall", audit_summary.get("avg_overall_score", 0)) or 0

    # ── KPI row ───────────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Audits", total_audits)
    col2.metric("Pass Rate", f"{pass_rate:.1f}%")
    col3.metric("Avg Score", f"{avg_overall:.1f}")

    latest_qm = quality_metrics[0] if quality_metrics else {}
    col4.metric("Compliance Score", f"{latest_qm.get('compliance_score', 0):.1f}%")

    st.divider()

    chart_col, action_col = st.columns([2, 1])

    with chart_col:
        # ── Violation severity distribution ───────────────────────────────────
        # Backend /violations/summary returns a flat list [{category, severity, count}]
        # Aggregate counts by severity into a plain dict
        if isinstance(violation_summary, list):
            by_severity = {}
            for item in violation_summary:
                sev = item.get("severity", "")
                by_severity[sev] = by_severity.get(sev, 0) + item.get("count", 0)
        else:
            by_severity = violation_summary.get("by_severity", {})
        if by_severity:
            st.markdown("### Violation Severity Distribution")
            fig, ax = plt.subplots(figsize=(5, 3))
            sevs = ["low", "medium", "high", "critical"]
            vals = [by_severity.get(s, 0) for s in sevs]
            colors = ["#2ecc71", "#f39c12", "#e67e22", "#e74c3c"]
            ax.bar(sevs, vals, color=colors)
            ax.set_ylabel("Count")
            for i, v in enumerate(vals):
                if v:
                    ax.text(i, v + 0.1, str(v), ha="center", fontsize=9)
            fig.tight_layout()
            st.pyplot(fig)
            plt.close(fig)

    with action_col:
        st.markdown("### Quick Actions")
        if st.button("➕ New Prescription", use_container_width=True, type="primary"):
            st.session_state.pa_view = "new_prescription"
            st.rerun()
        if st.button("📋 All Prescriptions", use_container_width=True):
            st.session_state.pa_view = "prescriptions"
            st.rerun()
        if st.button("🔍 View Audits", use_container_width=True):
            st.session_state.pa_view = "audits"
            st.rerun()
        if st.button("📊 Quality Metrics", use_container_width=True):
            st.session_state.pa_view = "quality_metrics"
            st.rerun()
        if st.button("⚠️ Violations", use_container_width=True):
            st.session_state.pa_view = "violations"
            st.rerun()

    # ── Recent audits ─────────────────────────────────────────────────────────
    st.divider()
    st.markdown("### Recent Audits")

    qm_doctor = doctor_id if st.session_state.get("backend_role") == "doctor" else None
    rec_data, rec_status = api_client.list_audits(doctor_id=qm_doctor, per_page=5)
    if rec_status == 200:
        recent = rec_data.get("audits", rec_data.get("data", []))
        if recent:
            sev_icon = {"pass": "✅", "warning": "⚠️", "fail": "❌"}
            for aud in recent[:5]:
                aud_id = str(aud.get("_id") or aud.get("id", ""))
                score = aud.get("overall_score", 0)
                aud_status = aud.get("status", "unknown")
                icon = sev_icon.get(aud_status, "📋")
                aud_date = (aud.get("audit_date") or aud.get("created_at", ""))[:10]
                rc1, rc2 = st.columns([4, 1])
                with rc1:
                    st.markdown(f"{icon} **{score:.1f}/100** — {aud_status.upper()} | {aud_date}")
                with rc2:
                    if st.button("View", key=f"dash_aud_{aud_id}"):
                        st.session_state.pa_audit_id = aud_id
                        st.session_state.pa_audit_prev_view = "dashboard"
                        st.session_state.pa_view = "audit_detail"
                        st.rerun()
        else:
            st.info("No audit records yet. Start by adding a prescription.")

if __name__ == "__main__":
    prescription_audit_module()