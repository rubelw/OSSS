# src/OSSS/api/routers/auth_flow.py
from __future__ import annotations

import os
from functools import lru_cache
import time
import requests
from requests import exceptions as req_exc
from fastapi import APIRouter, Request, Response, Form, HTTPException
from typing import Optional, Dict, Any, Iterable
from urllib.parse import urlparse, urlunparse

from OSSS.app_logger import get_logger
from OSSS.sessions import (
    ensure_sid_cookie_and_store,
    get_session_store,
    record_tokens_to_session,
)

log = get_logger("auth_flow")
router = APIRouter()

# ---- env helpers -------------------------------------------------------------
def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(name, default)

def _mask_email(email: Optional[str]) -> str:
    if not email:
        return ""
    try:
        user, domain = email.split("@", 1)
        head = user[:2]
        tail = user[-1:] if len(user) > 2 else ""
        return f"{head}***{tail}@{domain}"
    except Exception:
        return "***"

# ---- consistency/guardrails --------------------------------------------------
def _same_origin(a: Optional[str], b: Optional[str]) -> bool:
    pa, pb = urlparse(a or ""), urlparse(b or "")
    return (pa.scheme, pa.hostname, pa.port) == (pb.scheme, pb.hostname, pb.port)

def _assert_consistent(issuer: Optional[str], token: Optional[str], jwks: Optional[str]) -> None:
    if not token:
        raise HTTPException(status_code=502, detail="token_endpoint_unresolved")
    if jwks and not _same_origin(token, jwks):
        raise RuntimeError(f"OIDC endpoints mismatch (token vs jwks): {token} vs {jwks}")
    if issuer:
        pi, pt = urlparse(issuer), urlparse(token)
        if pi.scheme != pt.scheme:
            raise RuntimeError(f"Issuer/token scheme mismatch: {issuer} vs {token}")

def _upgrade_http_8443(u: Optional[str]) -> Optional[str]:
    """Auto-upgrade http://...:8443 to https://...:8443 (common misconfig)."""
    if not u:
        return u
    p = urlparse(u)
    if p.scheme == "http" and (p.port == 8443 or (p.netloc or "").endswith(":8443")):
        new = urlunparse(("https", p.netloc, p.path, p.params, p.query, p.fragment))
        log.warning("Upgrading OIDC URL from HTTP on TLS port 8443: %s -> %s", u, new)
        return new
    return u


# ---- OIDC / Keycloak config --------------------------------------------------
# External/public issuer (what Keycloak advertises in tokens)
KC_ISSUER = _env("KEYCLOAK_ISSUER") or _env("OIDC_ISSUER")

# Internal endpoints for container-to-container calls (recommended)
KC_DISCOVERY_URL_INTERNAL = _env("OIDC_DISCOVERY_URL_INTERNAL")
KC_TOKEN_URL_INTERNAL = _env("OIDC_TOKEN_URL_INTERNAL")

# Secondary fallback: public/external explicit token URL if provided
KC_TOKEN_URL_PUBLIC = _env("OIDC_TOKEN_URL")

KC_JWKS_URL = _env("OIDC_JWKS_URL")  # optional; not required here but kept for completeness

KC_CLIENT_ID = _env("KEYCLOAK_CLIENT_ID", "osss-api")
KC_CLIENT_SECRET = _env("KEYCLOAK_CLIENT_SECRET")  # optional (confidential client)

# ---- HTTP with retry ---------------------------------------------------------
_TRANSIENT_STATUSES: Iterable[int] = (502, 503, 504)

_session = requests.Session()
_session.headers.update({"Accept": "application/json"})

def _sleep_backoff(i: int, base: float = 0.2, cap: float = 2.0) -> None:
    time.sleep(min(base * (2 ** i), cap))

def _get_with_retry(url: str, tries: int = 5, base_sleep: float = 0.2):
    for i in range(tries):
        try:
            r = _session.get(url, timeout=10)
            r.raise_for_status()
            return r
        except req_exc.HTTPError as e:
            status = getattr(e.response, "status_code", None)
            if status in _TRANSIENT_STATUSES and i < tries - 1:
                _sleep_backoff(i, base_sleep)
                continue
            raise
        except (req_exc.ConnectTimeout, req_exc.ReadTimeout, req_exc.ConnectionError):
            if i == tries - 1:
                raise
            _sleep_backoff(i, base_sleep)

def _post_form_with_retry(url: str, data: Dict[str, Any], tries: int = 4, base_sleep: float = 0.25):
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    for i in range(tries):
        try:
            r = _session.post(url, data=data, headers=headers, timeout=10)
            # If KC returns 4xx, that's not transient—raise immediately.
            if 400 <= r.status_code < 500:
                r.raise_for_status()
            # For 5xx, allow retries.
            if r.status_code in _TRANSIENT_STATUSES and i < tries - 1:
                _sleep_backoff(i, base_sleep)
                continue
            r.raise_for_status()
            return r
        except req_exc.HTTPError as e:
            status = getattr(e.response, "status_code", None)
            if status in _TRANSIENT_STATUSES and i < tries - 1:
                _sleep_backoff(i, base_sleep)
                continue
            raise
        except (req_exc.ConnectTimeout, req_exc.ReadTimeout, req_exc.ConnectionError):
            if i == tries - 1:
                raise
            _sleep_backoff(i, base_sleep)

