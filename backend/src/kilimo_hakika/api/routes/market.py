"""Supplier-declared prices and demand/supply signals.

Every response carries `price_authority: "SUPPLIER_DECLARED"` and the publishing
organisation's name. These are not statutory numbers and the API never lets them
look like ones - see CLAUDE.md invariant 2.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from ...persistence import db
from ..deps import Caller, require

router = APIRouter()

DISCLAIMER = {
    "en": "Prices set by the seller or association shown. These are not government prices.",
    "sw": "Bei zilizowekwa na muuzaji au chama kilichoonyeshwa. Hizi si bei za serikali.",
}


@router.get("/market/prices")
def prices(
    caller: Annotated[Caller, Depends(require("market.read"))],
    product: str | None = Query(default=None),
    county: str | None = Query(default=None),
    kind: str | None = Query(default=None, pattern="^(RETAIL|WHOLESALE)$"),
    on: date | None = Query(default=None),
    lang: str = Query(default="en", pattern="^(en|sw)$"),
) -> dict[str, Any]:
    as_of = on or date.today()
    with db.user_connection(caller.claims) as conn, conn.cursor() as cur:
        cur.execute(
            """
            select q.id::text as id, q.product_code, p.name_en, p.name_sw,
                   q.price_kes, q.unit, q.quote_kind, q.county_code,
                   q.valid_from, q.valid_to, q.price_authority, q.note_en, q.note_sw,
                   o.id::text as org_id, o.name as org_name, o.kind as org_kind, o.status as org_status
              from market.price_quote q
              join market.product p on p.code = q.product_code
              join identity.organisation o on o.id = q.organisation_id
             where q.status = 'PUBLISHED'
               and %s between q.valid_from and q.valid_to
               and (%s::text is null or q.product_code = %s)
               and (%s::text is null or q.county_code = %s)
               and (%s::text is null or q.quote_kind = %s)
             order by q.price_kes asc
            """,
            (as_of, product, product, county, county, kind, kind),
        )
        rows = cur.fetchall()

    return {
        "as_of": as_of.isoformat(),
        "disclaimer": DISCLAIMER.get(lang, DISCLAIMER["en"]),
        "quotes": [
            {
                "id": row["id"],
                "product_code": row["product_code"],
                "product_name": row["name_sw"] if lang == "sw" else row["name_en"],
                "price_kes": float(row["price_kes"]),
                "unit": row["unit"],
                "quote_kind": row["quote_kind"],
                "county_code": row["county_code"],
                "valid_from": row["valid_from"].isoformat(),
                "valid_to": row["valid_to"].isoformat(),
                "price_authority": row["price_authority"],
                "note": row["note_sw"] if lang == "sw" else row["note_en"],
                "organisation": {
                    "id": row["org_id"],
                    "name": row["org_name"],
                    "kind": row["org_kind"],
                    "status": row["org_status"],
                },
            }
            for row in rows
        ],
    }


@router.get("/market/signals")
def signals(
    caller: Annotated[Caller, Depends(require("market.read"))],
    product: str | None = Query(default=None),
    county: str | None = Query(default=None),
    lang: str = Query(default="en", pattern="^(en|sw)$"),
) -> dict[str, Any]:
    with db.user_connection(caller.claims) as conn, conn.cursor() as cur:
        cur.execute(
            """
            select s.id::text as id, s.direction, s.product_code, s.county_code,
                   s.period_start, s.period_end, s.quantity, s.unit,
                   s.headline_en, s.headline_sw, s.detail_en, s.detail_sw, s.published_at,
                   o.id::text as org_id, o.name as org_name, o.kind as org_kind, o.status as org_status
              from market.signal s
              join identity.organisation o on o.id = s.organisation_id
             where s.status = 'PUBLISHED'
               and (%s::text is null or s.product_code = %s)
               and (%s::text is null or s.county_code = %s)
             order by s.period_start asc
            """,
            (product, product, county, county),
        )
        rows = cur.fetchall()

    return {
        "signals": [
            {
                "id": row["id"],
                "direction": row["direction"],
                "product_code": row["product_code"],
                "county_code": row["county_code"],
                "period_start": row["period_start"].isoformat(),
                "period_end": row["period_end"].isoformat(),
                "quantity": float(row["quantity"]) if row["quantity"] is not None else None,
                "unit": row["unit"],
                "headline": row["headline_sw"] if lang == "sw" else row["headline_en"],
                "detail": row["detail_sw"] if lang == "sw" else row["detail_en"],
                "published_at": row["published_at"].isoformat() if row["published_at"] else None,
                "organisation": {
                    "id": row["org_id"],
                    "name": row["org_name"],
                    "kind": row["org_kind"],
                    "status": row["org_status"],
                },
            }
            for row in rows
        ]
    }
