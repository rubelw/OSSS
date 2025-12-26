from typing import Any, Dict, List
from langgraph.runtime import Runtime

from OSSS.ai.orchestration.state_schemas import OSSSState, OSSSContext
from OSSS.ai.observability import get_logger

logger = get_logger(__name__)

# Import the new RAG function
from OSSS.ai.rag.additional_index_rag import rag_prefetch_additional

def _ensure_exec_state(state: Dict[str, Any]) -> Dict[str, Any]:
    exec_state = state.get("execution_state")
    if not isinstance(exec_state, dict):
        exec_state = {}
        state["execution_state"] = exec_state
    return exec_state


async def prefetch_rag_context(
    state: OSSSState,
    runtime: Runtime[OSSSContext],
) -> None:
    """
    Run vector search once per request and stash results into execution_state.

    This is where we bridge "RAG" -> FinalAgent-compatible fields:
      - execution_state["rag_context"] : big concatenated snippet
      - execution_state["rag_hits"]    : raw hits (optional)
      - execution_state["rag_meta"]    : metadata (optional)
    """
    exec_state = _ensure_exec_state(state)

    # 1) Check execution_config to see if RAG is enabled + top_k
    ec = exec_state.get("execution_config", {})
    if not isinstance(ec, dict):
        ec = {}
    use_rag = ec.get("use_rag", False)
    top_k = ec.get("top_k", 6)

    if not use_rag:
        logger.info("[rag_prefetch] RAG disabled for this request; skipping prefetch")
        return

    # 2) Decide what query to feed to RAG
    query = (
        runtime.context.query
        or state.get("query", "")
        or state.get("original_query", "")
        or ""
    ).strip()

    if not query:
        logger.info("[rag_prefetch] No query available for RAG; skipping prefetch")
        return

    logger.info(
        "[rag_prefetch] Running RAG search",
        extra={"query_preview": query[:120], "top_k": top_k},
    )

    # Use rag_prefetch_additional instead of get_retriever
    rag_context = await rag_prefetch_additional(query=query, index="main", top_k=top_k)

    if not rag_context:
        logger.info("[rag_prefetch] No RAG hits found")
        return

    # 3) Store the results in the execution state
    exec_state["rag_context"] = rag_context
    exec_state.setdefault("rag_meta", {})
    exec_state["rag_meta"].update(
        {
            "index": "main",
            "top_k_requested": top_k,
            "hits_returned": rag_context.count("\n\n") + 1,  # Count number of hits in the context
        }
    )

    logger.info(
        "[rag_prefetch] RAG context stored",
        extra={
            "rag_chars": len(rag_context),
            "hits_returned": rag_context.count("\n\n") + 1,
        },
    )
