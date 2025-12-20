from fastapi import APIRouter, Depends, HTTPException, Query
from OSSS.ai.additional_index import force_reload, INDEX_KINDS
from OSSS.ai.observability import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/ai/a2a",
    tags=["ai-a2a"],
)

# ---- Admin guard (Step 2-ish, but safe) ----

try:
    # If you already have a real a2a dependency, use it here.
    # Adjust the import / name to match your repo, e.g.:
    #   from OSSS.auth.deps import require_admin
    from OSSS.auth.deps import require_admin  # type: ignore


    def _admin_guard(user=Depends(require_admin)):
        """
        Real guard in "normal" app runs: uses your Keycloak / RBAC.
        """
        logger.debug(f"Admin guard invoked. User: {user}")
        return user

except Exception:
    # Fallback for local-dev / tests where auth isn't wired up
    def _admin_guard():
        """
        Dev-only guard: ALWAYS ALLOWS the call.
        Replace with something stricter later if you want.
        """
        logger.debug("Dev-only admin guard invoked. Always allows the call.")
        return True


@router.post("/reload-additional-index")
def reload_additional_index(
        _=Depends(_admin_guard),
        index: str = Query(
            "main",
            description=f"Which additional index to reload. One of: {', '.join(INDEX_KINDS)}",
        ),
):
    """
    Reload the additional_llm_data embeddings index from disk.

    Call this after running the management menu option that rebuilds:
      - vector_indexes/main/embeddings.jsonl   (index=main)
      - vector_indexes/tutor/embeddings.jsonl  (index=tutor)
      - vector_indexes/agent/embeddings.jsonl  (index=agent)
    """
    logger.info(f"Received request to reload additional index: {index}")

    if index not in INDEX_KINDS:
        logger.warning(f"Invalid index requested: {index}. Expected one of: {', '.join(INDEX_KINDS)}")
        raise HTTPException(
            status_code=400,
            detail=f"Unknown index '{index}'. Expected one of: {', '.join(INDEX_KINDS)}",
        )

    logger.debug(f"Index '{index}' is valid. Proceeding to reload.")

    try:
        count = force_reload(index=index)
        logger.info(f"Successfully reloaded index '{index}'. Number of chunks loaded: {count}.")
        return {"status": "ok", "index": index, "chunks_loaded": count}
    except Exception as e:
        logger.error(f"Failed to reload index '{index}': {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while reloading the index: {str(e)}",
        )
