"""Database access: two deliberately different connection modes.

`admin_connection()` bypasses RLS and is used for exactly three things - reading
the active rule pack, writing the anonymous triage log, and the dev auth
issuer's own bookkeeping.

`user_connection(claims)` opens a transaction as the `authenticated` role with
the caller's verified JWT claims installed, so every RLS policy in `identity`,
`market` and `ai` evaluates against the real user. Permission checks in the API
layer are the first gate; this is the one that holds if that gate has a bug.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from ..settings import get_settings

_pool: ConnectionPool | None = None


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        settings = get_settings()
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL is not set")
        _pool = ConnectionPool(
            settings.database_url,
            min_size=1,
            max_size=8,
            kwargs={
                "row_factory": dict_row,
                # Supavisor in transaction mode cannot hold prepared
                # statements. Harmless locally, required in production.
                "prepare_threshold": None,
            },
            open=True,
        )
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def is_available() -> bool:
    try:
        with admin_connection() as conn, conn.cursor() as cur:
            cur.execute("select 1")
        return True
    except Exception:
        return False


@contextmanager
def admin_connection() -> Iterator[psycopg.Connection]:
    with pool().connection() as conn:
        yield conn


@contextmanager
def user_connection(claims: dict[str, Any]) -> Iterator[psycopg.Connection]:
    """RLS-enforced connection. Claims must already be verified."""
    with pool().connection() as conn:
        with conn.cursor() as cur:
            # Order matters: install the claims while still privileged, then
            # drop to `authenticated` so policies apply for the rest of the tx.
            cur.execute("select set_config('request.jwt.claims', %s, true)", (json.dumps(claims),))
            cur.execute("set local role authenticated")
        try:
            yield conn
        finally:
            with conn.cursor() as cur:
                cur.execute("reset role")
