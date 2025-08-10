import jwt
from jwt import PyJWKClient
from fastapi import Header, HTTPException, status
from .config import settings

_jwks_client = None
_last_issuer = None

def _jwks():
    global _jwks_client, _last_issuer
    if _jwks_client is None or _last_issuer != settings.keycloak_issuer:
        jwks_uri = f"{settings.keycloak_issuer}/protocol/openid-connect/certs"
        _jwks_client = PyJWKClient(jwks_uri)
        _last_issuer = settings.keycloak_issuer
    return _jwks_client

def verify_token(auth_header: str | None) -> dict:
    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = auth_header.split(" ", 1)[1]
    try:
        signing_key = _jwks().get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=settings.keycloak_audience,
            issuer=settings.keycloak_issuer,
        )
        return claims
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}")

def current_user(authorization: str | None = Header(default=None)) -> dict:
    return verify_token(authorization)
