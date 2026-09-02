"""Development auth: phone OTP for farmers, email + TOTP for staff.

This stands in for Supabase Auth so the whole stack is testable locally. The
claim shape, the RLS behaviour and the frontend flow are all identical to what
Supabase will produce; swapping over replaces these routes and `security.verify`
and touches nothing else.

Everything here is gated on DEV_AUTH_ENABLED and refuses to run in production.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, status

from ...persistence import db
from ...settings import get_settings
from .. import security
from ..deps import CallerDep, load_permissions
from ..schemas import OtpStartRequest, OtpVerifyRequest, StaffLoginRequest

log = logging.getLogger(__name__)
router = APIRouter()

OTP_TTL = timedelta(minutes=10)
MAX_OTP_ATTEMPTS = 5
SHARED_DEVICE_TTL_SECONDS = 1_800  # 30 minutes, no refresh - see auth-and-roles.md §1
PHONE_RE = re.compile(r"^\+?[0-9]{9,15}$")


def _guard_dev_auth() -> None:
    settings = get_settings()
    if not settings.dev_auth_enabled or settings.app_env == "production":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "dev auth is disabled"}},
        )


def _normalise_phone(raw: str) -> str:
    phone = raw.strip().replace(" ", "")
    if phone.startswith("0"):
        phone = "+254" + phone[1:]  # Kenyan local form
    if not phone.startswith("+"):
        phone = "+" + phone
    if not PHONE_RE.match(phone):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_INPUT",
                    "message": "enter a phone number like 0712345678",
                    "field": "phone",
                }
            },
        )
    return phone


@router.post("/auth/otp/start")
def otp_start(body: OtpStartRequest) -> dict[str, Any]:
    _guard_dev_auth()
    settings = get_settings()
    phone = _normalise_phone(body.phone)

    with db.admin_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            insert into auth.otp_challenge (phone, code_hash, expires_at)
            values (%s, %s, %s)
            """,
            (phone, security.hash_secret(settings.dev_otp_code), datetime.now(UTC) + OTP_TTL),
        )

    # In production this is an SMS with a real cost per send, which is why
    # sessions are long-lived (see auth-and-roles.md §1).
    log.info("OTP issued for %s (dev code)", phone)
    return {
        "sent": True,
        "phone": phone,
        "expires_in": int(OTP_TTL.total_seconds()),
        "dev_hint": f"development mode: the code is {settings.dev_otp_code}",
    }


