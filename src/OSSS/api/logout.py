# src/OSSS/api/logout.py
from __future__ import annotations

import os
import logging
import requests
from typing import Any, Optional

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse

from OSSS.app_logger import get_logger

log = get_logger("auth.logout")
router = APIRouter(tags=["auth"])

# --- Config ---
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "sid")
COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN")  # optional
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "1") == "1"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax").lower()  # "lax" | "strict" | "none"

OIDC_ISSUER = os.getenv("OIDC_ISSUER") or os.getenv("KEYCLOAK_ISSUER")
OIDC_CLIENT_ID = os.getenv("OIDC_CLIENT_ID") or os.getenv("KEYCLOAK_CLIENT_ID")
OIDC_CLIENT_SECRET = os.getenv("OIDC_CLIENT_SECRET") or os.getenv("KEYCLOAK_CLIENT_SECRET")

def _delete_cookie(response: Response, name: str):
    response.delete_cookie(
        name,
        path="/",
        domain=COOKIE_DOMAIN,
        secure=COOKIE_SECURE,
        httponly=True,
        samesite=COOKIE_SAMESITE,
    )

def _revoke_refresh_token(refresh_token: Optional[str]) -> None:
    """
    Best-effort token revocation for Keycloak. Safe to fail silently.
    """
    if not (refresh_token and OIDC_ISSUER and OIDC_CLIENT_ID and OIDC_CLIENT_SECRET):
        return
    try:
        url = f"{OIDC_ISSUER}/protocol/openid-connect/revoke"
        data = {
            "client_id": OIDC_CLIENT_ID,
            "client_secret": OIDC_CLIENT_SECRET,
            "token": refresh_token,
            "token_type_hint": "refresh_token",
        }
        r = requests.post(url, data=data, timeout=5)
        # 200 even if already invalidated; just log non-2xx
        if r.status_code >= 300:
            log.warning("revocation returned %s: %s", r.status_code, r.text[:300])
    except Exception as e:
        log.debug("revocation failed: %s", e)

async def _clear_server_session(request: Request) -> Optional[str]:
    """
    Wipes the server-side session. Returns the refresh_token if present.
    Works with either a per-request session object or a plain store + sid cookie.
    """
    # Preferred: a per-request session object (if your middleware sets it)
    session = getattr(request.state, "session", None)
    if session is not None:
        try:
            rt = await session.get("refresh_token")
        except TypeError:
            rt = session.get("refresh_token")
        # blast everything
        keys = [
            "access_token", "refresh_token", "expires_at", "refresh_expires_at",
            "email", "roles"
        ]
        try:
            await session.delete_many(keys)
        except TypeError:
            session.delete_many(keys)
        return rt

    # Fallback: store + cookie
    store = getattr(request.state, "session_store", None)
    if not store:
        return None

    sid = request.cookies.get(SESSION_COOKIE_NAME)
    if not sid:
        return None

    try:
        sess = await store.get(sid)
    except TypeError:
        sess = store.get(sid)

    rt = None
    if isinstance(sess, dict):
        rt = sess.get("refresh_token")

    # delete full session
    try:
        await store.delete(sid)
    except TypeError:
        store.delete(sid)

    return rt

async def _logout_impl(request: Request) -> JSONResponse:
    """
    Clears server session, revokes refresh token (if configured), and clears cookies.
    """
    refresh_token = await _clear_server_session(request)
    _revoke_refresh_token(refresh_token)

    # Build response
    resp = JSONResponse({"ok": True}, status_code=status.HTTP_200_OK)

    # Clear cookies commonly used
    for cookie_name in (SESSION_COOKIE_NAME, "access_token", "refresh_token"):
        _delete_cookie(resp, cookie_name)

    return resp

@router.post("/auth/logout", operation_id="auth_logout")
async def logout_auth(request: Request):
    return await _logout_impl(request)

# Optional alias to match your requested path
@router.post("/usr/logout", operation_id="usr_logout")
async def logout_usr(request: Request):
    return await _logout_impl(request)
