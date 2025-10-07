from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, field_validator
from typing import Optional

class Settings(BaseSettings):
    # Upstream OpenAI-compatible model server (e.g., vLLM)
    VLLM_ENDPOINT: AnyHttpUrl = "http://ollama:11434/v1"

    # Optional: OIDC / Keycloak
    OIDC_ISSUER: Optional[str] = None
    OIDC_AUDIENCE: Optional[str] = None
    OIDC_JWKS_CACHE_SECONDS: int = 3600

    # App policy
    TUTOR_MAX_TOKENS: int = 768
    TUTOR_TEMPERATURE: float = 0.2
    RAG_TOP_K: int = 4
    RAG_CHUNK_SIZE: int = 800

    # Misc
    PROMETHEUS_ENABLED: bool = True
    LOG_LEVEL: str = "INFO"

    @field_validator("TUTOR_TEMPERATURE")
    @classmethod
    def clamp_temp(cls, v: float) -> float:
        return max(0.0, min(2.0, v))

settings = Settings()  # type: ignore
