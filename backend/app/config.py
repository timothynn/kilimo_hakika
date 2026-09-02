"""Application-level settings and the fixed compliance boundary of this service."""

from __future__ import annotations

from pathlib import Path

APP_NAME = "Kilimo Hakika (DepotReady)"
APP_VERSION = "1.0.0"
APP_SUMMARY = (
    "Deterministic Government Subsidy & Depot Triage Engine for Kenyan farmers."
)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

COUNTIES_FILE = DATA_DIR / "counties.json"
SCHEME_RULES_FILE = DATA_DIR / "scheme_rules.json"
DEPOTS_FILE = DATA_DIR / "ncpb_depots.json"

# CORS is deliberately open. The frontend folder is still empty, so no dev port
# is known yet; the service exposes only public statutory reference data and
# holds no credentials, sessions or personal records.
CORS_ALLOW_ORIGINS = ["*"]

# The three hard track constraints. Surfaced on /health and on every triage
# response so the boundary is visible to any client, not just documented.
TRACK_CONSTRAINTS = {
    "no_agronomic_advice": (
        "This service issues no crop, soil, seed or fertilizer recommendations. "
        "It reports statutory entitlement, mandatory paperwork and NCPB depot "
        "readiness only. Agronomic guidance must come from your Ward "
        "Agricultural Officer."
    ),
    "no_payments": (
        "No financial transactions of any kind. No M-Pesa, mobile money, card "
        "or banking integration exists. Published prices are statutory figures "
        "only; payment happens in person at the NCPB depot counter."
    ),
    "no_marketplace": (
        "No buying, selling, bidding or third-party vendor listings. Only "
        "gazetted Government (NCPB) depots are listed."
    ),
}
