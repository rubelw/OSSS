# src/OSSS/auth/introspection.py
import httpx
from fastapi import HTTPException, status
from OSSS.settings import settings

INTROSPECT_URL = f"{settings.KEYCLOAK_BASE_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/token/introspect"

async def introspect(token: str) -> dict:
    if not settings.INTROSPECTION_CLIENT_ID or not settings.INTROSPECTION_CLIENT_SECRET:
        raise RuntimeError("Introspection not configured")
    data = {
        "token": token,
        "client_id": settings.INTROSPECTION_CLIENT_ID,
        "client_secret": settings.INTROSPECTION_CLIENT_SECRET,
    }
    async with httpx.AsyncClient(timeout=5) as c:
        r = await c.post(INTROSPECT_URL, data=data)
        r.raise_for_status()
        info = r.json()
        if not info.get("active"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive token")
        return info
