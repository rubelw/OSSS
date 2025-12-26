# src/OSSS/ai/api/routes/admin.py

from fastapi import APIRouter
from OSSS.ai.api.factory import clear_orchestration_cache

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)

@router.post("/cache/clear", summary="Clear LangGraph graph cache")
async def clear_cache():
    """
    Clear the compiled LangGraph graph cache (admin/debug endpoint).
    """
    return await clear_orchestration_cache()
