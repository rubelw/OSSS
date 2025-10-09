# e.g., src/OSSS/api/debug.py
from fastapi import APIRouter, Depends, HTTPException, status
from OSSS.auth.jwt import verify_and_decode
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from OSSS.auth.roles import extract_roles
from OSSS.settings import settings

router = APIRouter(prefix="/debug", tags=["_debug"])
bearer = HTTPBearer(auto_error=False)

@router.get("/me")
async def me(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    if not creds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    decoded = await verify_and_decode(creds.credentials)
    return {
        "iss": decoded.get("iss"),
        "aud": decoded.get("aud"),
        "azp": decoded.get("azp"),
        "preferred_username": decoded.get("preferred_username"),
        "roles": sorted(list(extract_roles(decoded, settings.KEYCLOAK_AUDIENCE))),
    }
