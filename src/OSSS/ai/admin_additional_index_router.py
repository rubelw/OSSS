# src/OSSS/ai/admin_additional_index_router.py
from fastapi import APIRouter, Depends
from OSSS.ai.additional_index import force_reload

router = APIRouter(
    prefix="/ai/admin",
    tags=["ai-admin"],
)


# TODO: replace this with your real auth/permission dependency later
def _debug_admin_guard():
    # e.g., verify current user is CTO, etc.
    return True


@router.post("/reload-additional-index")
def reload_additional_index(_=Depends(_debug_admin_guard)):
    """
    Reload the additional_llm_data embeddings index from disk.

    Call this after running the management menu option that rebuilds
    vector_index_additional_llm_data/embeddings.jsonl.
    """
    count = force_reload()
    return {"status": "ok", "chunks_loaded": count}
