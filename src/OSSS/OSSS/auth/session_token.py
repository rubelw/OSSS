# src/OSSS/auth/session_token.py
# src/OSSS/auth/session_token.py
import time
from typing import Any, Dict, Optional
from fastapi import HTTPException, Request, Depends
from authlib.integrations.starlette_client import OAuthError
from OSSS.auth.oauth import oauth

ACCESS_SKEW = 60
REFRESH_SKEW = 60

def _now() -> int: return int(time.time())

@router.get("/protected")
async def protected_view(
    token: str = Depends(ensure_access_token),
    user: dict = Depends(get_current_user),
):
    # token is guaranteed fresh here
    ...

def _access_expires_at(token: Dict[str, Any]) -> int:
    if token.get("expires_at") is not None:
        return int(token["expires_at"])
    if token.get("expires_in") is not None:
        return _now() + int(token["expires_in"])
    return _now() + 300

def _refresh_expires_at(token: Dict[str, Any], prev: Optional[int]) -> Optional[int]:
    if token.get("refresh_expires_in") is not None:
        return _now() + int(token["refresh_expires_in"])
    return prev

async def ensure_access_token(request: Request) -> str:
    sess: Dict[str, Any] = request.session.get("oidc") or {}
    access = sess.get("access_token")
    access_exp = sess.get("access_expires_at") or sess.get("expires_at")
    refresh = sess.get("refresh_token")
    refresh_exp = sess.get("refresh_expires_at")

    if not refresh:
        raise HTTPException(status_code=401, detail="Not authenticated")

    now = _now()
    if access and access_exp and (access_exp - ACCESS_SKEW) > now:
        return access

    if refresh_exp is not None and (refresh_exp - REFRESH_SKEW) <= now:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Session expired")

    try:
        token = await oauth.keycloak.refresh_token(
            url=oauth.keycloak.client.server_metadata["token_endpoint"],
            refresh_token=refresh,
        )
    except OAuthError:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Session expired")

    new_access = token.get("access_token")
    if not new_access:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Session invalid")

    request.session["oidc"] = {
        "access_token": new_access,
        "access_expires_at": _access_expires_at(token),
        "expires_at": token.get("expires_at"),  # or use `expires_in`
        "refresh_token": token.get("refresh_token", refresh),           # may rotate
        "refresh_expires_at": _refresh_expires_at(token, refresh_exp),  # may be None
        "token_type": token.get("token_type"),
        "scope": token.get("scope"),
        "id_token": token.get("id_token"),
    }
    return new_access
