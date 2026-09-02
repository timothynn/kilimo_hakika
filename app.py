"""Kilimo Hakika (DepotReady) - 3-step depot readiness wizard.

All scheme, depot and document options are read from scheme_rules.json at run
time; every verdict shown here comes from validation_engine.run_triage().
"""

from pathlib import Path

import streamlit as st

from validation_engine import DO_NOT_TRAVEL, load_rules, run_triage

RULES_PATH = str(Path(__file__).with_name("scheme_rules.json"))

st.set_page_config(page_title="Kilimo Hakika - DepotReady", page_icon="🌾")

rules = load_rules(RULES_PATH)
schemes = rules["schemes"]
depots = rules["depots"]


def start_over() -> None:
    """Clear every stored answer and return to step 1."""
    st.session_state.clear()
    st.session_state["step"] = 1


st.session_state.setdefault("step", 1)

# Guard against arriving at a later step without the answers it needs.
if st.session_state["step"] >= 2 and "scheme_id" not in st.session_state:
    st.session_state["step"] = 1
if st.session_state["step"] >= 3 and "held_docs" not in st.session_state:
    st.session_state["step"] = 2

step = st.session_state["step"]

st.title("🌾 Kilimo Hakika")
st.caption("DepotReady - subsidy collection triage. SAMPLE DATA for demo purposes.")

if step == 1:
    st.subheader("Step 1 of 3 - Scheme, depot and acreage")

    scheme_id = st.selectbox(
        "Subsidy scheme",
        list(schemes),
        format_func=lambda sid: f"{schemes[sid]['name']} - {sid}",
        key="in_scheme",
    )
    depot = st.selectbox(
        "Collection depot",
        list(depots),
        format_func=lambda did: f"{depots[did]['name']} - {depots[did]['county']} County",
        key="in_depot",
    )
    acreage = st.number_input(
        "Registered acreage (acres)",
        min_value=0.0,
        max_value=1000.0,
        value=1.0,
        step=0.25,
        key="in_acreage",
    )

    if st.button("Next: documents", type="primary"):
        st.session_state["scheme_id"] = scheme_id
        st.session_state["depot"] = depot
        st.session_state["acreage"] = float(acreage)
        st.session_state["step"] = 2
        st.rerun()

elif step == 2:
    scheme = schemes[st.session_state["scheme_id"]]
    st.subheader("Step 2 of 3 - Documents in hand")
    st.write(f"Documents required by **{scheme['name']}**:")

    held_docs = [
        document
        for index, document in enumerate(scheme["required_documents"])
        if st.checkbox(document, key=f"doc_{index}")
    ]

    left, right = st.columns(2)
    if left.button("Check depot readiness", type="primary"):
        st.session_state["held_docs"] = held_docs
        st.session_state["step"] = 3
        st.rerun()
    right.button("Start Over", on_click=start_over)

else:
    st.subheader("Step 3 of 3 - Result")

    try:
        result = run_triage(
            scheme_id=st.session_state["scheme_id"],
            acreage=st.session_state["acreage"],
            depot=st.session_state["depot"],
            held_docs=st.session_state["held_docs"],
            rules=rules,
        )
    except ValueError as error:
        st.error(f"🛑 Cannot issue a verdict: {error}. Please start over.")
        st.button("Start Over", on_click=start_over)
        st.stop()

    if result["status"] == DO_NOT_TRAVEL:
        st.error("🛑 **DO NOT TRAVEL** - your documents are incomplete.")
        st.write("**Missing documents:**")
        for document in result["missing_documents"]:
            st.write(f"- {document}")
    else:
        st.success("✅ **PROCEED** - all required documents are in hand.")

    if result["tier_matched"]:
        bags, cost = st.columns(2)
        unit = "bag" if result["bag_cap"] == 1 else "bags"
        bags.metric("Bag cap", f"{result['bag_cap']} {unit}")
        cost.metric("Total cost", f"KES {result['total_cost_kes']:,}")
    else:
        st.warning(
            "⚠️ **Manual review required** - the acreage entered falls outside "
            "every tier defined for this scheme, so no bag cap can be issued "
            "automatically. Visit the sub-county agriculture office."
        )

    depot = depots[st.session_state["depot"]]
    st.write(
        f"**Scheme:** {schemes[st.session_state['scheme_id']]['name']}  \n"
        f"**Depot:** {depot['name']}, {depot['county']} County  \n"
        f"**Acreage:** {st.session_state['acreage']:g} acres"
    )
    st.caption(
        f"Source: {result['source_circular']} - SAMPLE DATA for demo purposes."
    )

    st.button("Start Over", on_click=start_over)
