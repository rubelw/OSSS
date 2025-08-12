# settings.py (excerpt)
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "My App"
    DATABASE_URL: str

    KEYCLOAK_SERVER_URL: str          # e.g. http://keycloak:8080
    KEYCLOAK_REALM: str               # e.g. myrealm
    KEYCLOAK_CLIENT_ID: str           # e.g. myclient
    KEYCLOAK_AUDIENCE: str | None = None
    KEYCLOAK_WELL_KNOWN_URL: str | None = None
    KEYCLOAK_JWKS_URL: str | None = None
    KEYCLOAK_ISSUER: str | None = None
    KEYCLOAK_PUBLIC_URL: str | None = None  # e.g. http://localhost:8080

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

settings = Settings()
