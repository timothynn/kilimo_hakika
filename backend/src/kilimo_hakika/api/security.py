"""Token issuing and verification.

In development this backend issues its own tokens, standing in for Supabase
Auth. The claim shape is deliberately identical to Supabase's (`sub`, `role`,
`aal`, `iss`, `exp`), so RLS, permission checks and the frontend all behave the
same once Supabase takes over issuing. Moving over means replacing `verify()`
with a JWKS check and deleting the dev routes - nothing else.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from typing import Any

import jwt

from ..settings import get_settings

ALGORITHM = "HS256"
PBKDF2_ROUNDS = 240_000


class TokenError(Exception):
    pass


def issue(user_id: str, *, aal: str = "aal1", extra: dict[str, Any] | None = None) -> tuple[str, int]:
    settings = get_settings()
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": str(user_id),
        "role": "authenticated",
        "aal": aal,
        "iss": settings.jwt_issuer,
        "iat": now,
        "exp": now + settings.jwt_ttl_seconds,
    }
    if extra:
        claims.update(extra)
    return jwt.encode(claims, settings.jwt_secret, algorithm=ALGORITHM), settings.jwt_ttl_seconds


def verify(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[ALGORITHM],
            issuer=settings.jwt_issuer,
            options={"require": ["sub", "exp", "iss"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("token invalid") from exc
    if claims.get("role") != "authenticated":
        raise TokenError("unexpected role claim")
    return claims


def hash_secret(value: str) -> str:
    """PBKDF2-SHA256 with a per-value salt. Used for passwords and OTP codes."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", value.encode("utf-8"), salt, PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${salt.hex()}${digest.hex()}"


def verify_secret(value: str, encoded: str) -> bool:
    try:
        _, rounds, salt_hex, digest_hex = encoded.split("$")
        expected = hashlib.pbkdf2_hmac("sha256", value.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds))
    except Exception:
        return False
    return hmac.compare_digest(expected.hex(), digest_hex)


def hmac_national_id(national_id: str) -> bytes:
    """Keyed hash of an ID number. The plaintext is never stored.

    The pepper is the JWT secret here only because this is a dev build; in
    production it must be a separate secret held outside the database, so a
    database dump cannot be brute-forced against the (small) ID number space.
    """
    settings = get_settings()
    return hmac.new(
        settings.jwt_secret.encode("utf-8"), national_id.strip().encode("utf-8"), hashlib.sha256
    ).digest()
