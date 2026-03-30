"""
Reports View — statistical analysis, doctor rankings, trend detection
"""

import streamlit as st
import matplotlib.pyplot as plt
import api_client


def reports_view_page():
    st.markdown("## Reports & Analytics")

    tab1, tab2, tab3, tab4 = st.tabs(["Audit Summary", "Violation Analysis", "Doctor Rankings", "Trend Detection"])

    # ── Audit Summary ─────────────────────────────────────────────────────────
    with tab1:
        st.markdown("### Audit Summary Statistics")
        with st.spinner("Loading..."):
            data, status = api_client.get_audit_summary()

        if status != 200:
            st.error(data.get("message", "Failed to load audit summary."))
        else:
            summary = data if isinstance(data, dict) else {}
            col1, col2, col3, col4 = st.columns(4)
            total_audits = summary.get("total_audits", 0)
            by_status = summary.get("by_status", {})
            # by_status values may be dicts {"count": N, "avg_score": X} or plain ints
            def _count(v):
                return v.get("count", 0) if isinstance(v, dict) else (v or 0)
            pass_count = _count(by_status.get("pass", 0))
            fail_count = _count(by_status.get("fail", 0))
            pass_rate = (pass_count / total_audits * 100) if total_audits else 0
            fail_rate = (fail_count / total_audits * 100) if total_audits else 0
            avg_scores = summary.get("average_scores", {})
            avg_overall = avg_scores.get("avg_overall", summary.get("avg_overall_score", 0)) or 0

            col1.metric("Total Audits", total_audits)
            col2.metric("Pass Rate", f"{pass_rate:.1f}%")
            col3.metric("Avg Score", f"{avg_overall:.1f}")
            col4.metric("Fail Rate", f"{fail_rate:.1f}%")

            if by_status:
                st.markdown("#### Audit Status Distribution")
                fig, ax = plt.subplots(figsize=(4, 4))
                labels = list(by_status.keys())
                vals = [_count(by_status[k]) for k in labels]
                if any(v > 0 for v in vals):
                    colors = {"pass": "#2ecc71", "warning": "#f39c12", "fail": "#e74c3c"}
                    pie_colors = [colors.get(l, "#95a5a6") for l in labels]
                    ax.pie(vals, labels=labels, autopct="%1.0f%%", colors=pie_colors,
                           startangle=90, textprops={"fontsize": 10})
                    st.pyplot(fig)
                plt.close(fig)

    # ── Violation Analysis ────────────────────────────────────────────────────
    with tab2:
        st.markdown("### Violation Analysis")
        with st.spinner("Loading..."):
            data, status = api_client.get_violation_analysis()

        if status != 200:
            st.error(data.get("message", "Failed to load violation analysis."))
        else:
            analysis = data if isinstance(data, dict) else {}
            st.json(analysis)

    # ── Doctor Rankings ───────────────────────────────────────────────────────
    with tab3:
        st.markdown("### Doctor Compliance Rankings")
        with st.spinner("Loading..."):
            data, status = api_client.get_doctor_rankings()

        if status != 200:
            st.error(data.get("message", "Failed to load doctor rankings."))
        else:
            rankings = data if isinstance(data, list) else data.get("rankings", [])

            if rankings:
                rows = []
                for rank, doc in enumerate(rankings, 1):
                    rows.append({
                        "Rank": rank,
                        "Doctor ID": doc.get("doctor_id", "")[:16],
                        "Avg Score": f"{doc.get('avg_score', 0):.1f}",
                        "Prescriptions": doc.get("total_prescriptions", 0),
                        "Pass Rate": f"{doc.get('pass_rate', 0):.1f}%",
                    })

                st.table(rows)

                if len(rankings) > 1:
                    fig, ax = plt.subplots(figsize=(7, 3))
                    ids = [f"Dr.{i+1}" for i in range(len(rankings))]
                    scores = [r.get("avg_score", 0) for r in rankings]
                    colors = ["#2ecc71" if s >= 70 else "#e74c3c" for s in scores]
                    ax.bar(ids, scores, color=colors)
                    ax.axhline(70, color="gray", linestyle="--", linewidth=0.8)
                    ax.set_ylabel("Avg Audit Score")
                    ax.set_title("Doctor Rankings")
                    fig.tight_layout()
                    st.pyplot(fig)
                    plt.close(fig)
            else:
                st.info("No doctor ranking data available.")

    # ── Trend Detection ───────────────────────────────────────────────────────
    with tab4:
        st.markdown("### Trend Detection")
        with st.spinner("Loading..."):
            data, status = api_client.get_trend_detection()

        if status != 200:
            st.error(data.get("message", "Failed to load trend data."))
        else:
            trends = data if isinstance(data, dict) else {}

            # Backend returns "improving"/"declining"; support both key names
            improving = trends.get("improving_doctors", trends.get("improving", []))
            declining = trends.get("declining_doctors", trends.get("declining", []))

            tcol1, tcol2 = st.columns(2)
            with tcol1:
                st.markdown("#### Improving Doctors 📈")
                if improving:
                    for d in improving:
                        did = str(d.get("doctor_id", d.get("_id", "")))[:12]
                        trend_val = d.get("trend", d.get("latest_trend", 0)) or 0
                        st.success(f"Doctor {did} — Trend: +{trend_val:.1f}")
                else:
                    st.info("No improving trend detected.")

            with tcol2:
                st.markdown("#### Declining Doctors 📉")
                if declining:
                    for d in declining:
                        did = str(d.get("doctor_id", d.get("_id", "")))[:12]
                        trend_val = d.get("trend", d.get("latest_trend", 0)) or 0
                        st.error(f"Doctor {did} — Trend: {trend_val:.1f}")
                else:
                    st.info("No declining trend detected.")