@router.post("/auth/otp/verify")
def otp_verify(body: OtpVerifyRequest) -> dict[str, Any]:
    _guard_dev_auth()
    phone = _normalise_phone(body.phone)

    with db.admin_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select id, code_hash, attempts, expires_at, consumed_at
              from auth.otp_challenge
             where phone = %s
             order by created_at desc
             limit 1
            """,
            (phone,),
        )
        challenge = cur.fetchone()

        if challenge is None or challenge["consumed_at"] is not None:
            raise _bad_otp("request a new code")
        if challenge["expires_at"] < datetime.now(UTC):
            raise _bad_otp("that code has expired")
        if challenge["attempts"] >= MAX_OTP_ATTEMPTS:
            raise _bad_otp("too many attempts; request a new code")

        if not security.verify_secret(body.code, challenge["code_hash"]):
            cur.execute(
                "update auth.otp_challenge set attempts = attempts + 1 where id = %s",
                (challenge["id"],),
            )
            raise _bad_otp("that code is not right")

        cur.execute("update auth.otp_challenge set consumed_at = now() where id = %s", (challenge["id"],))

        # The signup trigger creates identity.app_user and the farmer role.
        cur.execute(
            """
            insert into auth.users (phone) values (%s)
            on conflict (phone) do update set last_sign_in_at = now()
            returning id
            """,
            (phone,),
        )
        user_id = str(cur.fetchone()["id"])

        # Account consent is implicit in creating an account; everything else is
        # opt-in, and ASSISTANT_AI in particular gates all model calls.
        cur.execute(
            """
            insert into identity.consent (user_id, purpose, policy_version)
            values (%s, 'ACCOUNT', '2026-09-01')
            on conflict do nothing
            """,
            (user_id,),
        )

    token, ttl = security.issue(user_id)
    if body.shared_device:
        # "This is not my phone": a short session with no refresh, so nothing is
        # left behind on a borrowed handset.
        token, _ = security.issue(user_id, extra={"shared_device": True})
        ttl = SHARED_DEVICE_TTL_SECONDS

    return {"access_token": token, "token_type": "bearer", "expires_in": ttl, "user_id": user_id}


def _bad_otp(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": "UNAUTHENTICATED", "message": message}},
    )


@router.post("/auth/staff/login")
def staff_login(body: StaffLoginRequest) -> dict[str, Any]:
    """Email + password, with the TOTP step that unlocks aal2.

    Publishing a price or touching policy needs aal2. Password alone reads those
    consoles; it does not write to them.
    """
    _guard_dev_auth()
    settings = get_settings()
    email = body.email.strip().lower()

    with db.admin_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select id, encrypted_password, raw_user_meta_data from auth.users where email = %s",
            (email,),
        )
        user = cur.fetchone()

    if user is None or not user["encrypted_password"]:
        raise _bad_credentials()
    if not security.verify_secret(body.password, user["encrypted_password"]):
        raise _bad_credentials()

    aal = "aal1"
    mfa_enrolled = bool((user["raw_user_meta_data"] or {}).get("mfa_enrolled"))
    if mfa_enrolled and body.totp_code:
        if body.totp_code != settings.dev_otp_code:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {"code": "UNAUTHENTICATED", "message": "that second factor is not right"}},
            )
        aal = "aal2"

    user_id = str(user["id"])
    token, ttl = security.issue(user_id, aal=aal)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": ttl,
        "user_id": user_id,
        "aal": aal,
        "mfa_enrolled": mfa_enrolled,
    }


def _bad_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": "UNAUTHENTICATED", "message": "email or password is wrong"}},
    )


@router.get("/me")
def me(caller: CallerDep) -> dict[str, Any]:
    permissions, _, _ = load_permissions(caller.user_id)

    with db.user_connection(caller.claims) as conn, conn.cursor() as cur:
        cur.execute(
            "select display_name, locale, status from identity.app_user where id = %s",
            (caller.user_id,),
        )
        profile_row = cur.fetchone() or {}

        cur.execute(
            """
            select registration_county_code, default_acreage_acres, land_tenure,
                   kiamis_registered, national_id_hmac is not null as national_id_on_file
              from identity.farmer_profile where user_id = %s
            """,
            (caller.user_id,),
        )
        farmer = cur.fetchone()

        cur.execute(
            """
            select purpose, withdrawn_at is null as granted
              from identity.consent where user_id = %s
            """,
            (caller.user_id,),
        )
        consents = {row["purpose"]: row["granted"] for row in cur.fetchall()}

        cur.execute(
            """
            select o.id::text as id, o.name, o.kind, o.status,
                   array_agg(m.role_code order by m.role_code) as roles
              from identity.membership m
              join identity.organisation o on o.id = m.organisation_id
             where m.user_id = %s and m.revoked_at is null
             group by o.id, o.name, o.kind, o.status
            """,
            (caller.user_id,),
        )
        organisations = cur.fetchall()

        cur.execute(
            """
            select array_agg(distinct m.role_code) as roles
              from identity.membership m
             where m.user_id = %s and m.revoked_at is null
            """,
            (caller.user_id,),
        )
        roles = (cur.fetchone() or {}).get("roles") or []

    return {
        "user_id": caller.user_id,
        "display_name": profile_row.get("display_name"),
        "locale": profile_row.get("locale", "en"),
        "status": profile_row.get("status", "ACTIVE"),
        "roles": sorted(roles),
        "permissions": sorted(permissions),
        "organisations": organisations,
        "aal": caller.aal,
        "shared_device": bool(caller.claims.get("shared_device")),
        "consents": {
            purpose: consents.get(purpose, False)
            for purpose in ("ACCOUNT", "ASSISTANT_AI", "ANALYTICS", "MARKET_NOTIFICATIONS")
        },
        "farmer_profile": {
            "registration_county_code": farmer.get("registration_county_code") if farmer else None,
            "default_acreage_acres": float(farmer["default_acreage_acres"])
            if farmer and farmer.get("default_acreage_acres") is not None
            else None,
            "land_tenure": farmer.get("land_tenure") if farmer else None,
            "kiamis_registered": farmer.get("kiamis_registered") if farmer else None,
            "national_id_on_file": farmer.get("national_id_on_file") if farmer else False,
        }
        if farmer
        else None,
    }
