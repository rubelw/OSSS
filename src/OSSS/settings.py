# src/OSSS/settings.py
from typing import Optional, List
from pydantic import AnyUrl, Field

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict  # pydantic v2
except ImportError:
    from pydantic import BaseSettings  # pydantic v1
    SettingsConfigDict = dict  # type: ignore


class Settings(BaseSettings):
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

    # Canonical (lowercase) fields with ENV aliases
    session_secret: str = Field("dev-insecure-change-me", alias="SESSION_SECRET")
    session_cookie_name: str = Field("osss_session", alias="SESSION_COOKIE_NAME")
    session_cookie: str = "osss_session"
    session_max_age: int = 60 * 60 * 24 * 14
    session_https_only: bool = False
    session_samesite: str = "lax"

    OIDC_SCOPE: str = "openid profile email offline_access"

    # Back-compat uppercase attribute access (so old code still works)
    @property
    def SESSION_SECRET(self) -> str: return self.session_secret
    @property
    def SESSION_COOKIE_NAME(self) -> str: return self.session_cookie_name
    @property
    def SESSION_COOKIE(self) -> str: return self.session_cookie
    @property
    def SESSION_MAX_AGE(self) -> int: return self.session_max_age
    @property
    def SESSION_HTTPS_ONLY(self) -> bool: return self.session_https_only
    @property
    def SESSION_SAMESITE(self) -> str: return self.session_samesite

    # pydantic v2 config (ignored by v1, harmless)
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
