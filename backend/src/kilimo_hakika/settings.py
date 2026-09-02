from __future__ import annotations

import functools
import pathlib

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
# Named rule_pack.json, not scheme_rules.json: the Next app owns that filename
# for its own policy file. Two files, two formats, one source of truth for
# verdicts - see docs/design/integration.md.
BUNDLED_PACK = REPO_ROOT / "database" / "rule_pack.json"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_env: str = "development"
    log_level: str = "INFO"
    api_allowed_origins: str = "http://localhost:3000"

    scheme_code: str = "NFSP"

    database_url: str = ""

    pack_refresh_seconds: int = 300
    pack_allow_bundled_fallback: bool = True

    triage_log_enabled: bool = True
    triage_log_retention_days: int = 90

    # Dev auth stands in for Supabase Auth: same claim shape, same RLS
    # behaviour, local signing key. Swapping to Supabase means verifying against
    # its JWKS instead of this secret - the rest of the stack is unchanged.
    jwt_secret: str = "dev-only-not-a-real-secret-change-me"
    jwt_issuer: str = "kilimo-hakika-dev"
    jwt_ttl_seconds: int = 7_776_000  # 90 days: a farmer signs in about once a season
    dev_auth_enabled: bool = True
    dev_otp_code: str = "123456"

    # CLAUDE.md (merged 2026-09-02) states /check must work with no account.
    # Login still gates history, tracking, market data and the assistant.
    allow_anonymous_triage: bool = True

    anthropic_api_key: str = ""
    # Identity-linked keys must name the workspace the request acts in.
    anthropic_workspace_id: str = ""
    assistant_model: str = "claude-opus-5"
    assistant_effort: str = "low"

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.api_allowed_origins.split(",") if o.strip()]


@functools.lru_cache
def get_settings() -> Settings:
    return Settings()
