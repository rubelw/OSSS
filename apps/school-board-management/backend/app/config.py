from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    postgres_host: str = os.getenv("POSTGRES_HOST","localhost")
    postgres_port: int = int(os.getenv("POSTGRES_PORT","5432"))
    postgres_db: str = os.getenv("POSTGRES_DB","osss")
    postgres_user: str = os.getenv("POSTGRES_USER","osss")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD","changeme")
    api_secret: str = os.getenv("API_SECRET","devsecret")
    cors_origins: str = os.getenv("CORS_ORIGINS","http://localhost:5173")
    keycloak_issuer: str = os.getenv("KEYCLOAK_ISSUER","http://localhost:8081/realms/oss")
    keycloak_audience: str = os.getenv("KEYCLOAK_AUDIENCE","osss-web")

settings = Settings()
