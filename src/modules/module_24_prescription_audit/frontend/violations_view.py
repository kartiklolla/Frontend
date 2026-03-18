"""
Violations Summary View — aggregated statistics and charts
"""

import streamlit as st
import matplotlib.pyplot as plt
from . import api_client


def violations_view_page():
    st.markdown("## Violations Dashboard")

    with st.spinner("Loading violation summary..."):
        data, status = api_client.get_violation_summary()

    if status != 200:
        st.error(data.get("message", "Failed to load violation summary."))
        return

    summary = data if isinstance(data, dict) else {}

    # ── Top-level metrics ─────────────────────────────────────────────────────
    by_category = summary.get("by_category", {})
    by_severity = summary.get("by_severity", {})
    total = summary.get("total", sum(by_category.values()) if by_category else 0)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Violations", total)
    col2.metric("Critical", by_severity.get("critical", 0))
    col3.metric("High", by_severity.get("high", 0))
    col4.metric("Medium", by_severity.get("medium", 0))

    st.divider()

    chart_col1, chart_col2 = st.columns(2)

    # ── By Category pie chart ─────────────────────────────────────────────────
    with chart_col1:
        st.markdown("#### Violations by Category")
        if by_category:
            fig, ax = plt.subplots(figsize=(4, 4))
            labels = list(by_category.keys())
            values = [by_category[k] for k in labels]
            colors = ["#3498db", "#9b59b6", "#2ecc71", "#e74c3c"]
            ax.pie(values, labels=labels, autopct="%1.0f%%", colors=colors[:len(labels)],
                   startangle=90, textprops={"fontsize": 9})
            ax.set_title("By Category")
            st.pyplot(fig)
            plt.close(fig)
        else:
            st.info("No category data available.")

    # ── By Severity bar chart ─────────────────────────────────────────────────
    with chart_col2:
        st.markdown("#### Violations by Severity")
        if by_severity:
            fig, ax = plt.subplots(figsize=(4, 3))
            sevs = ["low", "medium", "high", "critical"]
            vals = [by_severity.get(s, 0) for s in sevs]
            colors = ["#2ecc71", "#f39c12", "#e67e22", "#e74c3c"]
            ax.bar(sevs, vals, color=colors)
            ax.set_ylabel("Count")
            ax.set_title("By Severity")
            for i, v in enumerate(vals):
                ax.text(i, v + 0.1, str(v), ha="center", fontsize=9)
            fig.tight_layout()
            st.pyplot(fig)
            plt.close(fig)
        else:
            st.info("No severity data available.")

    st.divider()

    # ── Filterable violation list ─────────────────────────────────────────────
    st.markdown("### Violation Records")
    fc1, fc2 = st.columns(2)
    with fc1:
        cat_filter = st.selectbox("Category", ["All", "completeness", "legibility", "appropriateness", "safety"])
    with fc2:
        sev_filter = st.selectbox("Severity", ["All", "low", "medium", "high", "critical"])

    with st.spinner("Loading violations..."):
        vdata, vstatus = api_client.list_violations(
            category=None if cat_filter == "All" else cat_filter,
            severity=None if sev_filter == "All" else sev_filter,
        )

    if vstatus != 200:
        msg = vdata.get("message", "Failed to load violations.") if isinstance(vdata, dict) else "Failed to load violations."
        st.error(msg)
        return

    violations = vdata if isinstance(vdata, list) else vdata.get("violations", [])
    st.caption(f"{len(violations)} violations")

    sev_icon = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}
    for v in violations:
        sev = v.get("severity", "low")
        cat = v.get("category", "")
        desc = v.get("description", "")
        field = v.get("field", "")
        penalty = v.get("penalty_points", 0)
        st.markdown(f"{sev_icon.get(sev, '⚪')} **{sev.upper()}** [{cat}] — {desc}")
        if field:
            st.caption(f"Field: `{field}` | Penalty: {penalty} pts")
        st.markdown("---")
