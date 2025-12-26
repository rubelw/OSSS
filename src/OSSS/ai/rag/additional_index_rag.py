# src/OSSS/ai/rag/additional_index_rag.py
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import httpx
import numpy as np
from fastapi import HTTPException

from OSSS.ai.additional_index import top_k as index_top_k, IndexedChunk
from OSSS.ai.observability import get_logger
from OSSS.ai.metrics import observe_prefetch  # 👈 metrics helper

logger = get_logger(__name__)

# ---- Embedding config ----
EMBED_MODEL = os.getenv("OSSS_EMBED_MODEL", "nomic-embed-text")
DEFAULT_EMBED_BASE = "http://host.containers.internal:11434"
OLLAMA_BASE = os.getenv("OSSS_EMBED_BASE", DEFAULT_EMBED_BASE)
EMBED_URL = os.getenv("OSSS_EMBED_URL", f"{OLLAMA_BASE}/api/embeddings")

# ---- Shared HTTP client for embeddings ----
_embed_client: httpx.AsyncClient | None = None


def get_embed_client() -> httpx.AsyncClient:
    """
    Lazily-initialized shared AsyncClient for embedding calls.
    Reused across requests to avoid per-request connection overhead.
    """
    global _embed_client
    if _embed_client is None:
        _embed_client = httpx.AsyncClient(timeout=10.0)
        logger.info(
            "[additional_index_rag] Created shared embedding AsyncClient",
            extra={"embed_url": EMBED_URL},
        )
    return _embed_client


@dataclass
class RagHit:
    score: float
    chunk: IndexedChunk


@dataclass
class RagResult:
    # NOTE: For pure retrieval (search_additional_index), combined_text
    # may be the empty string and filled later by formatters.
    combined_text: str
    hits: List[RagHit]
    meta: Dict[str, Any]


def _extract_embedding(ej: dict) -> List[float]:
    """
    Normalize various embedding response schemas into a 1D list[float].
    Supports:
      - { "data": [ { "embedding": [...] } ] }
      - { "embedding": [...] }
      - { "embeddings": [ [...], ... ] }
    """
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
    """
    Turn top-k results into a prompt-ready context string.
    Kept separate from retrieval so different agents can swap in their
    own formatting logic if needed.
    """
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


async def search_additional_index(
    query: str,
    index: str = "main",
    top_k: int = 6,
) -> RagResult:
    """
    Retrieval-only helper:

    - Compute an embedding for `query`
    - Search the in-memory additional index (main/tutor/agent)
    - Return RagResult with hits + meta, but *no* formatted combined_text.

    Callers that need a prompt-ready context string should format the
    hits themselves (e.g. via `_format_results`) or call
    `rag_prefetch_additional`, which wraps this and adds formatting.
    """
    start_time = time.monotonic()
    query_preview = (query or "")[:120]

    logger.info(
        "[additional_index_rag] RAG search start",
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
    embed_ms: float | None = None

    try:
        embed_start = time.monotonic()
        client = get_embed_client()
        er = await client.post(EMBED_URL, json=embed_req)
        embed_ms = (time.monotonic() - embed_start) * 1000.0

        logger.info(
            "[additional_index_rag] Embedding request completed",
            extra={
                "index": index,
                "status_code": er.status_code,
                "elapsed_ms": embed_ms,
            },
        )
    except httpx.RequestError as exc:
        # record error metrics
        total_ms = (time.monotonic() - start_time) * 1000.0
        observe_prefetch(
            index=index,
            outcome="error",
            hits=0,
            elapsed_ms_total=total_ms,
            elapsed_ms_embed=embed_ms,
            elapsed_ms_search=0.0,
            embed_model=EMBED_MODEL,
        )

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
        total_ms = (time.monotonic() - start_time) * 1000.0
        observe_prefetch(
            index=index,
            outcome="error",
            hits=0,
            elapsed_ms_total=total_ms,
            elapsed_ms_embed=embed_ms,
            elapsed_ms_search=0.0,
            embed_model=EMBED_MODEL,
        )

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
        total_ms = (time.monotonic() - start_time) * 1000.0
        observe_prefetch(
            index=index,
            outcome="error",
            hits=0,
            elapsed_ms_total=total_ms,
            elapsed_ms_embed=embed_ms,
            elapsed_ms_search=0.0,
            embed_model=EMBED_MODEL,
        )

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
    results: List[Tuple[float, IndexedChunk]] = index_top_k(
        query_emb,
        k=top_k,
        index=index,
    )
    search_ms = (time.monotonic() - search_start) * 1000.0

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

    # ---- 3. Build RagHit list (no formatting) ----
    hits: List[RagHit] = [
        RagHit(score=float(score), chunk=chunk) for score, chunk in results
    ]

    total_ms = (time.monotonic() - start_time) * 1000.0

    # ✅ success metrics
    observe_prefetch(
        index=index,
        outcome="success",
        hits=len(hits),
        elapsed_ms_total=total_ms,
        elapsed_ms_embed=embed_ms or 0.0,
        elapsed_ms_search=search_ms,
        embed_model=EMBED_MODEL,
    )

    meta: Dict[str, Any] = {
        "index": index,
        "top_k_requested": top_k,
        "result_count": len(results),
        "context_chars": 0,  # to be filled by formatters
        "elapsed_ms_total": total_ms,
        "elapsed_ms_search": search_ms,
        "elapsed_ms_embed": embed_ms,
        "embed_model": EMBED_MODEL,
        "embed_url": EMBED_URL,
    }

    # Retrieval-only: leave combined_text empty
    return RagResult(
        combined_text="",
        hits=hits,
        meta=meta,
    )


async def rag_prefetch_additional(
    query: str,
    index: str = "main",
    top_k: int = 6,
) -> RagResult:
    """
    High-level helper used by the orchestrator.

    NOTE:
    - Per-index defaults (top_k, snippet sizes, etc.) are resolved in the
      orchestrator (via RagIndexConfig / RAG_SETTINGS) *before* calling this.
    - This function assumes it is given the already-resolved `index` and `top_k`.
    """
    # 1. Retrieval (embedding + vector search + metrics)
    base_result = await search_additional_index(
        query=query,
        index=index,
        top_k=top_k,
    )

    # 2. Formatting: convert hits to (score, chunk) pairs
    index_name = str(base_result.meta.get("index", index))
    score_chunk_pairs: List[Tuple[float, IndexedChunk]] = [
        (hit.score, hit.chunk) for hit in base_result.hits
    ]
    combined_text = _format_results(score_chunk_pairs, index=index_name)

    # Enrich meta with context length, preserving existing metrics fields
    meta_with_ctx = dict(base_result.meta)
    meta_with_ctx["context_chars"] = len(combined_text or "")

    logger.info(
        "[additional_index_rag] RAG prefetch completed",
        extra={
            "index": index_name,
            "top_k": top_k,
            "result_count": len(base_result.hits),
            "context_chars": len(combined_text),
            "elapsed_ms": meta_with_ctx.get("elapsed_ms_total"),
        },
    )

    return RagResult(
        combined_text=combined_text,
        hits=base_result.hits,
        meta=meta_with_ctx,
    )


async def rag_prefetch_additional_index(
    query: str,
    index: str = "main",
    top_k: int = 8,
) -> RagResult:
    """
    Backwards-compatible alias with a slightly more descriptive name.
    """
    logger.debug(
        "[additional_index_rag] rag_prefetch_additional_index alias invoked",
        extra={"index": index, "top_k": top_k},
    )
    return await rag_prefetch_additional(query=query, index=index, top_k=top_k)
