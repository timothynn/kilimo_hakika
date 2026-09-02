"""Writing the two triage records.

`kh.triage_log` is the anonymous engine record - no user id, ever - and
`identity.triage_history` is the farmer's own view, linked to them. Erasure
deletes the second and leaves the first, so a farmer's right to be forgotten
never costs the ability to replay a disputed verdict.

Neither write may fail a request. A correct-but-unlogged verdict beats no verdict.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from ..engine import TriageInput, TriageResult
from ..settings import get_settings
from . import db

log = logging.getLogger(__name__)


def canonical_input(triage_input: TriageInput) -> str:
    """Stable JSON for hashing, so the same inputs always hash the same."""
    return json.dumps(
        {
            "acreage_acres": str(triage_input.acreage_acres),
            "depot_code": triage_input.depot_code,
            "held_documents": sorted(triage_input.held_documents),
            "land_tenure": str(triage_input.land_tenure),
            "travel_date": triage_input.travel_date.isoformat(),
            "registration_county_code": triage_input.registration_county_code,
            "collecting_in_person": triage_input.collecting_in_person,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def record_anonymous(*, triage_input: TriageInput, result: TriageResult, pack_version: str) -> str | None:
    """Log an anonymous check. The engine record has no user link by design."""
    return _write_engine_log(
        triage_input=triage_input, result=result, pack_version=pack_version, client_kind="web-anon"
    )


def _write_engine_log(
    *, triage_input: TriageInput, result: TriageResult, pack_version: str, client_kind: str
) -> str | None:
    if not get_settings().triage_log_enabled:
        return None
    payload = canonical_input(triage_input)
    try:
        with db.admin_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into kh.triage_log (
                    rule_pack_version, engine_version, input, input_hash,
                    verdict, reason_kind, blocker_codes, total_bags,
                    min_total_cost_kes, client_kind
                ) values (%s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s)
                returning id::text
                """,
                (
                    pack_version,
                    "1.0.0",
                    payload,
                    hashlib.sha256(payload.encode("utf-8")).hexdigest(),
                    str(result.verdict),
                    str(result.reason_kind),
                    list(result.blocker_codes),
                    result.allocation.total_bags if result.allocation else None,
                    result.costing.min_total_cost_kes if result.costing else None,
                    client_kind,
                ),
            )
            return cur.fetchone()["id"]
    except Exception as exc:
        log.warning("could not write the anonymous triage log: %s", exc)
        return None


def record(
    *,
    user_id: str,
    claims: dict[str, Any],
    triage_input: TriageInput,
    result: TriageResult,
    pack_version: str,
    client_kind: str = "web",
) -> tuple[str | None, str | None]:
    log_id = _write_engine_log(
        triage_input=triage_input, result=result, pack_version=pack_version, client_kind=client_kind
    )
    if log_id is None:
        return None, None

    try:
        with db.user_connection(claims) as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into identity.triage_history (
                    user_id, triage_log_id, verdict, depot_code, total_bags, gap_state
                ) values (%s, %s, %s, %s, %s, %s::jsonb)
                returning id::text
                """,
                (
                    user_id,
                    log_id,
                    str(result.verdict),
                    triage_input.depot_code,
                    result.allocation.total_bags if result.allocation else None,
                    json.dumps({b.document_code: "PENDING" for b in result.blockers if b.document_code}),
                ),
            )
            return log_id, cur.fetchone()["id"]
    except Exception as exc:
        log.warning("could not write triage history: %s", exc)
        return log_id, None
