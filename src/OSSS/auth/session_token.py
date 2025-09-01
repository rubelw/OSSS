# src/OSSS/auth/session_token.py
import time
from typing import Any, Dict, Optional
from fastapi import HTTPException, Request
from authlib.integrations.starlette_client import OAuthError
from OSSS.auth.oauth import oauth  # your Authlib OAuth instance

# refresh slightly before actual expiry
ACCESS_SKEW = 60
REFRESH_SKEW = 60

def _now() -> int:
    return int(time.time())

def _compute_access_expires_at(token: Dict[str, Any]) -> int:
    """
    Prefer absolute 'expires_at' if provided; else derive from 'expires_in' (seconds).
    Default to 5 minutes if neither is present.
    """
    if token.get("expires_at") is not None:
        return int(token["expires_at"])
    if token.get("expires_in") is not None:
        return _now() + int(token["expires_in"])
    return _now() + 300  # fallback

def _compute_refresh_expires_at(token: Dict[str, Any], prev: Optional[int]) -> Optional[int]:
    """
    Derive refresh token expiry if Keycloak returns 'refresh_expires_in'.
    Otherwise, keep previous value if we had one.
    """
    if token.get("refresh_expires_in") is not None:
        return _now() + int(token["refresh_expires_in"])
    return prev

async def ensure_access_token(request: Request) -> str:
    """
    Return a valid access token, refreshing with the refresh token when:
      - there is no access token (e.g., after server restart), or
      - the access token is near/at expiry.
    Clears session and raises 401 if refresh is invalid/expired.
    """
    sess: Dict[str, Any] = request.session.get("oidc") or {}
    access_token: Optional[str] = sess.get("access_token")
    access_expires_at: Optional[int] = sess.get("access_expires_at") or sess.get("expires_at")
    refresh_token: Optional[str] = sess.get("refresh_token")
    refresh_expires_at: Optional[int] = sess.get("refresh_expires_at")

    if not refresh_token:
        # no way to recover
        raise HTTPException(status_code=401, detail="Not authenticated")

    now = _now()

    # If we *do* have a still-valid access token, use it
    if access_token and access_expires_at and (access_expires_at - ACCESS_SKEW) > now:
        return access_token

    # If refresh token appears expired, force re-login
    if refresh_expires_at is not None and (refresh_expires_at - REFRESH_SKEW) <= now:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Session expired")

    # Refresh (covers restart: missing access_token/expiry) and normal expiry
    try:
        token = await oauth.keycloak.refresh_token(
            url=oauth.keycloak.client.server_metadata["token_endpoint"],
            refresh_token=refresh_token,
        )
    except OAuthError:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Session expired")

    new_access = token.get("access_token")
    if not new_access:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Session invalid")

    # Persist refreshed tokens + expiries
    new_access_exp = _compute_access_expires_at(token)
    new_refresh = token.get("refresh_token", refresh_token)  # may rotate
    new_refresh_exp = _compute_refresh_expires_at(token, refresh_expires_at)

    request.session["oidc"] = {
        "access_token": new_access,
        "access_expires_at": new_access_exp,
        "refresh_token": new_refresh,
        "refresh_expires_at": new_refresh_exp,
        # optional extras:
        "token_type": token.get("token_type"),
        "scope": token.get("scope"),
        "id_token": token.get("id_token"),
    }

    return new_access
