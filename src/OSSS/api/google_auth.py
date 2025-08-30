# src/OSSS/api/google_auth.py
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
import google.oauth2.credentials
import googleapiclient.discovery
from OSSS.core.settings_google import GoogleSettings
from starlette.responses import JSONResponse
from OSSS.db.session import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

router = APIRouter(prefix="/api/google", tags=["google"])

SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.rosters.readonly",
]

@router.get("/login")
def google_login(settings: GoogleSettings = Depends()):
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uris": [str(settings.google_oauth_redirect_uri)],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
    )
    flow.redirect_uri = str(settings.google_oauth_redirect_uri)
    auth_url, state = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent")
    # store `state` in server-side session or signed cookie to verify later
    return RedirectResponse(auth_url)

@router.get("/callback")
async def google_callback(request: Request, db: AsyncSession = Depends(get_session), settings: GoogleSettings = Depends()):
    # verify state with your session/cookie
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uris": [str(settings.google_oauth_redirect_uri)],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
    )
    flow.redirect_uri = str(settings.google_oauth_redirect_uri)

    code = request.query_params.get("code")
    if not code:
        raise HTTPException(400, "Missing code")

    flow.fetch_token(code=code)
    creds = flow.credentials

    # persist creds to DB for the logged-in OSSS user (you’ll have your own auth/user resolution)
    # upsert GoogleAccount for user_id
    # ...

    return JSONResponse({"status": "ok"})
