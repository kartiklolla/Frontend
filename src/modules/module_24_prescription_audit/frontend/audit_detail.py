"""
Audit Detail View — shows full audit report with scores, violations, improvements
"""

import streamlit as st
import matplotlib.pyplot as plt
import api_client


def audit_detail_page():
    audit_id = st.session_state.get("pa_audit_id", "")

    if st.button("⬅ Back"):
        prev = st.session_state.get("pa_audit_prev_view", "audits")
        st.session_state.pa_view = prev
        st.rerun()

    if not audit_id:
        st.error("No audit selected.")
        return

    with st.spinner("Loading audit report..."):
        data, status = api_client.get_audit(audit_id)

    if status != 200:
        st.error(data.get("message", "Failed to load audit."))
        return

    audit = data.get("audit", data)
    violations = data.get("violations", [])
    improvements = data.get("improvements", [])

    # ── Header ────────────────────────────────────────────────────────────────
    overall = audit.get("overall_score", 0)
    audit_status = audit.get("status", "unknown")
    icon = {"pass": "✅", "warning": "⚠️", "fail": "❌"}.get(audit_status, "📋")

    st.markdown(f"## {icon} Prescription Audit Report")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Overall Score", f"{overall:.1f}/100")
    col2.metric("Status", audit_status.upper())
    col3.metric("Violations", audit.get("violations_count", len(violations)))
    aud_date = (audit.get("audit_date") or audit.get("created_at", ""))[:10]
    col4.metric("Date", aud_date)

    st.divider()

    # ── Score Breakdown ───────────────────────────────────────────────────────
    st.markdown("### Score Breakdown")
    scores = {
        "Completeness (25%)": audit.get("completeness_score", 0),
        "Legibility (15%)": audit.get("legibility_score", 0),
        "Appropriateness (30%)": audit.get("appropriateness_score", 0),
        "Safety (30%)": audit.get("safety_score", 0),
    }

    score_col, chart_col = st.columns([2, 3])
    with score_col:
        for label, val in scores.items():
            color = "normal" if val >= 70 else ("off" if val >= 50 else "inverse")
            st.metric(label, f"{val:.1f}/100")

    with chart_col:
        fig, ax = plt.subplots(figsize=(5, 3))
        categories = ["Completeness", "Legibility", "Appropriateness", "Safety"]
        values = [audit.get("completeness_score", 0), audit.get("legibility_score", 0),
                  audit.get("appropriateness_score", 0), audit.get("safety_score", 0)]
        colors = ["#2ecc71" if v >= 70 else "#f39c12" if v >= 50 else "#e74c3c" for v in values]
        bars = ax.barh(categories, values, color=colors)
        ax.set_xlim(0, 100)
        ax.axvline(70, color="gray", linestyle="--", linewidth=0.8, label="Pass threshold (70)")
        ax.set_xlabel("Score")
        ax.legend(fontsize=7)
        for bar, val in zip(bars, values):
            ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                    f"{val:.0f}", va="center", fontsize=9)
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

    st.divider()

    # ── Root Cause Analysis ───────────────────────────────────────────────────
    rca = audit.get("root_cause_analysis", "")
    if rca:
        st.markdown("### Root Cause Analysis")
        st.info(rca)

    # ── Education Suggestions ─────────────────────────────────────────────────
    suggestions = audit.get("education_suggestions", [])
    if suggestions:
        st.markdown("### Education Suggestions")
        for s in suggestions:
            st.markdown(f"- {s}")

    st.divider()

    # ── Violations ────────────────────────────────────────────────────────────
    st.markdown(f"### Violations ({len(violations)})")
    if violations:
        sev_colors = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}
        for v in violations:
            sev = v.get("severity", "low")
            cat = v.get("category", "")
            desc = v.get("description", "")
            field = v.get("field", "")
            penalty = v.get("penalty_points", 0)
            col_a, col_b = st.columns([5, 1])
            with col_a:
                st.markdown(f"{sev_colors.get(sev, '⚪')} **{sev.upper()}** — {cat.capitalize()}: {desc}")
                if field:
                    st.caption(f"Field: `{field}` | Penalty: {penalty} pts")
            with col_b:
                guideline_ref = v.get("guideline_reference", "")
                if guideline_ref:
                    st.caption(f"Ref: {guideline_ref[:20]}")
            st.markdown("---")
    else:
        st.success("No violations detected.")

    st.divider()

    # ── Improvements ──────────────────────────────────────────────────────────
    st.markdown(f"### Improvement Suggestions ({len(improvements)})")
    if improvements:
        status_options = ["pending", "acknowledged", "resolved"]
        for imp in improvements:
            imp_id = str(imp.get("_id") or imp.get("id", ""))
            current_status = imp.get("status", "pending")
            priority = imp.get("priority", "low")
            suggestion = imp.get("education_suggestion", "")
            priority_icon = {"low": "🔵", "medium": "🟡", "high": "🔴"}.get(priority, "⚪")

            icol1, icol2 = st.columns([5, 2])
            with icol1:
                st.markdown(f"{priority_icon} **{priority.upper()} priority** — {suggestion}")
                st.caption(f"Status: {current_status}")
            with icol2:
                new_status = st.selectbox(
                    "Update status", status_options,
                    index=status_options.index(current_status),
                    key=f"imp_status_{imp_id}"
                )
                if new_status != current_status:
                    if st.button("Save", key=f"imp_save_{imp_id}"):
                        upd, upd_status = api_client.update_improvement_status(imp_id, new_status)
                        if upd_status == 200:
                            st.success("Updated")
                            st.rerun()
                        else:
                            st.error("Update failed")
            st.markdown("---")
    else:
        st.info("No improvement suggestions for this audit.")

    st.divider()

    # ── Guideline Adherence ───────────────────────────────────────────────────
    adherence = audit.get("guideline_adherence_score")
    if adherence is not None:
        st.metric("Guideline Adherence Score", f"{adherence:.1f}/100")
