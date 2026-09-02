"""Profile, consent, and the farmer's own triage history.

Every query here runs through `user_connection`, so RLS decides what the caller
can see. A bug in this file cannot leak another farmer's history.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from ...persistence import db
from ..deps import Caller, CallerDep, require
from ..schemas import ConsentRequest, GapStateRequest, ProfileRequest
from ..security import hmac_national_id

router = APIRouter()


@router.put("/me/profile")
def save_profile(
    body: ProfileRequest,
    caller: Annotated[Caller, Depends(require("profile.write.self"))],
) -> dict[str, Any]:
    national_id_hmac = hmac_national_id(body.national_id) if body.national_id else None

    with db.user_connection(caller.claims) as conn, conn.cursor() as cur:
        cur.execute(
            """
            insert into identity.farmer_profile (
                user_id, registration_county_code, default_acreage_acres,
                land_tenure, kiamis_registered, national_id_hmac
            ) values (%s, %s, %s, %s, %s, %s)
            on conflict (user_id) do update set
                registration_county_code = excluded.registration_county_code,
                default_acreage_acres    = excluded.default_acreage_acres,
                land_tenure              = excluded.land_tenure,
                kiamis_registered        = excluded.kiamis_registered,
                national_id_hmac         = coalesce(excluded.national_id_hmac,
                                                    identity.farmer_profile.national_id_hmac),
                updated_at               = now()
            returning registration_county_code, default_acreage_acres, land_tenure,
                      kiamis_registered, national_id_hmac is not null as national_id_on_file
            """,
            (
                caller.user_id,
                body.registration_county_code,
                body.default_acreage_acres,
                body.land_tenure,
                body.kiamis_registered,
                national_id_hmac,
            ),
        )
        row = cur.fetchone()

    return {
        "registration_county_code": row["registration_county_code"],
        "default_acreage_acres": float(row["default_acreage_acres"])
        if row["default_acreage_acres"] is not None
        else None,
        "land_tenure": row["land_tenure"],
        "kiamis_registered": row["kiamis_registered"],
        "national_id_on_file": row["national_id_on_file"],
    }


@router.put("/me/consent")
def set_consent(body: ConsentRequest, caller: CallerDep) -> dict[str, Any]:
    with db.user_connection(caller.claims) as conn, conn.cursor() as cur:
        if body.granted:
            cur.execute(
                """
                insert into identity.consent (user_id, purpose, policy_version)
                values (%s, %s, %s)
                on conflict (user_id, purpose, policy_version)
                  do update set withdrawn_at = null, granted_at = now()
                """,
                (caller.user_id, body.purpose, body.policy_version),
            )
        else:
            cur.execute(
                """
                update identity.consent set withdrawn_at = now()
                 where user_id = %s and purpose = %s and withdrawn_at is null
                """,
                (caller.user_id, body.purpose),
            )
    return {"purpose": body.purpose, "granted": body.granted}


@router.post("/me/erasure")
def request_erasure(caller: CallerDep) -> dict[str, Any]:
    with db.user_connection(caller.claims) as conn, conn.cursor() as cur:
        cur.execute(
            "insert into identity.erasure_request (user_id) values (%s) returning id::text, requested_at",
            (caller.user_id,),
        )
        row = cur.fetchone()
    return {
        "id": row["id"],
        "requested_at": row["requested_at"].isoformat(),
        "note": "Your history will be deleted. The anonymous engine record stays, with no link to you.",
    }


@router.get("/me/triage-history")
def triage_history(
    caller: Annotated[Caller, Depends(require("triage.history.read.self"))],
) -> dict[str, Any]:
    with db.user_connection(caller.claims) as conn, conn.cursor() as cur:
        cur.execute(
            """
            select id::text as history_id, created_at, verdict, depot_code, total_bags, gap_state
              from identity.triage_history
             where user_id = %s
             order by created_at desc
             limit 50
            """,
            (caller.user_id,),
        )
        rows = cur.fetchall()

    return {
        "items": [
            {
                "history_id": row["history_id"],
                "created_at": row["created_at"].isoformat(),
                "verdict": row["verdict"],
                "depot_code": row["depot_code"],
                "total_bags": row["total_bags"],
                "gap_state": row["gap_state"],
            }
            for row in rows
        ]
    }


@router.patch("/me/triage-history/{history_id}/gaps")
def update_gaps(history_id: str, body: GapStateRequest, caller: CallerDep) -> dict[str, Any]:
    """Tick off an artifact you have since obtained.

    This never changes a stored verdict. Re-running triage is what produces a
    new one - the checklist only records progress toward being able to.
    """
    with db.user_connection(caller.claims) as conn, conn.cursor() as cur:
        cur.execute(
            """
            update identity.triage_history
               set gap_state = gap_state || %s::jsonb, updated_at = now()
             where id = %s and user_id = %s
            returning gap_state
            """,
            (json.dumps(body.gap_state), history_id, caller.user_id),
        )
        row = cur.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "no such history entry"}},
        )
    return {"history_id": history_id, "gap_state": row["gap_state"]}
