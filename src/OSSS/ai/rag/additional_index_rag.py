# src/OSSS/ai/rag/additional_index_rag.py

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Tuple

import httpx
import numpy as np
from fastapi import HTTPException

from OSSS.ai.additional_index import top_k as index_top_k, IndexedChunk
from OSSS.ai.observability import get_logger

logger = get_logger(__name__)

EMBED_MODEL = os.getenv("OSSS_EMBED_MODEL", "nomic-embed-text")
DEFAULT_EMBED_BASE = "http://host.containers.internal:11434"
OLLAMA_BASE = os.getenv("OSSS_EMBED_BASE", DEFAULT_EMBED_BASE)
EMBED_URL = os.getenv("OSSS_EMBED_URL", f"{OLLAMA_BASE}/api/embeddings")


def _extract_embedding(ej: dict) -> List[float]:
    if isinstance(ej, dict) and "data" in ej:
        return ej["data"][0]["embedding"]
    if isinstance(ej, dict) and "embedding" in ej:
        return ej["embedding"]
    if isinstance(ej, dict) and "embeddings" in ej:
        return ej["embeddings"][0]
    raise ValueError(f"Unexpected embedding response schema: {ej}")


def _format_results(
    results: List[Tuple[float, IndexedChunk]],
    index: str,
) -> str:
    if not results:
        logger.info(
            "[additional_index_rag] No RAG results to format",
            extra={"index": index, "result_count": 0},
        )
        return ""

    lines: list[str] = []
    for i, (score, chunk) in enumerate(results, 1):
        header = (
            f"[{i}] index={index} "
            f"id={chunk.id} "
            f"score={score:.4f} "
            f"source={chunk.source or 'n/a'} "
            f"filename={chunk.filename or 'n/a'} "
            f"chunk_index={chunk.chunk_index}"
        )
        body = chunk.text or ""
        lines.append(f"{header}\n{body.strip()}")

    logger.debug(
        "[additional_index_rag] Formatted RAG results",
        extra={
            "index": index,
            "result_count": len(results),
            "first_score": float(results[0][0]) if results else None,
            "last_score": float(results[-1][0]) if results else None,
        },
    )

    return "\n\n".join(lines)


def _serialize_hits(
    results: List[Tuple[float, IndexedChunk]],
    index: str,
) -> List[Dict[str, Any]]:
    """
    Turn top-k (score, IndexedChunk) into a JSON-serializable list
    suitable for OSSSState.rag_hits.
    """
    hits: List[Dict[str, Any]] = []
    for score, chunk in results:
        hits.append(
            {
                "id": getattr(chunk, "id", None),
                "index": index,
                "score": float(score),
                "source": getattr(chunk, "source", None),
                "filename": getattr(chunk, "filename", None),
                "chunk_index": getattr(chunk, "chunk_index", None),
                "text": getattr(chunk, "text", None),
                # room for future fields (metadata, tags, etc.)
            }
        )
    return hits


async def rag_prefetch_additional(
    query: str,
    index: str = "main",
    top_k: int = 8,
) -> Dict[str, Any]:
    """
    Compute an embedding for `query`, search the in-memory additional index,
    and return BOTH a combined text block and a structured list of hits.

    Return schema (used by orchestrator._prefetch_rag):

    {
        "combined_text": str,     # prompt-ready context
        "hits": [ { ... }, ... ], # list of hit dicts
        "meta": { ... }           # optional metrics/diagnostics
    }
    """
    start_time = time.monotonic()
    query_preview = (query or "")[:120]

    logger.info(
        "[additional_index_rag] RAG prefetch start",
        extra={
            "index": index,
            "top_k": top_k,
            "embed_model": EMBED_MODEL,
            "embed_url": EMBED_URL,
            "query_preview": query_preview,
            "query_len": len(query or ""),
        },
    )

    # ---- 1. Embed the query ----
    embed_req = {"model": EMBED_MODEL, "prompt": query}

    try:
        embed_start = time.monotonic()
        async with httpx.AsyncClient(timeout=10.0) as client:
            er = await client.post(EMBED_URL, json=embed_req)
        embed_ms = (time.monotonic() - embed_start) * 1000

        logger.info(
            "[additional_index_rag] Embedding request completed",
            extra={
                "index": index,
                "status_code": er.status_code,
                "elapsed_ms": embed_ms,
            },
        )
    except httpx.RequestError as exc:
        logger.error(
            "[additional_index_rag] Failed to connect to embedding server",
            extra={
                "index": index,
                "embed_url": EMBED_URL,
                "exception": str(exc),
                "query_preview": query_preview,
            },
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Failed to connect to embedding server at {EMBED_URL}",
                "exc": str(exc),
            },
        )

    if er.status_code >= 400:
        logger.error(
            "[additional_index_rag] Embedding server returned error status",
            extra={
                "index": index,
                "status_code": er.status_code,
                "response_text_preview": er.text[:500] if er.text else "",
            },
        )
        raise HTTPException(
            status_code=er.status_code,
            detail={"error": "Embedding request failed", "body": er.text},
        )

    ej = er.json()
    try:
        vec = _extract_embedding(ej)
        logger.debug(
            "[additional_index_rag] Extracted embedding",
            extra={
                "index": index,
                "dim": len(vec) if isinstance(vec, list) else None,
                "response_schema_keys": list(ej.keys()) if isinstance(ej, dict) else None,
            },
        )
    except ValueError as e:
        logger.error(
            "[additional_index_rag] Failed to extract embedding from response",
            extra={
                "index": index,
                "error": str(e),
                "response_keys": list(ej.keys()) if isinstance(ej, dict) else None,
            },
        )
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "response": ej},
        )

    query_emb = np.array(vec, dtype="float32")

    # ---- 2. Vector search ----
    search_start = time.monotonic()
    results: List[Tuple[float, IndexedChunk]] = index_top_k(query_emb, k=top_k, index=index)
    search_ms = (time.monotonic() - search_start) * 1000

    logger.info(
        "[additional_index_rag] Vector search completed",
        extra={
            "index": index,
            "top_k_requested": top_k,
            "result_count": len(results),
            "elapsed_ms": search_ms,
        },
    )

    if results:
        logger.debug(
            "[additional_index_rag] Vector search result details",
            extra={
                "index": index,
                "top_score": float(results[0][0]),
                "min_score": float(results[-1][0]),
                "first_chunk_id": getattr(results[0][1], "id", None),
            },
        )
    else:
        logger.info(
            "[additional_index_rag] No results returned from index_top_k",
            extra={"index": index, "top_k": top_k},
        )

    # ---- 3. Format + serialize ----
    combined_text = _format_results(results, index=index)
    hits = _serialize_hits(results, index=index)

    total_ms = (time.monotonic() - start_time) * 1000
    logger.info(
        "[additional_index_rag] RAG prefetch completed",
        extra={
            "index": index,
            "top_k": top_k,
            "result_count": len(results),
            "context_chars": len(combined_text),
            "elapsed_ms": total_ms,
        },
    )

    return {
        "combined_text": combined_text,
        "hits": hits,
        "meta": {
            "index": index,
            "top_k_requested": top_k,
            "result_count": len(results),
            "context_chars": len(combined_text),
            "elapsed_ms": total_ms,
        },
    }


async def rag_prefetch_additional_index(
    query: str,
    index: str = "main",
    top_k: int = 8,
):
    logger.debug(
        "[additional_index_rag] rag_prefetch_additional_index alias invoked",
        extra={"index": index, "top_k": top_k},
    )
    return await rag_prefetch_additional(query=query, index=index, top_k=top_k)
