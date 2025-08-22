# src/OSSS/security.py
import os
from typing import Optional
from fastapi import HTTPException, Security, status
from fastapi.security import (
    OAuth2AuthorizationCodeBearer,
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
# ----- Keycloak endpoints -----
KEYCLOAK_BASE = os.getenv("KEYCLOAK_SERVER_URL", "http://localhost:8085").rstrip("/")
REALM = os.getenv("KEYCLOAK_REALM", "OSSS")

oauth2 = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"{KEYCLOAK_BASE}/realms/{REALM}/protocol/openid-connect/auth",
    tokenUrl=f"{KEYCLOAK_BASE}/realms/{REALM}/protocol/openid-connect/token",
    scopes={"openid": "OpenID Connect scope"},
)

bearer = HTTPBearer(auto_error=False)

async def get_bearer_token(
    # Accept token from either scheme (Swagger OAuth or raw Bearer)
    token_from_oauth: Optional[str] = Security(oauth2, scopes=["openid"]),
    creds: Optional[HTTPAuthorizationCredentials] = Security(bearer),
) -> str:
    token = token_from_oauth or (creds.credentials if creds else None)
    if not token:
        # Make WWW-Authenticate header nice for clients/tools
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": f'Bearer realm="{REALM}"'},
        )
    # TODO: (recommended) validate JWT signature/aud/iss via JWKS before returning
    return token
