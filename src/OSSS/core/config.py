# src/OSSS/core/config.py
from __future__ import annotations

from __future__ import annotations
from typing import Any, List, Optional
import json

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyUrl, AnyHttpUrl, Field, model_validator, AliasChoices


class Settings(BaseSettings):

    # Read the raw env string first (JSON or CSV)
    cors_origins_raw: str | None = Field(default=None, alias="CORS_ORIGINS")

    # Keep the actual parsed list separate so env can't bind directly
    cors_origins: list[AnyHttpUrl] = Field(
        default_factory=list,
        validation_alias=AliasChoices("CORS_ORIGINS_PARSED_DO_NOT_USE"),
    )

    # ---- App ----
    APP_NAME: str = "OSSS API"
    APP_VERSION: str = "0.1.0"

    # ---- DB ----
    # Prefer DATABASE_URL, but also accept OSSS_DB_URL as a fallback.
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///:memory:",
        validation_alias=AliasChoices("DATABASE_URL", "OSSS_DB_URL"),
    )
    TESTING: bool = False  # set to "1" in tests to skip real DB ping

    # ---- CORS / Web ----
    NEXT_PUBLIC_PUBLIC_URL: str = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices("NEXT_PUBLIC_PUBLIC_URL", "PUBLIC_URL"),
    )
    # If CORS_ORIGINS is not set, we'll default it to NEXT_PUBLIC_PUBLIC_URL
    CORS_ORIGINS: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # ---- Keycloak (backend confidential client) ----
    # Accept several common env var names; prefer KEYCLOAK_BASE_URL.
    KEYCLOAK_BASE_URL: str = Field(
        default="http://localhost:8085",
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
    # Prefer OSSS_SWAGGER_CLIENT_ID if present, else SWAGGER_CLIENT_ID.
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

    # Optional dev toggles
    AUTH_DEBUG: bool = Field(default=False, validation_alias=AliasChoices("AUTH_DEBUG", "REQUESTS_DEBUG"))

    REDIS_URL: str | None = Field(
        default=None,
        validation_alias=AliasChoices("REDIS_URL"),
    )

    SESSION_SECRET: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SESSION_SECRET"),
    )

    SESSION_MAX_AGE: int | None = Field(
        default=None,
        validation_alias=AliasChoices("SESSION_MAX_AGE"),
    )

    SESSION_TTL_SECONDS: int | None = Field(
        default=None,
        validation_alias=AliasChoices("SESSION_TTL_SECONDS"),
    )

    COOKIE_DOMAIN: str | None = Field(
        default=None,
        validation_alias=AliasChoices("COOKIE_DOMAIN"),
    )

    COOKIE_SECURE: bool | None = Field(
        default=False,
        validation_alias=AliasChoices("COOKIE_SECURE"),
    )

    COOKIE_SAMESITE: str | None = Field(
        default="lax",
        validation_alias=AliasChoices("COOKIE_SAMESITE"),
    )



    # Pydantic settings config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )



settings = Settings()
__all__ = ["settings", "Settings"]
