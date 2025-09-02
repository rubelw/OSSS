from fastapi import APIRouter, Depends, HTTPException, status, Request
from OSSS.auth import get_current_user
from OSSS.app_logger import get_logger
import os

router = APIRouter(tags=["me"])
log = get_logger("routers.me")

@router.get("/me")
async def me(request: Request, user = Depends(get_current_user)):
    # Request-level diagnostics
    log.info("[/me] client=%s method=%s path=%s", request.client.host if request.client else "?", request.method, request.url.path)

    # Header presence/lengths
    for h in ("authorization", "cookie", "host", "referer", "user-agent"):
        v = request.headers.get(h)
        if v:
            log.info("[/me] header %s: present len=%d", h, len(v))
        else:
            log.info("[/me] header %s: missing", h)

    # Cookie names (don’t log values)
    if "cookie" in request.headers:
        try:
            names = list(request.cookies.keys())
            log.info("[/me] cookie names: %s", names)
        except Exception:
            pass

    # OIDC config snapshot (helps spot missing JWKS quickly)
    log.info("[/me] OIDC cfg issuer=%r jwks_url=%r client_id=%r verify_aud=%s",
             os.getenv("OIDC_ISSUER") or os.getenv("KEYCLOAK_ISSUER"),
             os.getenv("OIDC_JWKS_URL"),
             os.getenv("OIDC_CLIENT_ID"),
             os.getenv("OIDC_VERIFY_AUD"))

    # Outcome
    if not user:
        log.warning("[/me] get_current_user -> None (unauthenticated)")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    log.info("[/me] OK sub=%s email=%s roles=%s",
             user.get("sub"), user.get("email"), sorted(list(user.get("_roles", [])))[:10])

    return user
