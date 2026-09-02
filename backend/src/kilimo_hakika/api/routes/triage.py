"""POST /api/v1/triage - the verdict.

This is where the clock lives. The engine takes the travel date as an argument;
resolving "today" is an API concern, and the resolved date is always echoed back
so the result screen shows what was actually evaluated.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, status

from ...engine import LandTenure, TriageInput, evaluate
from ...packs.repository import repository
from ...persistence import db, triage_log
from ..deps import OptionalCallerDep
from ..schemas import TriageRequest, serialise_triage

log = logging.getLogger(__name__)
router = APIRouter()

NAIROBI = ZoneInfo("Africa/Nairobi")
MAX_TRAVEL_HORIZON_DAYS = 90


def today_in_nairobi() -> date:
    return datetime.now(NAIROBI).date()


def _load_profile(user_id: str) -> dict[str, Any]:
    with db.admin_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select registration_county_code, default_acreage_acres, land_tenure, kiamis_registered
              from identity.farmer_profile where user_id = %s
            """,
            (user_id,),
        )
        return cur.fetchone() or {}


@router.post("/triage")
def run_triage(
    body: TriageRequest,
    caller: OptionalCallerDep,
    lang: str = Query(default="en", pattern="^(en|sw)$"),
    trace: bool = Query(default=False),
) -> dict[str, Any]:
    loaded = repository.current
    if loaded is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "NO_ACTIVE_PACK",
                    "message": "no published rules are loaded; do not travel on this app's word",
                }
            },
        )

    profile = _load_profile(caller.user_id) if caller else {}

    acreage = body.acreage_acres or profile.get("default_acreage_acres")
    if acreage is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_INPUT",
                    "message": "acreage_acres is required (or save it on your profile)",
                    "field": "acreage_acres",
                }
            },
        )

    travel_date = body.travel_date or today_in_nairobi()
    horizon = today_in_nairobi()
    if travel_date < horizon or travel_date > horizon + timedelta(days=MAX_TRAVEL_HORIZON_DAYS):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "TRAVEL_DATE_OUT_OF_RANGE",
                    "message": f"pick a date between today and {MAX_TRAVEL_HORIZON_DAYS} days ahead",
                    "field": "travel_date",
                }
            },
        )

    tenure = body.land_tenure or profile.get("land_tenure") or "UNKNOWN"
    county = body.registration_county_code or profile.get("registration_county_code")

    triage_input = TriageInput(
        acreage_acres=Decimal(str(acreage)),
        depot_code=body.depot_code,
        held_documents=frozenset(body.held_documents),
        travel_date=travel_date,
        land_tenure=LandTenure(tenure),
        registration_county_code=county,
        collecting_in_person=body.collecting_in_person,
        fertilizer_code=body.fertilizer_code,
    )

    result = evaluate(loaded.pack, triage_input, locale=lang)

    history_id: str | None = None
    if caller is not None:
        if not caller.has("triage.run"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "this action needs the triage.run permission",
                        "permission": "triage.run",
                    }
                },
            )
        _, history_id = triage_log.record(
            user_id=caller.user_id,
            claims=caller.claims,
            triage_input=triage_input,
            result=result,
            pack_version=loaded.pack.version,
        )
    else:
        # Anonymous check: still logged for engine correctness, with no user link.
        triage_log.record_anonymous(
            triage_input=triage_input, result=result, pack_version=loaded.pack.version
        )

    return serialise_triage(
        result,
        pack_source=loaded.source,
        environment=loaded.pack.environment,
        history_id=history_id,
        include_trace=trace,
    )
