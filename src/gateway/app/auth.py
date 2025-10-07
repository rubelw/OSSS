import time
import httpx
from jose import jwt
from jose.exceptions import JWTError
from fastapi import HTTPException, status, Request
from functools import lru_cache
from tenacity import retry, stop_after_attempt, wait_exponential
from .config import settings

class OIDCVerifier:
    def __init__(self, issuer: str, audience: str, cache_seconds: int = 3600):
        self.issuer = issuer.rstrip('/')
        self.audience = audience
        self.cache_seconds = cache_seconds
        self._jwks = None
        self._jwks_expiry = 0

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=0.5, max=3))
    async def _get_openid_config(self):
        url = f"{self.issuer}/.well-known/openid-configuration"
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=0.5, max=3))
    async def _refresh_jwks(self, jwks_uri: str):
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(jwks_uri)
            r.raise_for_status()
            self._jwks = r.json()
            self._jwks_expiry = int(time.time()) + self.cache_seconds

    async def ensure_jwks(self):
        now = int(time.time())
        if self._jwks and now < self._jwks_expiry:
            return
        config = await self._get_openid_config()
        await self._refresh_jwks(config["jwks_uri"])

    async def verify(self, token: str):
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
        await self.ensure_jwks()
        try:
            claims = jwt.decode(
                token,
                self._jwks,  # jose can take JWKS dict
                options={"verify_aud": bool(self.audience)},
                audience=self.audience if self.audience else None,
                issuer=self.issuer,
                algorithms=["RS256", "ES256", "PS256"],
            )
            return claims
        except JWTError as e:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}")

verifier: OIDCVerifier | None = None
if settings.OIDC_ISSUER and settings.OIDC_AUDIENCE:
    verifier = OIDCVerifier(settings.OIDC_ISSUER, settings.OIDC_AUDIENCE, settings.OIDC_JWKS_CACHE_SECONDS)

async def require_auth(request: Request):
    if verifier is None:
        return None  # auth disabled
    authz = request.headers.get("Authorization", "")
    if not authz.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Expected Bearer token")
    token = authz.split(" ", 1)[1]
    return await verifier.verify(token)
