# src/OSSS/core/config.py
from __future__ import annotations

import os
from typing import Any, List, Optional
import json

from pydantic import AnyHttpUrl, Field, AliasChoices, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ---- App ----
    APP_NAME: str = "OSSS API"
    APP_VERSION: str = "0.1.0"

    # ---- DB ----
    # read DATABASE_URL, else ASYNC_DATABASE_URL, else a safe default
    DATABASE_URL: str = (
            os.getenv("DATABASE_URL")
            or os.getenv("ASYNC_DATABASE_URL")
            or "postgresql+asyncpg://osss:password@osss_postgres:5432/osss"
    )
    DB_ECHO: bool = False
    TESTING: bool = False

    # ---- Web / CORS ----
    # Raw env value (JSON or CSV). Use validation_alias for env binding (v2 style).
    cors_origins_raw: str | None = Field(
        default=None,
        validation_alias=AliasChoices("CORS_ORIGINS"),
    )

    # Parsed list (authoritative value used by the app).
    # We *don’t* allow env to bind directly to this—only the validator sets it.
    cors_origins: list[AnyHttpUrl] = Field(
        default_factory=list,
        validation_alias=AliasChoices("CORS_ORIGINS_PARSED_DO_NOT_USE"),
    )

    NEXT_PUBLIC_PUBLIC_URL: str = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices("NEXT_PUBLIC_PUBLIC_URL", "PUBLIC_URL"),
    )

    # ---- Keycloak (backend confidential client) ----
    KEYCLOAK_BASE_URL: str = Field(
        default="http://localhost:8080",
        validation_alias=AliasChoices("KEYCLOAK_BASE_URL", "KEYCLOAK_SERVER_URL", "KEYCLOAK_PUBLIC_URL"),
    )
    KEYCLOAK_REALM: str = Field(
        default="OSSS",
        validation_alias=AliasChoices("KEYCLOAK_REALM", "REALM"),
    )
    KEYCLOAK_CLIENT_ID: str = Field(
        default="osss-api",
        validation_alias=AliasChoices("KEYCLOAK_CLIENT_ID", "KC_CLIENT_ID"),
    )
    KEYCLOAK_CLIENT_SECRET: str | None = Field(
        default=None,
        validation_alias=AliasChoices("KEYCLOAK_CLIENT_SECRET", "KC_CLIENT_SECRET"),
    )

    # Accept tokens from these audiences (aud/azp)
    KEYCLOAK_ALLOWED_AUDIENCES: str = Field(
        default="osss-api,osss-web",
        validation_alias=AliasChoices("KEYCLOAK_ALLOWED_AUDIENCES", "KEYCLOAK_AUDIENCE"),
    )

    # ---- Swagger / OAuth UI (controls the “Authorize” dialog) ----
    SWAGGER_CLIENT_ID: str = Field(
        default="osss-api",
        validation_alias=AliasChoices("OSSS_SWAGGER_CLIENT_ID", "SWAGGER_CLIENT_ID"),
    )
    SWAGGER_USE_PKCE: bool = True
    SWAGGER_CLIENT_SECRET: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OSSS_SWAGGER_CLIENT_SECRET", "SWAGGER_CLIENT_SECRET"),
    )
    CALLBACK_URL: str = Field(
        default="http://localhost:8081/callback",
        validation_alias=AliasChoices("CALLBACK_URL", "REDIRECT_URI"),
    )

    # ---- Sessions / Cookies / Redis ----
    AUTH_DEBUG: bool = Field(default=False, validation_alias=AliasChoices("AUTH_DEBUG", "REQUESTS_DEBUG"))

    REDIS_URL: str | None = Field(default=None, validation_alias=AliasChoices("REDIS_URL"))
    SESSION_SECRET: str | None = Field(default=None, validation_alias=AliasChoices("SESSION_SECRET"))
    SESSION_MAX_AGE: int | None = Field(default=None, validation_alias=AliasChoices("SESSION_MAX_AGE"))
    SESSION_TTL_SECONDS: int | None = Field(default=None, validation_alias=AliasChoices("SESSION_TTL_SECONDS"))
    COOKIE_DOMAIN: str | None = Field(default=None, validation_alias=AliasChoices("COOKIE_DOMAIN"))
    COOKIE_SECURE: bool | None = Field(default=False, validation_alias=AliasChoices("COOKIE_SECURE"))
    COOKIE_SAMESITE: str | None = Field(default="lax", validation_alias=AliasChoices("COOKIE_SAMESITE"))

    # ---- Pydantic settings config ----
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

    # ---- Validators ----
    @model_validator(mode="after")
    def _compute_cors(self) -> "Settings":
        """
        Populate `cors_origins` from:
          1) CORS_ORIGINS (JSON array or CSV)
          2) fallback to [NEXT_PUBLIC_PUBLIC_URL] if nothing provided
        """
        parsed: list[str] = []

        raw = self.cors_origins_raw
        if raw:
            raw = raw.strip()
            if raw.startswith("["):
                # JSON array
                try:
                    data = json.loads(raw)
                    if isinstance(data, list):
                        parsed = [str(x).strip() for x in data if x]
                except Exception:
                    # ignore parse errors; fall through to CSV
                    pass
            if not parsed:
                # CSV
                parsed = [p.strip() for p in raw.split(",") if p.strip()]

        if not parsed:
            # fallback to single origin from NEXT_PUBLIC_PUBLIC_URL
            parsed = [self.NEXT_PUBLIC_PUBLIC_URL]

        # Let pydantic coerce/validate to AnyHttpUrl
        self.cors_origins = parsed  # type: ignore[assignment]
        return self


settings = Settings()
__all__ = ["settings", "Settings"]
