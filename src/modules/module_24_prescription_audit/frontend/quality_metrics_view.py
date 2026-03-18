"""
Quality Metrics View — compliance scores, trends, and monthly summaries
"""

import streamlit as st
import matplotlib.pyplot as plt
from . import api_client


def quality_metrics_view_page():
    st.markdown("## Quality Metrics")

    doctor_id = st.session_state.get("user_id", "")
    backend_role = st.session_state.get("backend_role", "doctor")

    # ── Compute button (hospital_staff or admin) ───────────────────────────────
    if backend_role in ("hospital_staff", "admin"):
        st.markdown("### Compute Metrics")
        tc1, tc2, tc3 = st.columns([2, 2, 1])
        with tc1:
            target_doctor = st.text_input("Doctor ID", value=doctor_id, placeholder="Leave blank for own")
        with tc2:
            import datetime
            period_val = st.text_input("Period (YYYY-MM)", value=datetime.datetime.now().strftime("%Y-%m"))
        with tc3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Compute", type="primary"):
                tid = target_doctor.strip() or doctor_id
                with st.spinner("Computing metrics..."):
                    r, s = api_client.compute_quality_metrics(tid, period_val.strip())
                if s in (200, 201):
                    st.success("Metrics computed successfully!")
                    st.rerun()
                else:
                    st.error(r.get("message", "Computation failed"))
        st.divider()

    # ── Load metrics ──────────────────────────────────────────────────────────
    qm_doctor_id = doctor_id if backend_role == "doctor" else None

    with st.spinner("Loading quality metrics..."):
        data, status = api_client.list_quality_metrics(doctor_id=qm_doctor_id)

    if status != 200:
        st.error(data.get("message", "Failed to load quality metrics."))
        return

    metrics = data if isinstance(data, list) else data.get("quality_metrics", [])

    if not metrics:
        st.info("No quality metrics computed yet.")
        return

    latest = metrics[0] if metrics else {}

    # ── KPI cards ─────────────────────────────────────────────────────────────
    st.markdown("### Latest Period Summary")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Compliance Score", f"{latest.get('compliance_score', 0):.1f}%")
    col2.metric("Error Rate", f"{latest.get('error_rate', 0):.1f}%")
    col3.metric("Total Prescriptions", latest.get("total_prescriptions", 0))
    col4.metric("Total Audits", latest.get("total_audits", 0))

    st.divider()

    # ── Scores by area ────────────────────────────────────────────────────────
    st.markdown("### Average Scores by Area")
    area_cols = st.columns(4)
    areas = [
        ("avg_completeness", "Completeness"),
        ("avg_legibility", "Legibility"),
        ("avg_appropriateness", "Appropriateness"),
        ("avg_safety", "Safety"),
    ]
    for col, (key, label) in zip(area_cols, areas):
        val = latest.get(key, 0)
        delta = "pass" if val >= 70 else "fail"
        col.metric(label, f"{val:.1f}/100")

    # ── Trend chart ───────────────────────────────────────────────────────────
    st.divider()
    st.markdown("### Compliance Trend")

    with st.spinner("Loading trend data..."):
        trend_data, trend_status = api_client.get_quality_trend(doctor_id)

    if trend_status == 200:
        trend = trend_data if isinstance(trend_data, list) else trend_data.get("trend", [])
        if trend:
            periods = [t.get("period", "") for t in trend]
            scores = [t.get("compliance_score", 0) for t in trend]

            fig, ax = plt.subplots(figsize=(8, 3))
            ax.plot(periods, scores, marker="o", color="#3498db", linewidth=2)
            ax.axhline(70, color="gray", linestyle="--", linewidth=0.8, label="Pass (70%)")
            ax.fill_between(periods, scores, alpha=0.15, color="#3498db")
            ax.set_ylabel("Compliance Score")
            ax.set_xlabel("Period")
            ax.set_ylim(0, 105)
            ax.legend(fontsize=8)
            plt.xticks(rotation=30, fontsize=8)
            fig.tight_layout()
            st.pyplot(fig)
            plt.close(fig)
        else:
            st.info("Not enough data for trend chart.")
    else:
        st.info("Trend data not available.")

    # ── Full metrics table ────────────────────────────────────────────────────
    st.divider()
    st.markdown("### All Periods")
    rows = []
    for m in metrics:
        rows.append({
            "Period": m.get("period", ""),
            "Compliance": f"{m.get('compliance_score', 0):.1f}%",
            "Error Rate": f"{m.get('error_rate', 0):.1f}%",
            "Prescriptions": m.get("total_prescriptions", 0),
            "Audits": m.get("total_audits", 0),
            "Trend": f"{m.get('improvement_trend', 0):+.1f}",
        })
    if rows:
        st.table(rows)
