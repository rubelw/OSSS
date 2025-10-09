# src/OSSS/auth/routes.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from starlette.responses import RedirectResponse

from OSSS.settings import settings
from OSSS.auth.oauth import oauth  # your registered Authlib client
from OSSS.auth.tokens import TokenSet

router = APIRouter()

def _now_utc():
    return datetime.now(timezone.utc)

def _get_login_redirect() -> str:
    return getattr(settings, "LOGIN_REDIRECT_URL", "/")

def _extract_subject(token: dict) -> Optional[str]:
    """
    Prefer sub from userinfo, then from ID token if present.
    Authlib puts userinfo (when requested) under token.get("userinfo").
    """
    ui = token.get("userinfo") or {}
    sub = ui.get("sub")
    if sub:
        return sub

    # Fallback: some setups include "id_token" (JWT). If you want to decode it,
    # plug in your JWT decoder here. For now we skip decoding and return None.
    # Example (if using python-jose):
    # from jose import jwt
    # claims = jwt.get_unverified_claims(token.get("id_token"))
    # return claims.get("sub")
    return None

@router.get("/auth/callback")
async def auth_callback(request: Request):
    """
    Handle Keycloak OIDC callback:
      - exchange code for tokens via Authlib
      - persist access/refresh tokens and expirations in Redis session (request.state.session)
      - set initial idle TTL (SessionTTL middleware will adjust on each request)
      - redirect to app
    """
    # Ensure our Redis-backed session is attached by earlier middleware
    session = getattr(request.state, "session", None)
    if session is None:
        # If you still have starlette's cookie session, you can guide devs here:
        raise HTTPException(status_code=500, detail="Server session missing; ensure session-attach middleware runs before auth_callback")

    try:
        # Authlib will validate state/PKCE and perform the token request
        token: dict = await oauth.keycloak.authorize_access_token(request)
    except Exception:
        # keep generic to avoid leaking details
        raise HTTPException(status_code=401, detail="Authentication failed")

    # Normalize into our TokenSet (computes absolute UTC expirations)
    tset = TokenSet.from_oidc_response(token)

    # Subject / user id (prefer userinfo.sub)
    user_id = _extract_subject(token) or ""

    # Persist required fields for the SessionTTL middleware
    await session.set("user_id", user_id)
    await session.set("access_token", tset.access_token)
    await session.set("access_expires_at", tset.access_expires_at)

    if tset.refresh_token:
        await session.set("refresh_token", tset.refresh_token)
    if tset.refresh_expires_at:
        await session.set("refresh_expires_at", tset.refresh_expires_at)

    # Optional extras (handy if you need them later)
    if token.get("scope"):
        await session.set("scope", token["scope"])
    if token.get("token_type"):
        await session.set("token_type", token["token_type"])
    if token.get("id_token"):
        # store raw id_token only if you actually need it later
        await session.set("id_token", token["id_token"])
    if token.get("userinfo"):
        await session.set("email", (token["userinfo"] or {}).get("email") or "")

    # Touch idle timer; SessionTTL will enforce idle vs absolute on requests
    await session.set("last_seen", _now_utc())

    # Give an initial idle TTL; SessionTTL middleware will tighten it to the min of
    # (IDLE_TIMEOUT, refresh_expires_at - now, kc_session_expires_at - now)
    await session.set_ttl(30 * 60)  # 30 minutes


    # Done: send user to app
    return RedirectResponse(url=_get_login_redirect())
