"""
Clinical Guidelines Management View (admin only)
"""

import streamlit as st
from . import api_client


def guidelines_view_page():
    role = st.session_state.get("backend_role", "doctor")
    st.markdown("## Clinical Guidelines")

    # ── Add new guideline (admin only) ────────────────────────────────────────
    if role == "admin":
        with st.expander("➕ Add New Guideline", expanded=False):
            g_name = st.text_input("Guideline Name", placeholder="e.g. Paracetamol Safety Rule")
            g_category = st.selectbox("Category", ["dosage", "interaction", "contraindication", "general"])
            g_drug = st.text_input("Drug Name", placeholder="e.g. Paracetamol (leave blank for general)")

            st.markdown("**Rules** (add at least one rule)")
            if "new_guideline_rules" not in st.session_state:
                st.session_state.new_guideline_rules = [{"rule_type": "max_dosage", "description": "", "params": {}}]

            for ri, rule in enumerate(st.session_state.new_guideline_rules):
                rc1, rc2 = st.columns([2, 3])
                with rc1:
                    rt = st.selectbox(
                        "Rule Type", ["max_dosage", "interaction", "contraindication", "required_field"],
                        index=["max_dosage", "interaction", "contraindication", "required_field"].index(
                            rule.get("rule_type", "max_dosage")
                        ),
                        key=f"g_rt_{ri}"
                    )
                    st.session_state.new_guideline_rules[ri]["rule_type"] = rt
                with rc2:
                    desc = st.text_input("Description", value=rule.get("description", ""), key=f"g_desc_{ri}",
                                         placeholder="e.g. Maximum daily dose is 4000mg")
                    st.session_state.new_guideline_rules[ri]["description"] = desc

                # Dynamic params for max_dosage
                if rt == "max_dosage":
                    pc1, pc2 = st.columns(2)
                    with pc1:
                        max_mg = st.number_input("Max mg", min_value=0, value=4000, key=f"g_maxmg_{ri}")
                    with pc2:
                        per = st.text_input("Per", value="day", key=f"g_per_{ri}")
                    st.session_state.new_guideline_rules[ri]["params"] = {"max_mg": max_mg, "per": per}
                elif rt == "interaction":
                    interacts_with = st.text_input("Interacts with (drug name)", key=f"g_iw_{ri}")
                    st.session_state.new_guideline_rules[ri]["params"] = {"interacts_with": interacts_with}
                elif rt == "contraindication":
                    condition = st.text_input("Contraindicated in (condition)", key=f"g_cond_{ri}")
                    st.session_state.new_guideline_rules[ri]["params"] = {"condition": condition}

                if len(st.session_state.new_guideline_rules) > 1:
                    if st.button("Remove Rule", key=f"g_rm_rule_{ri}"):
                        st.session_state.new_guideline_rules.pop(ri)
                        st.rerun()

            if st.button("+ Add Rule"):
                st.session_state.new_guideline_rules.append({"rule_type": "max_dosage", "description": "", "params": {}})
                st.rerun()

            if st.button("Save Guideline", type="primary"):
                if not g_name.strip():
                    st.error("Guideline name is required.")
                else:
                    payload = {
                        "name": g_name.strip(),
                        "category": g_category,
                        "drug_name": g_drug.strip() if g_drug.strip() else None,
                        "rules": st.session_state.new_guideline_rules,
                        "is_active": True,
                    }
                    with st.spinner("Saving..."):
                        data, status = api_client.create_guideline(payload)
                    if status in (200, 201):
                        st.success("Guideline created!")
                        st.session_state.new_guideline_rules = [{"rule_type": "max_dosage", "description": "", "params": {}}]
                        st.rerun()
                    else:
                        st.error(data.get("message", "Failed to create guideline."))

    # ── List guidelines ───────────────────────────────────────────────────────
    st.markdown("### Active Guidelines")
    cat_filter = st.selectbox("Filter by Category", ["All", "dosage", "interaction", "contraindication", "general"])

    with st.spinner("Loading guidelines..."):
        data, status = api_client.list_guidelines(
            category=None if cat_filter == "All" else cat_filter
        )

    if status != 200:
        st.error(data.get("message", "Failed to load guidelines."))
        return

    guidelines = data if isinstance(data, list) else data.get("guidelines", [])
    st.caption(f"{len(guidelines)} guidelines")

    if not guidelines:
        st.info("No guidelines found.")
        return

    cat_icon = {"dosage": "💊", "interaction": "⚡", "contraindication": "🚫", "general": "📋"}

    for g in guidelines:
        g_id = str(g.get("_id") or g.get("id", ""))
        g_name = g.get("name", "Unnamed")
        g_cat = g.get("category", "general")
        g_drug = g.get("drug_name", "")
        rules = g.get("rules", [])

        with st.expander(f"{cat_icon.get(g_cat, '📋')} {g_name} [{g_cat}]{' — ' + g_drug if g_drug else ''}"):
            st.caption(f"ID: {g_id[:16]}... | Rules: {len(rules)}")
            for r in rules:
                st.markdown(f"- **{r.get('rule_type', '')}**: {r.get('description', '')}")
                params = r.get("params", {})
                if params:
                    st.caption(f"  Params: {params}")

            if role == "admin":
                del_col, _ = st.columns([1, 4])
                with del_col:
                    if st.button("🗑 Delete", key=f"g_del_{g_id}"):
                        dr, ds = api_client.delete_guideline(g_id)
                        if ds == 200:
                            st.success("Guideline deleted.")
                            st.rerun()
                        else:
                            st.error(dr.get("message", "Delete failed."))