# ---- discovery / endpoint resolution -----------------------------------------
@lru_cache(maxsize=1)
def _discover() -> Dict[str, str]:
    """
    Resolve OIDC endpoints preferring internal URLs for network calls,
    while allowing the issuer to remain the public/external value.

    Resolution order for token endpoint:
        A) If OIDC_TOKEN_URL_INTERNAL is set -> use it.
        B) Else if we used OIDC_DISCOVERY_URL_INTERNAL -> derive token URL from that internal base.
        C) Else use discovery's token_endpoint unless it points to localhost.
        D) Else fall back to OIDC_TOKEN_URL (public) or issuer-derived token URL.
    """
    # Shortcut: if both internal token and jwks are provided, skip discovery
    if KC_TOKEN_URL_INTERNAL and KC_JWKS_URL:
        token_ep = _upgrade_http_8443(KC_TOKEN_URL_INTERNAL)
        jwks_uri = _upgrade_http_8443(KC_JWKS_URL)
        _assert_consistent(KC_ISSUER, token_ep, jwks_uri)

        resolved = {
            "issuer": KC_ISSUER,
            "token_endpoint": token_ep,
            "jwks_uri": jwks_uri,
        }

        log.debug(
            "OIDC discovery shortcut via env: token=%s jwks=%s issuer=%s",
            resolved["token_endpoint"], resolved["jwks_uri"], resolved["issuer"]
        )
        return resolved

    discovery_url = KC_DISCOVERY_URL_INTERNAL or (
        KC_ISSUER and KC_ISSUER.rstrip("/") + "/.well-known/openid-configuration"
    )

    data: Dict[str, Any] = {}
    if discovery_url:
        try:
            r = _get_with_retry(discovery_url)
            data = r.json() or {}
        except req_exc.RequestException as e:
            log.error("OIDC discovery fetch failed from %s: %s", discovery_url, e)
            data = {}

    # Helper: build an internal token URL from an internal discovery URL
    token_from_internal_discovery: Optional[str] = None
    if KC_DISCOVERY_URL_INTERNAL and KC_DISCOVERY_URL_INTERNAL in (discovery_url or ""):
        # e.g. http://keycloak:8080/realms/OSSS/.well-known/openid-configuration
        # -> http://keycloak:8080/realms/OSSS/protocol/openid-connect/token
        try:
            base = discovery_url.split("/.well-known/")[0].rstrip("/")
            token_from_internal_discovery = f"{base}/protocol/openid-connect/token"
        except Exception:
            token_from_internal_discovery = None

    disc_token = (data.get("token_endpoint") or "").strip()

    def _is_localhost(u: str) -> bool:
        return "://localhost:" in u or "://127.0.0.1:" in u

    # Resolution order
    token_endpoint = (
        KC_TOKEN_URL_INTERNAL
        or token_from_internal_discovery
        or (disc_token if disc_token and not _is_localhost(disc_token) else None)
        or KC_TOKEN_URL_PUBLIC
        or (KC_ISSUER and KC_ISSUER.rstrip("/") + "/protocol/openid-connect/token")
    )

    if not token_endpoint:
        raise HTTPException(status_code=502, detail="token_endpoint_unresolved")

    # Prefer external/public issuer from discovery if present; otherwise env
    issuer = data.get("issuer") or KC_ISSUER

    # Warn if the discovery doc advertises localhost values
    if disc_token and _is_localhost(disc_token):
        log.warning(
            "Discovery advertised localhost token_endpoint (%s); overriding to %s",
            disc_token, token_endpoint
        )

    # Auto-upgrade accidental http://...:8443 to https://...:8443 (common foot-gun)
    token_endpoint = _upgrade_http_8443(token_endpoint)
    jwks_uri = _upgrade_http_8443(KC_JWKS_URL or data.get("jwks_uri"))

    # Validate consistency (fail-fast instead of 502 later)
    _assert_consistent(issuer, token_endpoint, jwks_uri)

    # Auto-upgrade accidental http://...:8443 and then validate
    token_endpoint = _upgrade_http_8443(token_endpoint)
    jwks_uri = _upgrade_http_8443(KC_JWKS_URL or data.get("jwks_uri"))
    _assert_consistent(issuer, token_endpoint, jwks_uri)

    resolved = {
        "issuer": issuer,
        "token_endpoint": token_endpoint,
        "jwks_uri": jwks_uri,
    }

    log.debug(
        "OIDC discovery resolved: discovery=%s token_endpoint=%s issuer=%s",
        discovery_url, resolved["token_endpoint"], resolved["issuer"]
    )
    return resolved


@lru_cache(maxsize=1)
def _token_url() -> str:
    url = _discover()["token_endpoint"]
    # Log once; extremely helpful when a container accidentally uses localhost:8080
    log.info("OIDC token endpoint in use: %s", url)
    return url

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

    log.debug("/auth/token: requesting tokens for %s", _mask_email(username))

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

    url = _token_url()
    try:
        r = _post_form_with_retry(url, data=data)
    except req_exc.HTTPError as e:
        resp = e.response
        status = getattr(resp, "status_code", 502)
        detail = {"error": "token_exchange_failed", "status": status}
        try:
            detail["body"] = resp.json()
        except Exception:
            detail["body"] = getattr(resp, "text", "")
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

    url = _token_url()
    try:
        r = _post_form_with_retry(url, data=data)
    except req_exc.HTTPError as e:
        resp = e.response
        status = getattr(resp, "status_code", 502)
        detail = {"error": "token_refresh_failed", "status": status}
        try:
            detail["body"] = resp.json()
        except Exception:
            detail["body"] = getattr(resp, "text", "")
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
