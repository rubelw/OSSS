# src/OSSS/settings.py

from typing import Optional, List
from pydantic import AnyUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    KEYCLOAK_BASE_URL: AnyUrl                    # e.g. http://localhost:8080
    KEYCLOAK_REALM: str                          # e.g. "OSSS"
    KEYCLOAK_AUDIENCE: str                       # e.g. "osss-api"
    ACCEPTED_ISSUERS: Optional[List[str]] = None
    JWKS_CACHE_SECONDS: int = 600
    REQUIRE_AZP_MATCH: bool = False

    # Optional (only if you use token introspection for instant role flips)
    INTROSPECTION_CLIENT_ID: Optional[str] = None
    INTROSPECTION_CLIENT_SECRET: Optional[str] = None

    # Pydantic v2 settings config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

settings = Settings()
