# src/OSSS/auth/routes.py (example)
from fastapi import APIRouter, Request, HTTPException
from OSSS.settings import settings
# if using Authlib:
from OSSS.auth.oauth import oauth  # your registered client

router = APIRouter()

@router.get("/auth/callback")
async def auth_callback(request: Request):
    # Exchange code for tokens
    token = await oauth.keycloak.authorize_access_token(request)
    # token includes: access_token, refresh_token, expires_at, etc.

    # You can keep just the essentials to save cookie size:
    request.session["oidc"] = {
        "refresh_token": token.get("refresh_token"),
        "expires_at": token.get("expires_at"),               # optional
        "id_token": token.get("id_token"),                   # optional
        "sub": token.get("userinfo", {}).get("sub") or "",   # optional
        "email": token.get("userinfo", {}).get("email") or ""
    }
    return RedirectResponse(url="/")  # or wherever
