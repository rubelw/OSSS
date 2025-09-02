# src/OSSS/settings.py
from __future__ import annotations

from typing import Optional, List
import json
import os

# Detect pydantic v2 (pydantic-settings present) vs v1
from pydantic_settings import BaseSettings, SettingsConfigDict  # v2
from pydantic import AnyUrl, AnyHttpUrl, Field, model_validator, AliasChoices

# -----------------------------
# Google / Classroom integration
# -----------------------------
def _default_gc_scopes() -> List[str]:
    # Add coursework/grades scopes later as needed.
    return [
        "https://www.googleapis.com/auth/classroom.courses",
        "https://www.googleapis.com/auth/classroom.rosters",
        "https://www.googleapis.com/auth/classroom.profile.emails",
    ]


class GoogleSettings(BaseSettings):
    """
    Unified Google config:
      - Per-user OAuth: set google_client_id/secret/redirect (or a client secrets JSON path)
      - Service Account + DWD: set google_use_service_account + SA JSON (path or inline) + impersonation email
    All fields are environment-driven with prefix OSSS_ (case-insensitive).
    """

    # --- General / project ---
    google_project_id: Optional[str] = None

    # --- Per-user OAuth (optional) ---
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_oauth_redirect_uri: Optional[AnyHttpUrl] = None
    google_oauth_client_secrets_json_path: Optional[str] = None

    # --- Service Account + Domain-Wide Delegation (optional) ---
    google_use_service_account: bool = Field(
        False,
        description="If true, use Service Account + Domain-Wide Delegation for Google Classroom.",
    )
    google_sa_json_path: Optional[str] = None
    google_sa_json: Optional[str] = None  # raw JSON string
    google_workspace_impersonate: Optional[str] = None  # e.g., admin@yourdomain.org

    # --- Classroom scopes ---
    google_classroom_scopes: List[str] = Field(default_factory=_default_gc_scopes)

    # --- Pub/Sub verification (if you use Classroom notifications) ---
    pubsub_verification_token: Optional[str] = None

    # v2 config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_prefix="OSSS_",
    )

    # ---- helpers -----------------------------------------------------
    @property
    def use_service_account(self) -> bool:
        return bool(self.google_use_service_account)

    @property
    def scopes(self) -> List[str]:
        return list(self.google_classroom_scopes)

    @property
    def sa_json_source(self) -> Optional[str]:
        return self.google_sa_json

    @property
    def sa_json_path_source(self) -> Optional[str]:
        return self.google_sa_json_path


class Settings(BaseSettings):


    # Read the raw env (we’ll parse ourselves)
    cors_origins_raw: str | None = Field(default=None, alias="CORS_ORIGINS")

    # Prevent env from binding directly to this list field (which forces JSON)
    # by pointing it at a non-existent env name.
    cors_origins: list[AnyHttpUrl] = Field(
        default_factory=list,
        validation_alias=AliasChoices("CORS_ORIGINS_PARSED_DO_NOT_USE"),
    )

    KEYCLOAK_BASE_URL: AnyUrl
    KEYCLOAK_REALM: str
    KEYCLOAK_AUDIENCE: str
    ACCEPTED_ISSUERS: Optional[List[str]] = None
    JWKS_CACHE_SECONDS: int = 600
    REQUIRE_AZP_MATCH: bool = False

    SWAGGER_CLIENT_ID: str = "osss-api"
    SWAGGER_CLIENT_SECRET: Optional[str] = None
    SWAGGER_USE_PKCE: bool = True

    INTROSPECTION_CLIENT_ID: Optional[str] = None
    INTROSPECTION_CLIENT_SECRET: Optional[str] = None

    session_secret: str = Field("dev-insecure-change-me", alias="SESSION_SECRET")
    session_cookie_name: str = Field("osss_session", alias="SESSION_COOKIE_NAME")
    session_cookie: str = "osss_session"
    session_max_age: int = Field(60 * 60 * 24 * 14, env="SESSION_MAX_AGE")
    session_https_only: bool = False
    session_samesite: str = "lax"

    OIDC_SCOPE: str = "openid profile email offline_access"


    @property
    def SESSION_SECRET(self) -> str:
        return self.session_secret

    @property
    def SESSION_COOKIE_NAME(self) -> str:
        return self.session_cookie_name

    @property
    def SESSION_COOKIE(self) -> str:
        return self.session_cookie

    @property
    def SESSION_MAX_AGE(self) -> int:
        return self.session_max_age

    @property
    def SESSION_HTTPS_ONLY(self) -> bool:
        return self.session_https_only

    @property
    def SESSION_SAMESITE(self) -> str:
        return self.session_samesite

    @model_validator(mode="after")
    def _normalize_cors(self):
        raw = self.cors_origins_raw
        if not raw:
            return self
        s = raw.strip()
        # Try JSON first
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                self.cors_origins = parsed
                return self
        except Exception:
            pass
        # Fallback to CSV
        self.cors_origins = [p.strip() for p in s.split(",") if p.strip()]
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )


# Instantiate at import time
settings = Settings()
google = GoogleSettings()
