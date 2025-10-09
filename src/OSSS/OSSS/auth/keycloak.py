# src/OSSS/auth/keycloak.py
from __future__ import annotations
from typing import Any, Dict
from OSSS.core.config import settings
import requests
import httpx  # NEW
from .tokens import TokenSet  # NEW


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


# --- NEW: refresh support -----------------------------------------------------

class RefreshError(Exception):
    """Raised when Keycloak token refresh fails."""


async def refresh_with_keycloak(refresh_token: str) -> TokenSet:
    """
    Refresh tokens via Keycloak using confidential client credentials.

    Returns:
        TokenSet: parsed from the OIDC token response.

    Raises:
        RefreshError: if configuration is missing or the refresh call fails.
    """
    if not all(
        [
            settings.KEYCLOAK_BASE_URL,
            settings.KEYCLOAK_REALM,
            settings.KEYCLOAK_CLIENT_ID,
            settings.KEYCLOAK_CLIENT_SECRET,
        ]
    ):
        raise RefreshError("Keycloak configuration is incomplete")

    data = {
        "grant_type": "refresh_token",
        "client_id": settings.KEYCLOAK_CLIENT_ID,
        "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
        "refresh_token": refresh_token,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(token_endpoint(), data=data)
    except httpx.HTTPError as e:
        raise RefreshError(f"KC refresh unavailable: {e}") from e

    if resp.status_code != 200:
        raise RefreshError(f"KC refresh failed: {resp.status_code} {resp.text}")

    payload = resp.json()
    return TokenSet.from_oidc_response(payload)
