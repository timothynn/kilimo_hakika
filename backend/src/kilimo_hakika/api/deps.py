"""Request dependencies: who is calling, and may they do this.

Two layers of authorization, in this order:
  1. `require("<permission>")` here, which produces a clear 403 naming the
     missing permission.
  2. RLS in the database, which holds if this layer has a bug.

Authorization reads the membership table, never the token's own claims, so a
revoked grant takes effect immediately instead of at token expiry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, status

from ..persistence import db
from ..settings import get_settings
from . import security


@dataclass(frozen=True, slots=True)
class Caller:
    user_id: str
    claims: dict[str, Any]
    permissions: frozenset[str]
    roles: frozenset[str]
    organisation_ids: frozenset[str]
    aal: str

    def has(self, permission: str) -> bool:
        return permission in self.permissions


def _unauthenticated(detail: str = "authentication required") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": "UNAUTHENTICATED", "message": detail}},
        headers={"WWW-Authenticate": "Bearer"},
    )


def load_permissions(user_id: str) -> tuple[frozenset[str], frozenset[str], frozenset[str]]:
    with db.admin_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select coalesce(array_agg(distinct rp.permission_code), '{}') as permissions,
                   coalesce(array_agg(distinct m.role_code), '{}')          as roles
              from identity.membership m
              join identity.role_permission rp on rp.role_code = m.role_code
             where m.user_id = %s and m.revoked_at is null
            """,
            (user_id,),
        )
        row = cur.fetchone() or {}
        permissions = row.get("permissions") or []
        roles = row.get("roles") or []

        cur.execute(
            """
            select coalesce(array_agg(distinct m.organisation_id::text), '{}') as orgs
              from identity.membership m
              join identity.organisation o on o.id = m.organisation_id
             where m.user_id = %s and m.revoked_at is null and o.status = 'VERIFIED'
            """,
            (user_id,),
        )
        orgs = (cur.fetchone() or {}).get("orgs") or []
    return frozenset(permissions), frozenset(roles), frozenset(orgs)


async def current_caller(authorization: Annotated[str | None, Header()] = None) -> Caller:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _unauthenticated()
    token = authorization.split(" ", 1)[1].strip()
    try:
        claims = security.verify(token)
    except security.TokenError as exc:
        raise _unauthenticated(str(exc)) from exc

    user_id = str(claims["sub"])
    permissions, roles, orgs = load_permissions(user_id)
    if not permissions:
        # Either the account was suspended, every grant was revoked, or the
        # profile row never got created. All three mean: no access.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "this account has no active permissions",
                }
            },
        )
    return Caller(
        user_id=user_id,
        claims=claims,
        permissions=permissions,
        roles=roles,
        organisation_ids=orgs,
        aal=str(claims.get("aal", "aal1")),
    )


CallerDep = Annotated[Caller, Depends(current_caller)]


def require(permission: str, *, aal2: bool = False):
    """Dependency factory: demand a permission, optionally at assurance level 2."""

    async def dependency(caller: CallerDep) -> Caller:
        if not caller.has(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "FORBIDDEN",
                        "message": f"this action needs the {permission} permission",
                        "permission": permission,
                    }
                },
            )
        if aal2 and caller.aal != "aal2":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "MFA_REQUIRED",
                        "message": "this action requires a second factor",
                        "permission": permission,
                    }
                },
            )
        return caller

    return dependency


def require_consent(caller: Caller, purpose: str) -> None:
    with db.admin_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select 1 from identity.consent
             where user_id = %s and purpose = %s and withdrawn_at is null
             limit 1
            """,
            (caller.user_id, purpose),
        )
        if cur.fetchone() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "CONSENT_REQUIRED",
                        "message": "this feature needs your consent first",
                        "purpose": purpose,
                    }
                },
            )


async def optional_caller(authorization: Annotated[str | None, Header()] = None) -> Caller | None:
    """A caller if there is one, otherwise None when anonymous triage is allowed.

    CLAUDE.md: "/check must stay usable with no account ... If a change would
    require signing in to get a verdict, the change is wrong." So the verdict
    path accepts no token, and so does the assistant - a signed-out visitor gets
    the public-policy tier of it (see assistant/scopes.py). What an account buys
    is history, gap tracking, market data, and a verdict drawn from a saved
    profile.
    """
    if authorization:
        return await current_caller(authorization)
    if not get_settings().allow_anonymous_triage:
        raise _unauthenticated()
    return None


OptionalCallerDep = Annotated[Caller | None, Depends(optional_caller)]
