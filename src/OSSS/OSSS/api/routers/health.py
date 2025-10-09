# src/OSSS/api/routers/health.py
from fastapi import APIRouter
router = APIRouter(tags=["health"])

@router.get("/healthz", include_in_schema=False)
def healthz():
    return {"status": "ok"}
