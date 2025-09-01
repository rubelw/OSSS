# src/OSSS/auth/routes.py
from fastapi import APIRouter, Request, HTTPException
from starlette.responses import RedirectResponse
from OSSS.settings import settings
from OSSS.auth.oauth import oauth  # your registered Authlib client
# import the expiry helpers used by ensure_access_token()
from OSSS.auth.session_token import _access_expires_at, _refresh_expires_at

router = APIRouter()

@router.get("/auth/callback")
async def auth_callback(request: Request):
    """
    Handle Keycloak OIDC callback:
      - exchange code for tokens
      - persist both access & refresh tokens with absolute expirations
      - include minimal profile fields, optional
    """
    try:
        token = await oauth.keycloak.authorize_access_token(request)
    except Exception as e:
        # could be OAuthError from Authlib; keep generic to avoid leaking details
        raise HTTPException(status_code=401, detail="Authentication failed")

    # Build session payload capable of surviving restarts
    request.session["oidc"] = {
        # required for continued auth across restarts
        "access_token": token.get("access_token"),
        "access_expires_at": _access_expires_at(token),            # absolute epoch (int)
        "refresh_token": token.get("refresh_token"),
        "refresh_expires_at": _refresh_expires_at(token, None),    # may be None if KC didn't return it

        # optional but handy
        "token_type": token.get("token_type"),
        "scope": token.get("scope"),
        "id_token": token.get("id_token"),

        # optional profile fields if present in token["userinfo"]
        "sub": (token.get("userinfo") or {}).get("sub") or "",
        "email": (token.get("userinfo") or {}).get("email") or "",
    }

    # Redirect home (or use settings.LOGIN_REDIRECT_URL if you have one)
    return RedirectResponse(url=getattr(settings, "LOGIN_REDIRECT_URL", "/"))
