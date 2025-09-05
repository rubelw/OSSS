# src/OSSS/api/routers/auth_flow.py
from __future__ import annotations

import os
import logging
from typing import Optional, Dict, Any

import requests
from fastapi import APIRouter, Request, Response, Form, HTTPException

from OSSS.app_logger import get_logger
from OSSS.sessions import (
    ensure_sid_cookie_and_store,
    get_session_store,
    record_tokens_to_session,
)

log = get_logger("auth_flow")

router = APIRouter()

# ---- OIDC / Keycloak config --------------------------------------------------
KC_ISSUER         = os.getenv("KEYCLOAK_ISSUER") or os.getenv("OIDC_ISSUER")
KC_CLIENT_ID      = os.getenv("KEYCLOAK_CLIENT_ID", "osss-api")
KC_CLIENT_SECRET  = os.getenv("KEYCLOAK_CLIENT_SECRET")  # optional (confidential client)

def _token_url() -> str:
    if not KC_ISSUER:
        raise RuntimeError("KEYCLOAK_ISSUER / OIDC_ISSUER not configured")
    return KC_ISSUER.rstrip("/") + "/protocol/openid-connect/token"


# ---- helpers ----------------------------------------------------------------
async def _persist_tokens(
    request: Request,
    response: Response,
    tokens: Dict[str, Any],
    *,
    user_email: Optional[str] = None,
) -> Dict[str, Any]:
    # ensure sid cookie + initial session
    sid = await ensure_sid_cookie_and_store(request, response)
    # get the store (SYNC function; do NOT await)
    store = get_session_store(request)
    # persist tokens w/ set-many semantics
    updated = await record_tokens_to_session(
        store,
        sid,
        tokens,
        user_email=user_email,
    )
    return updated


# ---- routes -----------------------------------------------------------------
@router.post("/token")
async def password_grant(
    request: Request,
    response: Response,
    username: str = Form(..., alias="username"),
    password: str = Form(..., alias="password"),
    grant_type: str = Form("password"),
    scope: Optional[str] = Form(None),
):
    if grant_type != "password":
        raise HTTPException(status_code=400, detail="Unsupported grant_type")

    log.debug("/auth/token: requesting tokens for %s", username)

    data = {
        "grant_type": "password",
        "username": username,
        "password": password,
        "client_id": KC_CLIENT_ID,
    }
    if KC_CLIENT_SECRET:
        data["client_secret"] = KC_CLIENT_SECRET
    if scope:
        data["scope"] = scope

    try:
        r = requests.post(_token_url(), data=data, timeout=10)
        r.raise_for_status()
    except requests.HTTPError as e:
        detail = {"error": "token_exchange_failed", "status": r.status_code if "r" in locals() else 502}
        try:
            detail["body"] = r.json()
        except Exception:
            detail["body"] = getattr(r, "text", str(e))
        raise HTTPException(status_code=detail["status"], detail=detail)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    tokens = r.json()
    await _persist_tokens(request, response, tokens, user_email=username)

    # Return full token payload so Swagger/clients can set Authorization: Bearer ...
    return tokens


@router.post("/refresh")
async def refresh_grant(
    request: Request,
    response: Response,
    refresh_token: str = Form(..., alias="refresh_token"),
    grant_type: str = Form("refresh_token"),
):
    if grant_type != "refresh_token":
        raise HTTPException(status_code=400, detail="Unsupported grant_type")

    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": KC_CLIENT_ID,
    }
    if KC_CLIENT_SECRET:
        data["client_secret"] = KC_CLIENT_SECRET

    try:
        r = requests.post(_token_url(), data=data, timeout=10)
        r.raise_for_status()
    except requests.HTTPError as e:
        detail = {"error": "token_refresh_failed", "status": r.status_code if "r" in locals() else 502}
        try:
            detail["body"] = r.json()
        except Exception:
            detail["body"] = getattr(r, "text", str(e))
        raise HTTPException(status_code=detail["status"], detail=detail)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    tokens = r.json()
    await _persist_tokens(request, response, tokens)

    # Return full token payload for clients
    return tokens
