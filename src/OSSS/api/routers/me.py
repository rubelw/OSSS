from fastapi import APIRouter, Depends, HTTPException, status
from OSSS.auth.deps import get_current_user  # OAuth2-password based dep
from OSSS.settings import settings
from fastapi import APIRouter, Depends
from OSSS.auth.deps import ensure_access_token  # <-- add this import


router = APIRouter()

@router.get("/me", tags=["auth"])
async def me(access_token: str = Depends(ensure_access_token)):
    # call downstream APIs with Bearer access_token,
    # or decode locally if you only need claims
    return {"ok": True}
