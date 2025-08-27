# src/OSSS/auth/deps.py
from __future__ import annotations
from typing import Any, Dict, Iterable, Optional, Set
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer

from OSSS.settings import settings
from OSSS.auth.jwt import verify_and_decode
from OSSS.auth.roles import extract_roles

oauth2 = OAuth2PasswordBearer(
    tokenUrl="/auth/token",  # implemented by the small proxy route
    scopes={"openid": "OIDC", "profile": "Profile", "email": "Email", "roles": "Keycloak roles"},
)

async def get_current_user(token: str = Security(oauth2, scopes=["roles"])) -> Dict[str, Any]:
    decoded = await verify_and_decode(token)
    roles = extract_roles(decoded, settings.KEYCLOAK_AUDIENCE)
    return {
        "sub": decoded.get("sub"),
        "email": decoded.get("email"),
        "preferred_username": decoded.get("preferred_username"),
        "roles": roles,
        "token": decoded,
    }

async def get_token_payload(token: str = Security(oauth2, scopes=["roles"])) -> Dict[str, Any]:
    return await verify_and_decode(token)

async def require_auth(_user: Dict[str, Any] = Depends(get_current_user)) -> None:
    return None

def require_roles(any_of: Iterable[str] | None = None, all_of: Iterable[str] | None = None, client_id: Optional[str] = None):
    any_set: Set[str] = set(any_of or [])
    all_set: Set[str] = set(all_of or [])
    async def _checker(token: str = Security(oauth2, scopes=["roles"])):
        decoded = await verify_and_decode(token)
        roles = extract_roles(decoded, settings.KEYCLOAK_AUDIENCE)
        if any_set and roles.isdisjoint(any_set):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        if all_set and not all_set.issubset(roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return decoded
    return _checker
