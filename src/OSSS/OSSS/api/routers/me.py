# src/OSSS/routers/me.py
from __future__ import annotations

import os
from fastapi import APIRouter, Depends, HTTPException, status, Request
from OSSS.auth import get_current_user
from OSSS.app_logger import get_logger

# Validator's effective config (what deps.py uses)
from OSSS.auth.deps import (
    ISSUER as OIDC_ISSUER_CFG,
    JWKS_URL as OIDC_JWKS_URL_CFG,
    AUDIENCE as OIDC_CLIENT_ID_CFG,
    OIDC_VERIFY_AUD as OIDC_VERIFY_AUD_CFG,
)

# Use the *same* resolver as auth_flow so /me diagnostics match token flows
try:
    from OSSS.api.routers.auth_flow import _discover  # cached resolver
except Exception:  # pragma: no cover
    _discover = None  # graceful degradation

router = APIRouter(tags=["me"])
log = get_logger("routers.me")

# Resolve “best” issuer/JWKS for diagnostics (prefers internal when available)
def _resolved_oidc_endpoints():
    # If an explicit internal JWKS is provided, prefer it for container->KC calls
    jwks_internal = os.getenv("OIDC_JWKS_URL_INTERNAL")

    disc_issuer = None
    disc_jwks = None
    if _discover is not None:
        try:
            disc = _discover()
            disc_issuer = disc.get("issuer")
            disc_jwks = disc.get("jwks_uri")
        except Exception as e:  # discovery can fail during boot
            log.debug("[/me] discovery failed in diagnostics: %s", e)

    # Choose JWKS: internal env > discovery > sensible internal default
    jwks_best = (
        jwks_internal
        or disc_jwks
        or "http://keycloak:8080/realms/OSSS/protocol/openid-connect/certs"
    )
    # Choose issuer: discovery issuer if present, else whatever deps is using
    issuer_best = disc_issuer or OIDC_ISSUER_CFG

    return issuer_best, jwks_best


@router.get("/me")
async def me(request: Request, user=Depends(get_current_user)):
    store = getattr(request.state, "session_store", None)

    # Simple per-request cache (optional)
    cache_key = None
    if store:
        q = "&".join(f"{k}={v}" for k, v in sorted(request.query_params.multi_items()))
        cache_key = f"list:{request.url.path}?{q}"
        cached = await store.get(cache_key)
        if cached:
            return cached

    # Request-level diagnostics (safe: lengths + names only)
    log.info("[/me] client=%s method=%s path=%s",
             request.client.host if request.client else "?",
             request.method, request.url.path)

    for h in ("authorization", "cookie", "host", "referer", "user-agent"):
        v = request.headers.get(h)
        log.info("[/me] header %s: %s", h, f"present len={len(v)}" if v else "missing")

    if "cookie" in request.headers:
        try:
            names = list(request.cookies.keys())
            log.info("[/me] cookie names: %s", names)
        except Exception:
            pass

    # OIDC config snapshot — BOTH validator config and internally-resolved endpoints
    issuer_best, jwks_best = _resolved_oidc_endpoints()
    log.info("[/me] OIDC cfg (validator): issuer=%r jwks_url=%r client_id=%r verify_aud=%s",
             OIDC_ISSUER_CFG, OIDC_JWKS_URL_CFG, OIDC_CLIENT_ID_CFG, OIDC_VERIFY_AUD_CFG)
    log.info("[/me] OIDC cfg (resolved ): issuer=%r jwks_url=%r",
             issuer_best, jwks_best)

    # Outcome
    if not user:
        log.warning("[/me] get_current_user -> None (unauthenticated)")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    roles = sorted(list(user.get("_roles", [])))[:10]
    log.info("[/me] OK sub=%s email=%s roles=%s",
             user.get("sub"), user.get("email"), roles)

    result = user
    if store and cache_key:
        await store.set(cache_key, result, ttl_sec=60)

    return result
