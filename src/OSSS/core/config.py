# src/OSSS/core/config.py
from __future__ import annotations

from pydantic import field_validator, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ---- App ----
    APP_NAME: str = "OSSS API"
    APP_VERSION: str = "0.1.0"

    # ---- DB ----
    DATABASE_URL: str = "sqlite+aiosqlite:///:memory:"
    TESTING: bool = False  # set to "1" in tests to skip real DB ping

    # ---- CORS / Web ----
    NEXT_PUBLIC_PUBLIC_URL: str = "http://localhost:3000"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # ---- Keycloak (backend confidential client) ----
    KEYCLOAK_BASE_URL: str = "http://localhost:8085"  # no trailing slash
    KEYCLOAK_REALM: str = "OSSS"
    KEYCLOAK_CLIENT_ID: str = "osss-api"
    KEYCLOAK_CLIENT_SECRET: str = "changeme"

    # Accept tokens from these audiences (aud/azp)
    KEYCLOAK_ALLOWED_AUDIENCES: str = "osss-api,osss-web"

    # ---- Swagger / OAuth UI ----
    SWAGGER_CLIENT_ID: str = "osss-web"   # public web client for browser flow
    SWAGGER_USE_PKCE: bool = True
    # Optional: set a client secret to show in “Available authorizations” (dev only)
    SWAGGER_CLIENT_SECRET: str | None = None
    CALLBACK_URL: str = "http://localhost:8081/callback"

    # Optional dev toggles (harmless if present in env)
    AUTH_DEBUG: bool = False

    # Pydantic settings config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,   # allow lower/upper env names
        extra="ignore",         # <-- ignore all unknown env keys
    )

    # Parse comma-separated CORS_ORIGINS from env
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors(cls, v):
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    # Convenience computed values
    @computed_field(return_type=str)
    def KEYCLOAK_ISSUER(self) -> str:
        return f"{self.KEYCLOAK_BASE_URL.rstrip('/')}/realms/{self.KEYCLOAK_REALM}"

    @computed_field(return_type=set[str])
    def ALLOWED_AUDIENCES_SET(self) -> set[str]:
        return {s.strip() for s in self.KEYCLOAK_ALLOWED_AUDIENCES.split(",") if s.strip()}


settings = Settings()
__all__ = ["settings", "Settings"]
