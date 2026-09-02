"""The assistant's tools. All four are read-only.

There is no write tool, so no conversation can change state. `get_triage_verdict`
is the seam to the deterministic core: it runs the same engine the API runs and
returns the verdict verbatim, recording the `kh.triage_log` id so any answer
that mentions a verdict is traceable to the engine run behind it.
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from ..engine import LandTenure, TriageInput, evaluate
from ..packs.repository import repository
from ..persistence import db, triage_log
from . import corpus

log = logging.getLogger(__name__)
NAIROBI = ZoneInfo("Africa/Nairobi")

DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "get_triage_verdict",
        "description": (
            "Run the official depot check and return the verdict. Use this whenever the farmer "
            "asks whether they can travel, whether they will be served, what they are missing, "
            "or what it will cost. You must never state a verdict without calling this first."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "depot_code": {"type": "string", "description": "Depot code, e.g. NCPB-NAKURU"},
                "held_documents": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Document codes the farmer says they are holding",
                },
                "acreage_acres": {
                    "type": ["number", "null"],
                    "description": "Acres; null to use the saved profile",
                },
            },
            "required": ["depot_code", "held_documents", "acreage_acres"],
        },
    },
    {
        "name": "search_policy",
        "description": "Keyword search the official rules, cited sources and document guidance.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "get_document_guidance",
        "description": "How to obtain one required artifact, by document code.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"document_code": {"type": "string"}},
            "required": ["document_code"],
        },
    },
]


def execute(
    name: str, args: dict[str, Any], *, user_id: str | None, claims: dict[str, Any], locale: str
) -> tuple[dict[str, Any], str | None]:
    """Run a tool. Returns (result payload, triage_log_id if any)."""
    if name == "get_triage_verdict":
        return _triage(args, user_id=user_id, claims=claims, locale=locale)
    if name == "search_policy":
        hits = corpus.search(str(args.get("query", "")), locale=locale)
        return {
            "results": [
                {
                    "source_kind": h["source_kind"],
                    "source_ref": h["source_ref"],
                    "title": h["title"],
                    "content": h["content"],
                    "citation": h["citation_id"],
                }
                for h in hits
            ]
        }, None
    if name == "get_document_guidance":
        return _document(str(args.get("document_code", "")), locale), None
    return {"error": f"unknown tool {name}"}, None


def _triage(
    args: dict[str, Any], *, user_id: str | None, claims: dict[str, Any], locale: str
) -> tuple[dict[str, Any], str | None]:
    # A verdict is drawn from the caller's own saved profile, so there is no
    # such thing as an anonymous one here. The scope layer does not offer this
    # tool to a signed-out visitor; this is the second lock.
    if not user_id:
        return {"error": "a depot check needs an account; the free check on the site does not"}, None
    loaded = repository.current
    if loaded is None:
        return {"error": "no rules are loaded, so no verdict can be given"}, None

    with db.admin_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select registration_county_code, default_acreage_acres, land_tenure
              from identity.farmer_profile where user_id = %s
            """,
            (user_id,),
        )
        profile = cur.fetchone() or {}

    acreage = args.get("acreage_acres") or profile.get("default_acreage_acres")
    if acreage is None:
        return {
            "error": "no acreage available",
            "ask_the_farmer": "How many acres are you planting this season?",
        }, None

    triage_input = TriageInput(
        acreage_acres=Decimal(str(acreage)),
        depot_code=str(args.get("depot_code", "")),
        held_documents=frozenset(args.get("held_documents") or []),
        travel_date=datetime.now(NAIROBI).date(),
        land_tenure=LandTenure(profile.get("land_tenure") or "UNKNOWN"),
        registration_county_code=profile.get("registration_county_code"),
    )
    result = evaluate(loaded.pack, triage_input, locale=locale)
    log_id, _ = triage_log.record(
        user_id=user_id,
        claims=claims,
        triage_input=triage_input,
        result=result,
        pack_version=loaded.pack.version,
        client_kind="assistant",
    )

    return {
        "verdict": str(result.verdict),
        "reason_kind": str(result.reason_kind),
        "headline": result.headline,
        "missing": [
            {"document_code": b.document_code, "label": b.label, "why": b.message, "citation": b.citation}
            for b in result.blockers
        ],
        "advisories": [
            {"code": a.code, "message": a.message, "citation": a.citation} for a in result.advisories
        ],
        "allocation": None
        if result.allocation is None
        else {
            "total_bags": result.allocation.total_bags,
            "planting_bags": result.allocation.planting_bags,
            "topdress_bags": result.allocation.topdress_bags,
            "citation": result.allocation.citation,
        },
        "official_min_total_kes": None
        if result.costing is None or result.costing.min_total_cost_kes is None
        else float(result.costing.min_total_cost_kes),
        "depot": None if result.depot is None else result.depot.name,
    }, log_id


def _document(code: str, locale: str) -> dict[str, Any]:
    loaded = repository.current
    if loaded is None:
        return {"error": "no rules loaded"}
    doc = loaded.pack.documents.get(code)
    if doc is None:
        return {"error": f"no document {code}", "known": sorted(loaded.pack.documents)}
    from ..engine.pack import _text

    return {
        "document_code": doc.code,
        "label": _text(doc.label, locale),
        "how_to_obtain": _text(doc.how_to_obtain, locale),
        "is_physical": doc.is_physical,
    }
