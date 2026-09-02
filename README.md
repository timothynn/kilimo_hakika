# Kilimo Hakika (DepotReady)
Deterministic subsidy-collection triage: tells a farmer **PROCEED** or **DO NOT TRAVEL** before they spend money travelling to a depot. All figures in `scheme_rules.json` are **SAMPLE DATA for demo purposes** — not official MOALD figures.
- Verify the logic: `python3 validation_engine.py` → prints `3/3 PASS`
- Run the app: `.venv/bin/streamlit run app.py` (or `pip install streamlit && streamlit run app.py`)
- Every verdict is a direct read of `scheme_rules.json`; acreage outside all tiers is flagged for manual review, never estimated.
