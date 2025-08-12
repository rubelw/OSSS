# settings.py (excerpt)
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "My App"
    DATABASE_URL: str

    KEYCLOAK_SERVER_URL: str          # e.g. http://keycloak:8080
    KEYCLOAK_REALM: str               # e.g. myrealm
    KEYCLOAK_CLIENT_ID: str           # e.g. myclient
    KEYCLOAK_AUDIENCE: Optional[str] = None
    KEYCLOAK_WELL_KNOWN_URL: Optional[str] = None  # optional override
    KEYCLOAK_JWKS_URL: Optional[str] = None
    KEYCLOAK_ISSUER: Optional[str] = None
    KEYCLOAK_PUBLIC_URL: Optional[str] = None  # e.g. http://localhost:8080

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

settings = Settings()
