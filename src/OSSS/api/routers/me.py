from fastapi import APIRouter, Depends, HTTPException, status
from OSSS.auth.deps import get_current_user  # OAuth2-password based dep
from OSSS.settings import settings

router = APIRouter()

@router.get("/me", tags=["auth"])
async def me(user: dict = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token = user.get("token") or {}
    return {
        "sub": user.get("sub"),
        "email": user.get("email"),
        "preferred_username": user.get("preferred_username"),
        "roles": sorted(list(user.get("roles") or [])),
        "iss": token.get("iss"),
        "aud": token.get("aud"),
        "azp": token.get("azp"),
    }
