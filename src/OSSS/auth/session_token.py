# src/OSSS/auth/session_token.py
import time
from fastapi import Depends, HTTPException, Request
from authlib.integrations.starlette_client import OAuthError
from OSSS.auth.oauth import oauth  # your Authlib OAuth instance

async def ensure_access_token(request: Request) -> str:
    sess = request.session.get("oidc") or {}
    rtok = sess.get("refresh_token")
    if not rtok:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Optionally refresh preemptively when close to expiry.
    exp = sess.get("expires_at")
    needs_refresh = not exp or (exp and exp < time.time() + 30)

    if needs_refresh:
        try:
            token = await oauth.keycloak.refresh_token(
                url=oauth.keycloak.client.server_metadata["token_endpoint"],
                refresh_token=rtok,
            )
        except OAuthError:
            # refresh no longer valid -> force login
            request.session.clear()
            raise HTTPException(status_code=401, detail="Session expired")

        # Persist new values (Authlib returns full token dict)
        request.session["oidc"] = {
            "refresh_token": token.get("refresh_token", rtok),
            "expires_at": token.get("expires_at"),
        }
        return token["access_token"]

    # If you chose to not store access_token at all, just refresh everytime:
    token = await oauth.keycloak.refresh_token(
        url=oauth.keycloak.client.server_metadata["token_endpoint"],
        refresh_token=rtok,
    )
    request.session["oidc"]["refresh_token"] = token.get("refresh_token", rtok)
    request.session["oidc"]["expires_at"] = token.get("expires_at")
    return token["access_token"]
