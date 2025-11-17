# src/OSSS/ai/admin_additional_index_router.py
from fastapi import APIRouter, Depends, HTTPException

from OSSS.ai.additional_index import force_reload

router = APIRouter(
    prefix="/ai/admin",
    tags=["ai-admin"],
)

# ---- Admin guard (Step 2-ish, but safe) ----

try:
    # If you already have a real admin dependency, use it here.
    # Adjust the import / name to match your repo, e.g.:
    #   from OSSS.auth.deps import require_admin
    from OSSS.auth.deps import require_admin  # type: ignore

    def _admin_guard(user=Depends(require_admin)):
        """
        Real guard in "normal" app runs: uses your Keycloak / RBAC.
        """
        return user

except Exception:
    # Fallback for local-dev / tests where auth isn't wired up
    def _admin_guard():
        """
        Dev-only guard: ALWAYS ALLOWS the call.
        Replace with something stricter later if you want.
        """
        return True


@router.post("/reload-additional-index")
def reload_additional_index(_=Depends(_admin_guard)):
    """
    Reload the additional_llm_data embeddings index from disk.

    Call this after running the management menu option that rebuilds
    vector_indexes/main/embeddings.jsonl.
    """
    count = force_reload()
    return {"status": "ok", "chunks_loaded": count}
