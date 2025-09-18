# src/OSSS/auth/keycloak_refresh.py
from __future__ import annotations
import time
from typing import Any, Dict, Optional
import httpx
import logging
import os

log = logging.getLogger(__name__)

KC_TOKEN_URL = os.getenv("KEYCLOAK_TOKEN_URL")  # e.g. http://localhost:8080/realms/OSSS/protocol/openid-connect/token
KC_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID")
KC_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET")  # optional if public

async def refresh_access_token(refresh_token: str) -> Optional[Dict[str, Any]]:
    data = {
        "grant_type": "refresh_token",
        "client_id": KC_CLIENT_ID,
        "refresh_token": refresh_token,
    }
    if KC_CLIENT_SECRET:
        data["client_secret"] = KC_CLIENT_SECRET

    async with httpx.AsyncClient(timeout=10) as ac:
        r = await ac.post(KC_TOKEN_URL, data=data)
        if r.status_code != 200:
            log.warning("Keycloak refresh failed %s: %s", r.status_code, r.text[:300])
            return None
        tok = r.json()
        now = int(time.time())
        tok["obtained_at"] = now
        tok["expires_at"] = now + int(tok.get("expires_in", 300))
        # Keycloak may include refresh_expires_in; respect it if present
        rei = tok.get("refresh_expires_in")
        if rei is not None:
            tok["refresh_expires_at"] = now + int(rei)
        return tok
