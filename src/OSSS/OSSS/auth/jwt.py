# src/OSSS/auth/jwt.py
from __future__ import annotations

import time
import logging
from typing import Any, Dict

import httpx
from jose import jwt, JWTError
from fastapi import HTTPException, status

from OSSS.settings import settings

logger = logging.getLogger("auth")

# src/OSSS/auth/jwt.py (top of file where JWKS_URL/ISSUER are defined)
BASE = str(settings.KEYCLOAK_BASE_URL).rstrip("/")              # normalize
JWKS_URL = f"{BASE}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/certs"
ISSUER   = f"{BASE}/realms/{settings.KEYCLOAK_REALM}"

class JWKSCache:
    """Simple in-memory JWKS cache with TTL."""
    _jwks: Dict[str, Any] | None = None
    _at: float | None = None

    @classmethod
    async def get(cls) -> Dict[str, Any]:
        if (
            cls._jwks is None
            or cls._at is None
            or (time.time() - cls._at) > settings.JWKS_CACHE_SECONDS
        ):
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.get(JWKS_URL)
                r.raise_for_status()
                cls._jwks = r.json()
                cls._at = time.time()
        return cls._jwks

async def verify_and_decode(token: str) -> Dict[str, Any]:
    # Basic JWT shape: three segments
    if not isinstance(token, str) or token.count(".") != 2:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed bearer token (expected 3 segments).",
        )

    try:
        jwks = await JWKSCache.get()
        # Parse header to get kid
        try:
            headers = jwt.get_unverified_header(token)
        except JWTError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token header: {e}")

        kid = headers.get("kid")
        keys = jwks.get("keys", [])
        key = next((k for k in keys if k.get("kid") == kid), None)

        if key is None:
            # One forced refresh in case of rotation
            JWKSCache._at = None
            jwks = await JWKSCache.get()
            keys = jwks.get("keys", [])
            key = next((k for k in keys if k.get("kid") == kid), None)
            if key is None:
                logger.error("JWKS missing kid=%s; available kids=%s", kid, [k.get("kid") for k in keys])
                raise HTTPException(status_code=401, detail="No matching JWKS key for token kid")

        try:
            decoded = jwt.decode(
                token,
                key,  # JWK dict from JWKS
                algorithms=[key.get("alg", "RS256")],
                audience=settings.KEYCLOAK_AUDIENCE,
                issuer=ISSUER,
                options={"verify_aud": True, "verify_iss": True},
            )
        except JWTError as e:
            # signature/expiry/audience/issuer errors land here
            raise HTTPException(status_code=401, detail=f"Token verification failed: {e}")

        # Optional extra guards
        if settings.ACCEPTED_ISSUERS and decoded.get("iss") not in settings.ACCEPTED_ISSUERS:
            raise HTTPException(status_code=401, detail="Issuer not accepted")
        if settings.REQUIRE_AZP_MATCH and decoded.get("azp") != settings.KEYCLOAK_AUDIENCE:
            raise HTTPException(status_code=401, detail="azp mismatch")

        return decoded

    except HTTPException:
        raise
    except Exception as e:  # unexpected
        logger.exception("Unexpected token verification error")
        raise HTTPException(status_code=401, detail=f"Auth error: {e}")
