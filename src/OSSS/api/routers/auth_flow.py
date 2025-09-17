# src/OSSS/api/routers/auth_flow.py
from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional, Dict, Any
import time
import requests
from requests import exceptions as req_exc
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
def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(name, default)

# External/public issuer (what Keycloak advertises in tokens)
KC_ISSUER = _env("KEYCLOAK_ISSUER") or _env("OIDC_ISSUER")

# Internal endpoints for container-to-container calls (recommended)
KC_DISCOVERY_URL_INTERNAL = _env("OIDC_DISCOVERY_URL_INTERNAL")
KC_TOKEN_URL_INTERNAL = _env("OIDC_TOKEN_URL_INTERNAL")
KC_JWKS_URL = _env("OIDC_JWKS_URL")  # optional; not required here but kept for completeness

KC_CLIENT_ID = _env("KEYCLOAK_CLIENT_ID", "osss-api")
KC_CLIENT_SECRET = _env("KEYCLOAK_CLIENT_SECRET")  # optional (confidential client)

def _get_with_retry(url: str, tries: int = 5, base_sleep: float = 0.2):
    for i in range(tries):
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            return r
        except req_exc.RequestException as e:
            if i == tries - 1:
                raise
            time.sleep(min(base_sleep * (2 ** i), 2.0))

@lru_cache(maxsize=1)
def _discover() -> Dict[str, str]:
    """
    Resolve OIDC endpoints preferring internal URLs for network calls,
    while allowing the issuer to remain the public/external value.
    """

    # Shortcut: if both internal endpoints are provided, skip discovery
    if KC_TOKEN_URL_INTERNAL and KC_JWKS_URL:
        resolved = {
            "issuer": KC_ISSUER,
            "token_endpoint": KC_TOKEN_URL_INTERNAL,
            "jwks_uri": KC_JWKS_URL,
        }
        log.debug(
            "OIDC discovery shortcut via env: token=%s jwks=%s issuer=%s",
            resolved["token_endpoint"], resolved["jwks_uri"], resolved["issuer"]
        )
        return resolved

    # Prefer internal discovery; otherwise derive from external issuer
    discovery_url = KC_DISCOVERY_URL_INTERNAL or (
        KC_ISSUER and KC_ISSUER.rstrip("/") + "/.well-known/openid-configuration"
    )
    if not discovery_url:
        raise RuntimeError(
            "OIDC discovery not configured. Set OIDC_DISCOVERY_URL_INTERNAL "
            "or KEYCLOAK_ISSUER / OIDC_ISSUER."
        )

    try:
        r = _get_with_retry(discovery_url)
        data = r.json()
    except req_exc.RequestException as e:
        log.error("OIDC discovery fetch failed from %s: %s", discovery_url, e)
        raise HTTPException(status_code=502, detail="keycloak_discovery_error")

    token_endpoint = KC_TOKEN_URL_INTERNAL or data.get("token_endpoint")
    if not token_endpoint:
        if KC_ISSUER:
            token_endpoint = KC_ISSUER.rstrip("/") + "/protocol/openid-connect/token"
        else:
            raise HTTPException(status_code=502, detail="token_endpoint_unresolved")

    resolved = {
        "issuer": data.get("issuer") or KC_ISSUER,
        "token_endpoint": token_endpoint,
        "jwks_uri": KC_JWKS_URL or data.get("jwks_uri"),
    }
    log.debug(
        "OIDC discovery resolved: discovery=%s token_endpoint=%s issuer=%s",
        discovery_url, resolved["token_endpoint"], resolved["issuer"]
    )
    return resolved

def _token_url() -> str:
    return _discover()["token_endpoint"]


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
    except req_exc.HTTPError:
        status = getattr(r, "status_code", 502)  # type: ignore[name-defined]
        detail = {"error": "token_exchange_failed", "status": status}
        try:
            detail["body"] = r.json()  # type: ignore[name-defined]
        except Exception:
            detail["body"] = getattr(r, "text", "")  # type: ignore[name-defined]
        raise HTTPException(status_code=status, detail=detail)
    except req_exc.ConnectionError:
        raise HTTPException(status_code=502, detail="keycloak_connect_error")
    except (req_exc.ConnectTimeout, req_exc.ReadTimeout, req_exc.Timeout):
        raise HTTPException(status_code=504, detail="keycloak_timeout")
    except req_exc.RequestException as e:
        raise HTTPException(status_code=502, detail=f"keycloak_request_error: {e}")

    tokens = r.json()
    await _persist_tokens(request, response, tokens, user_email=username)
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
    except req_exc.HTTPError:
        status = getattr(r, "status_code", 502)  # type: ignore[name-defined]
        detail = {"error": "token_refresh_failed", "status": status}
        try:
            detail["body"] = r.json()  # type: ignore[name-defined]
        except Exception:
            detail["body"] = getattr(r, "text", "")  # type: ignore[name-defined]
        raise HTTPException(status_code=status, detail=detail)
    except req_exc.ConnectionError:
        raise HTTPException(status_code=502, detail="keycloak_connect_error")
    except (req_exc.ConnectTimeout, req_exc.ReadTimeout, req_exc.Timeout):
        raise HTTPException(status_code=504, detail="keycloak_timeout")
    except req_exc.RequestException as e:
        raise HTTPException(status_code=502, detail=f"keycloak_request_error: {e}")

    tokens = r.json()
    await _persist_tokens(request, response, tokens)
    return tokens
