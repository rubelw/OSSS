# src/OSSS/routers/me.py
from fastapi import APIRouter, Depends, HTTPException, status, Request
from OSSS.auth import get_current_user
from OSSS.app_logger import get_logger

# Use the SAME values your validator uses (from deps) for accurate diagnostics
from OSSS.auth.deps import (
    ISSUER as OIDC_ISSUER_CFG,
    JWKS_URL as OIDC_JWKS_URL_CFG,
    AUDIENCE as OIDC_CLIENT_ID_CFG,
    OIDC_VERIFY_AUD as OIDC_VERIFY_AUD_CFG,
)

router = APIRouter(tags=["me"])
log = get_logger("routers.me")

@router.get("/me")
async def me(request: Request, user = Depends(get_current_user)):
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

    # OIDC config snapshot — pulled from deps (single source of truth)
    log.info("[/me] OIDC cfg issuer=%r jwks_url=%r client_id=%r verify_aud=%s",
             OIDC_ISSUER_CFG, OIDC_JWKS_URL_CFG, OIDC_CLIENT_ID_CFG, OIDC_VERIFY_AUD_CFG)

    # Outcome
    if not user:
        log.warning("[/me] get_current_user -> None (unauthenticated)")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    roles = sorted(list(user.get("_roles", [])))[:10]
    log.info("[/me] OK sub=%s email=%s roles=%s",
             user.get("sub"), user.get("email"), roles)

    # ✅ fix: define result before caching
    result = user
    if store and cache_key:
        await store.set(cache_key, result, ttl_sec=60)

    return result
