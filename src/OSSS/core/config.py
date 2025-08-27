# src/OSSS/core/config.py
from __future__ import annotations

from typing import Any
from pydantic import Field, AliasChoices, field_validator, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
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

    # Pydantic settings config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # allow lower/upper env names
        extra="ignore",        # ignore unknown env keys (your .env has many)
    )

    # --- Validators / Computed ---

    # Parse comma-separated CORS_ORIGINS; if not provided, default to NEXT_PUBLIC_PUBLIC_URL
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors(cls, v: Any) -> list[str]:
        if v is None or v == "":
            # default to NEXT_PUBLIC_PUBLIC_URL at runtime; pydantic gives us values post-init
            return []
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    @computed_field(return_type=str)
    def KEYCLOAK_ISSUER(self) -> str:
        return f"{self.KEYCLOAK_BASE_URL.rstrip('/')}/realms/{self.KEYCLOAK_REALM}"

    @computed_field(return_type=set[str])
    def ALLOWED_AUDIENCES_SET(self) -> set[str]:
        return {s.strip() for s in self.KEYCLOAK_ALLOWED_AUDIENCES.split(",") if s.strip()}

    @computed_field(return_type=list[str])
    def EFFECTIVE_CORS_ORIGINS(self) -> list[str]:
        """
        If CORS_ORIGINS wasn't explicitly set, use NEXT_PUBLIC_PUBLIC_URL.
        (Expose as a separate computed field so your app can choose which to use.)
        """
        if self.CORS_ORIGINS:
            return self.CORS_ORIGINS
        return [self.NEXT_PUBLIC_PUBLIC_URL]


settings = Settings()
__all__ = ["settings", "Settings"]
