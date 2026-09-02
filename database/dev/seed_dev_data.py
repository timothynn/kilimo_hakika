#!/usr/bin/env python
"""DEV ONLY. Seed staff accounts, organisations, market data and the chat prompt.

Run from the backend so it can reuse the app's own password hashing - that way
the stored hashes are guaranteed to match what the login route verifies:

    cd backend
    DATABASE_URL=... uv run python ../database/dev/seed_dev_data.py

Idempotent: re-running updates rather than duplicating.
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta

import psycopg
from psycopg.rows import dict_row

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend", "src"))

from kilimo_hakika.api.security import hash_secret  # noqa: E402

STAFF_PASSWORD = "depot-dev-2026"

STAFF = [
    ("author@kilimohakika.test", "Policy Author", ["policy_author"], True),
    ("reviewer@kilimohakika.test", "Policy Reviewer", ["policy_reviewer"], True),
    ("publisher@kilimohakika.test", "Policy Publisher", ["policy_publisher"], True),
    ("admin@kilimohakika.test", "Platform Admin", ["platform_admin"], True),
    ("moderator@kilimohakika.test", "Moderator", ["moderator"], True),
    ("analyst@kilimohakika.test", "Analyst", ["analyst"], False),
]

ORG_STAFF = [
    ("agrovet@kilimohakika.test", "Agrovet Manager", "RETAIL", ["org_admin"], True),
    ("association@kilimohakika.test", "Association Officer", "SUPPLIER_ASSOCIATION", ["supplier_publisher"], True),
]

ORGS = [
    ("Rift Valley Agrovet", "RETAIL", "BRS-DEV-0001", "032"),
    ("Kenya Fertilizer Suppliers Association", "SUPPLIER_ASSOCIATION", "SOC-DEV-0002", "047"),
]

PRODUCTS = [
    ("DAP", "DAP (planting)", "DAP (kupanda)", "FERTILIZER", "DAP", "BAG_50KG"),
    ("CAN", "CAN (top dressing)", "CAN (kukuzia)", "FERTILIZER", "CAN", "BAG_50KG"),
    ("UREA", "Urea (top dressing)", "Urea (kukuzia)", "FERTILIZER", "UREA", "BAG_50KG"),
    ("NPK", "NPK (planting)", "NPK (kupanda)", "FERTILIZER", "NPK", "BAG_50KG"),
    ("MAIZE_GRAIN", "Maize grain", "Mahindi", "PRODUCE", None, "BAG_50KG"),
]

SYSTEM_PROMPT_NOTE = "Initial chat prompt. Guardrails live in assistant/client.py SYSTEM_PROMPT."


def main() -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        sys.exit("set DATABASE_URL")

    password_hash = hash_secret(STAFF_PASSWORD)

    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        cur = conn.cursor()

        # --- organisations -------------------------------------------------
        org_ids: dict[str, str] = {}
        for name, kind, reg, county in ORGS:
            cur.execute(
                """
                insert into identity.organisation (name, kind, registration_number, county_code, status)
                values (%s, %s, %s, %s, 'PENDING_VERIFICATION')
                on conflict (kind, registration_number) do update set name = excluded.name
                returning id::text as id
                """,
                (name, kind, reg, county),
            )
            org_ids[kind] = cur.fetchone()["id"]

        # --- staff and org users ------------------------------------------
        def upsert_user(email: str, display: str, mfa: bool) -> str:
            cur.execute(
                """
                insert into auth.users (email, encrypted_password, raw_user_meta_data)
                values (%s, %s, %s::jsonb)
                on conflict (email) do update set
                    encrypted_password = excluded.encrypted_password,
                    raw_user_meta_data = excluded.raw_user_meta_data
                returning id::text as id
                """,
                (email, password_hash, f'{{"display_name": "{display}", "mfa_enrolled": {str(mfa).lower()}}}'),
            )
            user_id = cur.fetchone()["id"]
            cur.execute(
                "update identity.app_user set display_name = %s where id = %s", (display, user_id)
            )
            return user_id

        def grant(user_id: str, role: str, org_id: str | None) -> None:
            cur.execute(
                """
                insert into identity.membership (user_id, organisation_id, role_code)
                values (%s, %s, %s)
                on conflict do nothing
                """,
                (user_id, org_id, role),
            )

        admin_id: str | None = None
        for email, display, roles, mfa in STAFF:
            user_id = upsert_user(email, display, mfa)
            for role in roles:
                grant(user_id, role, None)
            if "platform_admin" in roles:
                admin_id = user_id

        org_user_ids: dict[str, str] = {}
        for email, display, org_kind, roles, mfa in ORG_STAFF:
            user_id = upsert_user(email, display, mfa)
            for role in roles:
                grant(user_id, role, org_ids[org_kind])
            org_user_ids[org_kind] = user_id

        # --- verify the organisations (a moderator would normally do this) --
        for kind, org_id in org_ids.items():
            cur.execute(
                """
                update identity.organisation
                   set status = 'VERIFIED', verified_at = now(), verified_by = %s
                 where id = %s
                """,
                (admin_id, org_id),
            )

        # --- market catalogue and published data ---------------------------
        for code, en, sw, category, fert, unit in PRODUCTS:
            cur.execute(
                """
                insert into market.product (code, name_en, name_sw, category, fertilizer_code, default_unit)
                values (%s, %s, %s, %s, %s, %s)
                on conflict (code) do update set
                    name_en = excluded.name_en, name_sw = excluded.name_sw
                """,
                (code, en, sw, category, fert, unit),
            )

        today = date.today()
        valid_from, valid_to = today - timedelta(days=1), today + timedelta(days=45)

        # Commercial prices sit deliberately ABOVE the gazetted subsidy price -
        # that gap is the whole reason a farmer needs to know the official cap.
        quotes = [
            (org_ids["RETAIL"], org_user_ids["RETAIL"], "DAP", "RETAIL", 4100, "032", "Ex-store, Nakuru town"),
            (org_ids["RETAIL"], org_user_ids["RETAIL"], "CAN", "RETAIL", 3450, "032", None),
            (
                org_ids["SUPPLIER_ASSOCIATION"],
                org_user_ids["SUPPLIER_ASSOCIATION"],
                "DAP",
                "WHOLESALE",
                3800,
                None,
                "Member wholesale indication, 10 bags minimum",
            ),
            (
                org_ids["SUPPLIER_ASSOCIATION"],
                org_user_ids["SUPPLIER_ASSOCIATION"],
                "UREA",
                "WHOLESALE",
                4250,
                None,
                None,
            ),
        ]
        cur.execute("delete from market.price_quote")
        for org_id, author, product, kind, price, county, note in quotes:
            cur.execute(
                """
                insert into market.price_quote (
                    organisation_id, product_code, quote_kind, unit, price_kes, county_code,
                    valid_from, valid_to, status, created_by, published_by, published_at, note_en
                ) values (%s, %s, %s, 'BAG_50KG', %s, %s, %s, %s, 'PUBLISHED', %s, %s, now(), %s)
                """,
                (org_id, product, kind, price, county, valid_from, valid_to, author, author, note),
            )

        cur.execute("delete from market.signal")
        signals = [
            (
                "SUPPLY",
                "DAP",
                "026",
                today + timedelta(days=20),
                today + timedelta(days=80),
                12000,
                "Additional DAP stock expected in Trans Nzoia from mid-October",
                "Mbolea ya DAP ya nyongeza inatarajiwa Trans Nzoia kutoka katikati ya Oktoba",
            ),
            (
                "DEMAND",
                "MAIZE_GRAIN",
                "032",
                today,
                today + timedelta(days=60),
                None,
                "Strong demand for dry maize grain in Nakuru through the short rains",
                "Mahitaji makubwa ya mahindi kavu Nakuru katika msimu wa vuli",
            ),
        ]
        for direction, product, county, start, end, qty, head_en, head_sw in signals:
            cur.execute(
                """
                insert into market.signal (
                    organisation_id, direction, product_code, county_code, period_start, period_end,
                    quantity, unit, headline_en, headline_sw, status, created_by, published_by, published_at
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'PUBLISHED', %s, %s, now())
                """,
                (
                    org_ids["SUPPLIER_ASSOCIATION"],
                    direction,
                    product,
                    county,
                    start,
                    end,
                    qty,
                    "BAG_50KG" if qty else None,
                    head_en,
                    head_sw,
                    org_user_ids["SUPPLIER_ASSOCIATION"],
                    org_user_ids["SUPPLIER_ASSOCIATION"],
                ),
            )

        # --- assistant prompt version --------------------------------------
        cur.execute(
            """
            insert into ai.prompt_version (name, version, model, effort, system_prompt, notes, is_active)
            values ('assistant.chat', 1, 'claude-opus-5', 'low', %s, %s, true)
            on conflict (name, version) do update set
                model = excluded.model, effort = excluded.effort, is_active = true
            """,
            ("See kilimo_hakika.assistant.client.SYSTEM_PROMPT", SYSTEM_PROMPT_NOTE),
        )

        conn.commit()

    print("dev data seeded")
    print(f"  staff password: {STAFF_PASSWORD}  (TOTP code in dev = DEV_OTP_CODE)")
    print(f"  organisations: {', '.join(k for k in org_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
