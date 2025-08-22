# src/OSSS/api/routers/me.py
from fastapi import APIRouter, Depends
from OSSS.auth.dependencies import require_auth

router = APIRouter(prefix="", tags=["auth"])

@router.get("/me")
def me(claims: dict = Depends(require_auth)):
    return {
        "sub": claims.get("sub"),
        "preferred_username": claims.get("preferred_username"),
        "email": claims.get("email"),
        "roles": (claims.get("realm_access") or {}).get("roles", []),
        "aud": claims.get("aud"),
        "azp": claims.get("azp"),
        "iss": claims.get("iss"),
    }
