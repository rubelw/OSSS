# src/OSSS/auth/keycloak.py
from __future__ import annotations
from typing import Any, Dict
from OSSS.core.config import settings
import requests

def token_endpoint() -> str:
    return f"{settings.KEYCLOAK_BASE_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/token"

def auth_endpoint() -> str:
    return f"{settings.KEYCLOAK_BASE_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/auth"

def introspect(token: str) -> Dict[str, Any]:
    """Keycloak token introspection using confidential client creds."""
    data = {
        "token": token,
        "client_id": settings.KEYCLOAK_CLIENT_ID,
        "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
    }
    try:
        r = requests.post(
            f"{settings.KEYCLOAK_BASE_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/token/introspect",
            data=data,
            timeout=10,
        )
    except requests.RequestException:
        raise RuntimeError("Keycloak introspection unavailable")

    if r.status_code != 200:
        raise PermissionError("Token introspection failed")

    payload = r.json()
    if not payload.get("active"):
        raise PermissionError("Inactive token")

    iss = payload.get("iss")
    expected_iss = f"{settings.KEYCLOAK_BASE_URL}/realms/{settings.KEYCLOAK_REALM}"
    if iss != expected_iss:
        raise PermissionError("Token issuer mismatch")

    # audience / azp check
    aud = payload.get("aud")
    azp = payload.get("azp")
    allowed = settings.KEYCLOAK_ALLOWED_AUDIENCES
    if isinstance(aud, str):
        aud_ok = aud in allowed
    else:
        aud_ok = bool(aud and any(a in allowed for a in aud))
    if not aud_ok and azp not in allowed:
        raise PermissionError("Audience not allowed")

    return payload
