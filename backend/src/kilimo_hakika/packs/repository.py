"""Pack loading: read once, verify, hold in memory.

No request ever reads rules from the database. A database outage degrades to
"serving the last known policy", never to a wrong verdict.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass

from ..engine import RulePack, load
from ..persistence import db
from ..settings import get_settings

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LoadedPack:
    pack: RulePack
    checksum: str
    source: str  # "database" | "bundled_fixture"
    loaded_at: float


class PackRepository:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._current: LoadedPack | None = None

    @property
    def current(self) -> LoadedPack | None:
        return self._current

    def require(self) -> LoadedPack:
        loaded = self._current
        if loaded is None:
            raise RuntimeError("no active rule pack")
        return loaded

    def refresh(self) -> LoadedPack | None:
        """Try the database, fall back to the bundled fixture.

        A refresh that fails keeps the pack already in memory: a transient
        database error must never blank the product.
        """
        with self._lock:
            loaded = self._from_database()
            if loaded is None and get_settings().pack_allow_bundled_fallback:
                loaded = self._from_bundle()
            if loaded is None:
                if self._current is not None:
                    log.warning("pack refresh failed; keeping %s", self._current.pack.version)
                return self._current
            self._current = loaded
            return loaded

    def _from_database(self) -> LoadedPack | None:
        settings = get_settings()
        if not settings.database_url:
            return None
        try:
            with db.admin_connection() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    select version, payload::text as payload_text, checksum
                      from kh.rule_pack
                     where scheme_code = %s and is_active
                     limit 1
                    """,
                    (settings.scheme_code,),
                )
                row = cur.fetchone()
        except Exception as exc:
            log.warning("could not read a pack from the database: %s", exc)
            return None

        if row is None:
            log.info("no active pack for scheme %s", settings.scheme_code)
            return None

        # Hash the exact text Postgres returned, which is what was hashed on
        # build. Re-serialising parsed JSON would not reproduce it.
        digest = hashlib.sha256(row["payload_text"].encode("utf-8")).hexdigest()
        if digest != row["checksum"]:
            log.error(
                "pack %s checksum mismatch (stored %s, computed %s); refusing it",
                row["version"],
                row["checksum"][:12],
                digest[:12],
            )
            return None

        try:
            pack = load(json.loads(row["payload_text"]))
        except Exception as exc:
            log.error("active pack %s failed validation: %s", row["version"], exc)
            return None

        return LoadedPack(pack=pack, checksum=digest, source="database", loaded_at=time.time())

    def _from_bundle(self) -> LoadedPack | None:
        from ..settings import BUNDLED_PACK

        if not BUNDLED_PACK.exists():
            log.error("bundled pack %s is missing", BUNDLED_PACK)
            return None
        text = BUNDLED_PACK.read_text(encoding="utf-8")
        try:
            pack = load(json.loads(text))
        except Exception as exc:
            log.error("bundled pack failed validation: %s", exc)
            return None
        log.warning(
            "serving the bundled fixture %s (%s) - in production this is an incident",
            pack.version,
            pack.environment,
        )
        return LoadedPack(
            pack=pack,
            checksum=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            source="bundled_fixture",
            loaded_at=time.time(),
        )


repository = PackRepository()
