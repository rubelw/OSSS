# src/OSSS/ai/rag/additional_index_rag.py
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx
import numpy as np
from fastapi import HTTPException

from OSSS.ai.additional_index import top_k as index_top_k, IndexedChunk, get_docs
from OSSS.ai.observability import get_logger
from OSSS.ai.metrics import observe_prefetch

logger = get_logger(__name__)

# ---- Embedding + retrieval tuning config ----
EMBED_MODEL = os.getenv("OSSS_EMBED_MODEL", "nomic-embed-text")
DEFAULT_EMBED_BASE = "http://host.containers.internal:11434"
OLLAMA_BASE = os.getenv("OSSS_EMBED_BASE", DEFAULT_EMBED_BASE)
EMBED_URL = os.getenv("OSSS_EMBED_URL", f"{OLLAMA_BASE}/api/embeddings")

MAX_TOP_K = int(os.getenv("OSSS_RAG_MAX_TOP_K", "8"))
SNIPPET_MAX_CHARS = int(os.getenv("OSSS_RAG_SNIPPET_MAX_CHARS", "2500"))

# ---- Optional web fallback config ----
WEB_FALLBACK_URL = os.getenv(
    "OSSS_WEB_FALLBACK_URL",
    "http://host.containers.internal:8081/api/ai/admin/web-fallback"
).strip()

WEB_FALLBACK_TIMEOUT_SECONDS = float(os.getenv("OSSS_WEB_FALLBACK_TIMEOUT_SECONDS", "8.0"))
WEB_FALLBACK_MIN_CONFIDENCE = float(os.getenv("OSSS_WEB_FALLBACK_MIN_CONFIDENCE", "0.7"))
FORCE_WEB_FALLBACK = os.getenv("OSSS_FORCE_WEB_FALLBACK", "0") == "1"

# helpful marker so logs prove the running code is this version
RAG_DEBUG_BUILD = "board-fallback-v6"

# ---- Shared HTTP clients ----
_embed_client: httpx.AsyncClient | None = None
_web_fallback_client: httpx.AsyncClient | None = None

# ---- Name-aware reranker helpers ----
NAME_QUERY_PATTERNS = [
    r"\bwho\s+is\b",
    r"\bwho\s+are\b",
    r"\blist\s+the\s+names\b",
    r"\bname(s)?\b",
    r"\bmember(s)?\b",
    r"\bboard\s+member(s)?\b",
    r"\broster\b",
    r"\btrustee(s)?\b",
    r"\bdirector(s)?\b",
    r"\bpresident\b",
    r"\bvice president\b",
    r"\bchair\b",
    r"\bboard\b",
]

PERSON_NAME_RE = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z]\.)?(?:\s+[A-Z][a-z'\-]+){1,3})\b"
)

ROLE_HINT_RE = re.compile(
    r"\b(board|member|director|president|vice president|secretary|treasurer|chair)\b",
    re.IGNORECASE,
)

ROLE_TITLE_QUERY_RE = re.compile(
    r"\b(who is|who's|name)\b.*\b(principal|superintendent|director|assistant principal|dean|counselor)\b",
    re.IGNORECASE,
)



NEGATIVE_DOC_HINT_RE = re.compile(
    r"\b(policy|standard|procedure|evaluation|responsibilities|framework)\b",
    re.IGNORECASE,
)

FILENAME_NAME_HINT_RE = re.compile(
    r"\b(minutes|transcript|agenda|regular meeting|board of directors|roster|attendance|roll call)\b",
    re.IGNORECASE,
)

# Stronger than filename hints: evidence that the chunk is actually about present members/directors
BOARD_MEMBER_LIST_RE = re.compile(
    r"\b(board of directors|board members?|trustees?)\b",
    re.IGNORECASE,
)

ATTENDANCE_LIST_RE = re.compile(
    r"\b(members present|directors present|roll call)\b",
    re.IGNORECASE,
)

def _extract_role_modifiers(query: str) -> List[str]:
    q = (query or "").lower()
    modifiers: List[str] = []

    if "high school" in q:
        modifiers.append("high school")
    if "middle school" in q:
        modifiers.append("middle school")
    if "elementary" in q:
        modifiers.append("elementary")
    if "preschool" in q:
        modifiers.append("preschool")
    if "assistant" in q:
        modifiers.append("assistant")

    return modifiers

def is_role_title_query(query: str) -> bool:
    return bool(ROLE_TITLE_QUERY_RE.search(query or ""))

def is_name_query(query: str) -> bool:
    q = (query or "").strip().lower()
    return any(re.search(p, q, re.IGNORECASE) for p in NAME_QUERY_PATTERNS)


def is_board_member_query(query: str) -> bool:
    q = query or ""
    return bool(
        re.search(r"\bschool board members?\b", q, re.IGNORECASE)
        or re.search(r"\bboard members?\b", q, re.IGNORECASE)
        or re.search(r"\bboard of directors\b", q, re.IGNORECASE)
    )


def get_embed_client() -> httpx.AsyncClient:
    global _embed_client
    if _embed_client is None:
        _embed_client = httpx.AsyncClient(timeout=10.0)
        logger.info(
            "[additional_index_rag] Created shared embedding AsyncClient",
            extra={"embed_url": EMBED_URL},
        )
    return _embed_client


def get_web_fallback_client() -> httpx.AsyncClient:
    global _web_fallback_client
    if _web_fallback_client is None:
        _web_fallback_client = httpx.AsyncClient(timeout=WEB_FALLBACK_TIMEOUT_SECONDS)
        logger.info(
            "[additional_index_rag] Created shared web fallback AsyncClient",
            extra={"web_fallback_url": WEB_FALLBACK_URL},
        )
    return _web_fallback_client


def get_cached_index(index: str = "main") -> List[IndexedChunk]:
    return get_docs(index=index)


@dataclass
class RagHit:
    score: float
    chunk: IndexedChunk


@dataclass
class RagResult:
    combined_text: str
    hits: List[RagHit]
    meta: Dict[str, Any]


def _extract_embedding(ej: dict) -> List[float]:
    if isinstance(ej, dict) and "data" in ej:
        return ej["data"][0]["embedding"]
    if isinstance(ej, dict) and "embedding" in ej:
        return ej["embedding"]
    if isinstance(ej, dict) and "embeddings" in ej:
        return ej["embeddings"][0]
    raise ValueError(f"Unexpected embedding response schema: {ej}")


def _normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip())


def _extract_candidate_names(text: str) -> List[str]:
    raw = PERSON_NAME_RE.findall(text or "")
    out: List[str] = []
    for n in raw:
        nn = _normalize_name(n)
        if len(nn.split()) < 2:
            continue
        lowered = nn.lower()
        if lowered in {
            "board workshop",
            "regular meeting",
            "student services",
            "school district",
            "board report",
            "march board",
            "administration center",
            "board room",
        }:
            continue
        out.append(nn)
    return out


def _score_name_features(
    *,
    query: str,
    score: float,
    chunk: IndexedChunk,
) -> Tuple[float, Dict[str, Any]]:
    text = (chunk.text or "").strip()
    source_blob = " ".join(
        [
            chunk.filename or "",
            chunk.source or "",
            getattr(chunk, "directory_context", "") or "",
        ]
    )

    detected_names = _extract_candidate_names(text)
    role_hint = bool(ROLE_HINT_RE.search(text)) or bool(ROLE_HINT_RE.search(source_blob))
    negative_doc_hint = bool(NEGATIVE_DOC_HINT_RE.search(source_blob)) or bool(
        NEGATIVE_DOC_HINT_RE.search(text[:250])
    )
    filename_name_hint = bool(FILENAME_NAME_HINT_RE.search(source_blob))
    board_member_list_hint = bool(BOARD_MEMBER_LIST_RE.search(text)) or bool(
        BOARD_MEMBER_LIST_RE.search(source_blob)
    )
    attendance_list_hint = bool(ATTENDANCE_LIST_RE.search(text)) or bool(
        ATTENDANCE_LIST_RE.search(source_blob)
    )

    bonus = 0.0

    if is_name_query(query) or is_role_title_query(query):
        # generic names in generic docs should not dominate
        if detected_names:
            if board_member_list_hint or attendance_list_hint or role_hint:
                bonus += min(0.12, 0.03 * len(detected_names))
            else:
                bonus += min(0.03, 0.005 * len(detected_names))

        if role_hint:
            bonus += 0.04

        if filename_name_hint:
            bonus += 0.04

        if board_member_list_hint:
            bonus += 0.10

        if attendance_list_hint:
            bonus += 0.12

        if negative_doc_hint:
            bonus -= 0.06

    final_score = float(score) + bonus

    return final_score, {
        "original_score": float(score),
        "bonus": bonus,
        "final_score": final_score,
        "detected_names": detected_names[:10],
        "role_hint": role_hint,
        "filename_name_hint": filename_name_hint,
        "negative_doc_hint": negative_doc_hint,
        "board_member_list_hint": board_member_list_hint,
        "attendance_list_hint": attendance_list_hint,
    }


def rerank_name_query(
    query: str,
    results: List[Tuple[float, IndexedChunk]],
) -> Tuple[List[Tuple[float, IndexedChunk]], Dict[str, Any]]:
    name_query = is_name_query(query)
    board_query = is_board_member_query(query)
    role_title_query = is_role_title_query(query)

    logger.warning(
        "[additional_index_rag] reranker build marker",
        extra={"build": RAG_DEBUG_BUILD, "query_preview": (query or "")[:120]},
    )

    if not results or not (name_query or role_title_query):
        return results, {
            "applied": False,
            "build": RAG_DEBUG_BUILD,
            "is_name_query": name_query,
            "is_board_member_query": board_query,
            "is_role_title_query": role_title_query,
            "name_hits": 0,
            "distinct_name_count": 0,
            "filename_hint_hits": 0,
            "board_member_list_hits": 0,
            "attendance_list_hits": 0,
            "weak_name_signal": False,
            "needs_roster_source": False,
            "suggest_web_fallback": False,
            "forced_board_member_fallback": False,
            "forced_role_title_fallback": False,
        }

    reranked: List[Tuple[float, IndexedChunk, Dict[str, Any]]] = []
    name_hits = 0
    distinct_names: set[str] = set()
    filename_hint_hits = 0
    board_member_list_hits = 0
    attendance_list_hits = 0

    for score, chunk in results:
        final_score, debug = _score_name_features(query=query, score=score, chunk=chunk)

        detected_names = debug.get("detected_names", [])
        if detected_names:
            name_hits += 1
            distinct_names.update(detected_names)

        if debug.get("filename_name_hint"):
            filename_hint_hits += 1
        if debug.get("board_member_list_hint"):
            board_member_list_hits += 1
        if debug.get("attendance_list_hint"):
            attendance_list_hits += 1

        reranked.append((final_score, chunk, debug))

    reranked.sort(key=lambda x: x[0], reverse=True)
    out_results = [(score, chunk) for score, chunk, _ in reranked]

    distinct_name_count = len(distinct_names)
    top_debug = [
        {
            "chunk_id": getattr(chunk, "id", None),
            "filename": getattr(chunk, "filename", None),
            **debug,
        }
        for _, chunk, debug in reranked[:5]
    ]

    # Force fallback for board-member queries
    if board_query:
        return out_results, {
            "applied": True,
            "build": RAG_DEBUG_BUILD,
            "is_name_query": True,
            "is_board_member_query": True,
            "is_role_title_query": role_title_query,
            "name_hits": name_hits,
            "distinct_name_count": distinct_name_count,
            "filename_hint_hits": filename_hint_hits,
            "board_member_list_hits": board_member_list_hits,
            "attendance_list_hits": attendance_list_hits,
            "weak_name_signal": True,
            "needs_roster_source": True,
            "suggest_web_fallback": True,
            "forced_board_member_fallback": True,
            "forced_role_title_fallback": False,
            "top_debug": top_debug,
            "distinct_names_preview": sorted(distinct_names)[:10],
        }

    # Force fallback for role-title queries unless the top hit clearly ties
    # a person name to the requested role in the chunk text itself.
    # Force fallback for role-title queries unless the top hit clearly ties
    # a person name to the requested role AND requested school-level modifier.
    if role_title_query:
        role_terms = re.findall(
            r"(assistant principal|principal|superintendent|director|dean|counselor)",
            query,
            re.IGNORECASE,
        )
        role_terms = [t.lower() for t in role_terms]

        role_modifiers = _extract_role_modifiers(query)

        has_clear_local_role_answer = False
        matching_role_hits = 0
        matching_role_modifier_hits = 0

        for _, chunk, debug in reranked[:3]:
            text_blob = f"{chunk.filename or ''}\n{chunk.source or ''}\n{chunk.text or ''}".lower()
            detected_names = debug.get("detected_names", [])

            if not detected_names:
                continue

            role_match = any(role in text_blob for role in role_terms)
            modifier_match = True

            # If the query includes a school-level modifier, require it too
            if role_modifiers:
                modifier_match = any(mod in text_blob for mod in role_modifiers)

            if role_match:
                matching_role_hits += 1
            if role_match and modifier_match:
                matching_role_modifier_hits += 1
                has_clear_local_role_answer = True

        weak_name_signal = not has_clear_local_role_answer
        needs_roster_source = not has_clear_local_role_answer
        suggest_web_fallback = not has_clear_local_role_answer

        return out_results, {
            "applied": True,
            "build": "board-fallback-v6",
            "is_name_query": name_query,
            "is_board_member_query": False,
            "is_role_title_query": True,
            "name_hits": name_hits,
            "distinct_name_count": distinct_name_count,
            "filename_hint_hits": filename_hint_hits,
            "board_member_list_hits": board_member_list_hits,
            "attendance_list_hits": attendance_list_hits,
            "weak_name_signal": weak_name_signal,
            "needs_roster_source": needs_roster_source,
            "suggest_web_fallback": suggest_web_fallback,
            "forced_board_member_fallback": False,
            "forced_role_title_fallback": suggest_web_fallback,
            "matching_role_hits": matching_role_hits,
            "matching_role_modifier_hits": matching_role_modifier_hits,
            "role_modifiers": role_modifiers,
            "top_debug": top_debug,
            "distinct_names_preview": sorted(distinct_names)[:10],
        }

    has_true_roster_answer = (
        distinct_name_count >= 3
        and (board_member_list_hits >= 1 or attendance_list_hits >= 1)
    )

    weak_name_signal = not has_true_roster_answer
    needs_roster_source = (board_member_list_hits == 0 and attendance_list_hits == 0)
    suggest_web_fallback = weak_name_signal or needs_roster_source

    return out_results, {
        "applied": True,
        "build": RAG_DEBUG_BUILD,
        "is_name_query": name_query,
        "is_board_member_query": False,
        "is_role_title_query": False,
        "name_hits": name_hits,
        "distinct_name_count": distinct_name_count,
        "filename_hint_hits": filename_hint_hits,
        "board_member_list_hits": board_member_list_hits,
        "attendance_list_hits": attendance_list_hits,
        "weak_name_signal": weak_name_signal,
        "needs_roster_source": needs_roster_source,
        "suggest_web_fallback": suggest_web_fallback,
        "forced_board_member_fallback": False,
        "forced_role_title_fallback": False,
        "top_debug": top_debug,
        "distinct_names_preview": sorted(distinct_names)[:10],
    }

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
        body = (chunk.text or "").strip()
        lines.append(f"{header}\n{body}")

    combined = "\n\n".join(lines)

    if SNIPPET_MAX_CHARS and len(combined) > SNIPPET_MAX_CHARS:
        logger.info(
            "[additional_index_rag] Truncating RAG combined_text",
            extra={
                "index": index,
                "original_chars": len(combined),
                "truncated_chars": SNIPPET_MAX_CHARS,
            },
        )
        combined = combined[:SNIPPET_MAX_CHARS]

    logger.debug(
        "[additional_index_rag] Formatted RAG results",
        extra={
            "index": index,
            "result_count": len(results),
            "first_score": float(results[0][0]) if results else None,
            "last_score": float(results[-1][0]) if results else None,
        },
    )

    return combined


async def _maybe_web_fallback(query: str, index: str, rag_meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    logger.warning(
        "[additional_index_rag] web fallback decision check",
        extra={
            "build": RAG_DEBUG_BUILD,
            "index": index,
            "web_fallback_url": WEB_FALLBACK_URL,
            "is_name_query": rag_meta.get("is_name_query", False),
            "is_board_member_query": rag_meta.get("is_board_member_query", False),
            "suggest_web_fallback": rag_meta.get("suggest_web_fallback", False),
            "needs_roster_source": rag_meta.get("needs_roster_source", False),
            "distinct_name_count": rag_meta.get("distinct_name_count", 0),
            "board_member_list_hits": rag_meta.get("board_member_list_hits", 0),
            "attendance_list_hits": rag_meta.get("attendance_list_hits", 0),
            "force_web_fallback": FORCE_WEB_FALLBACK,
        },
    )

    if not WEB_FALLBACK_URL:
        logger.warning("[additional_index_rag] web fallback skipped: OSSS_WEB_FALLBACK_URL is empty")
        return None

    should_fallback = FORCE_WEB_FALLBACK or (
        (
                rag_meta.get("is_name_query", False)
                or rag_meta.get("is_role_title_query", False)
        )
        and (
                rag_meta.get("suggest_web_fallback", False)
                or rag_meta.get("needs_roster_source", False)
        )
    )

    if not should_fallback:
        logger.warning(
            "[additional_index_rag] web fallback skipped: trigger conditions not met",
            extra={
                "index": index,
                "is_name_query": rag_meta.get("is_name_query", False),
                "suggest_web_fallback": rag_meta.get("suggest_web_fallback", False),
                "needs_roster_source": rag_meta.get("needs_roster_source", False),
            },
        )
        return None

    payload = {
        "query": query,
        "index": index,
        "reason": {
            "build": RAG_DEBUG_BUILD,
            "is_name_query": rag_meta.get("is_name_query", False),
            "is_board_member_query": rag_meta.get("is_board_member_query", False),
            "weak_name_signal": rag_meta.get("weak_name_signal", False),
            "needs_roster_source": rag_meta.get("needs_roster_source", False),
            "distinct_name_count": rag_meta.get("distinct_name_count", 0),
            "board_member_list_hits": rag_meta.get("board_member_list_hits", 0),
            "attendance_list_hits": rag_meta.get("attendance_list_hits", 0),
            "rerank_debug": rag_meta.get("rerank_debug", []),
        },
    }

    try:
        logger.warning(
            "[additional_index_rag] calling web fallback",
            extra={"index": index, "url": WEB_FALLBACK_URL, "query_preview": query[:120]},
        )

        client = get_web_fallback_client()
        resp = await client.post(WEB_FALLBACK_URL, json=payload)

        logger.warning(
            "[additional_index_rag] web fallback response received",
            extra={"index": index, "status_code": resp.status_code},
        )

        resp.raise_for_status()
        data = resp.json()

        logger.warning(
            "[additional_index_rag] web fallback payload parsed",
            extra={
                "index": index,
                "confidence": float(data.get("confidence", 0.0)),
                "has_answer": bool((data.get("answer") or "").strip()),
                "source_count": len(data.get("sources", []) or []),
                "name_count": len(data.get("extracted_names", []) or []),
            },
        )

        confidence = float(data.get("confidence", 0.0))
        if confidence < WEB_FALLBACK_MIN_CONFIDENCE:
            logger.info(
                "[additional_index_rag] Web fallback returned below confidence threshold",
                extra={
                    "index": index,
                    "confidence": confidence,
                    "threshold": WEB_FALLBACK_MIN_CONFIDENCE,
                },
            )
            return None

        logger.info(
            "[additional_index_rag] Web fallback accepted",
            extra={
                "index": index,
                "confidence": confidence,
                "source_count": len(data.get("sources", []) or []),
            },
        )
        return data

    except Exception as exc:
        logger.warning(
            "[additional_index_rag] Web fallback failed",
            extra={
                "index": index,
                "web_fallback_url": WEB_FALLBACK_URL,
                "exception": str(exc),
            },
        )
        return None


async def search_additional_index(
    query: str,
    index: str = "main",
    top_k: int = 6,
) -> RagResult:
    start_time = time.monotonic()
    query_preview = (query or "")[:120]

    effective_top_k = max(1, min(MAX_TOP_K, top_k or MAX_TOP_K))

    logger.info(
        "[additional_index_rag] RAG search start",
        extra={
            "index": index,
            "top_k": effective_top_k,
            "embed_model": EMBED_MODEL,
            "embed_url": EMBED_URL,
            "query_preview": query_preview,
            "query_len": len(query or ""),
        },
    )

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
            detail={"error": f"Failed to connect to embedding server at {EMBED_URL}", "exc": str(exc)},
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

    search_start = time.monotonic()
    results: List[Tuple[float, IndexedChunk]] = index_top_k(
        query_emb,
        k=effective_top_k,
        index=index,
    )
    search_ms = (time.monotonic() - search_start) * 1000.0

    logger.info(
        "[additional_index_rag] Vector search completed",
        extra={
            "index": index,
            "top_k_requested": top_k,
            "top_k_effective": effective_top_k,
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
            extra={"index": index, "top_k_effective": effective_top_k},
        )

    results, rerank_meta = rerank_name_query(query, results)

    if rerank_meta.get("applied"):
        logger.info(
            "[additional_index_rag] Name-aware reranker applied",
            extra={
                "index": index,
                "build": rerank_meta.get("build"),
                "name_hits": rerank_meta.get("name_hits"),
                "distinct_name_count": rerank_meta.get("distinct_name_count"),
                "filename_hint_hits": rerank_meta.get("filename_hint_hits"),
                "board_member_list_hits": rerank_meta.get("board_member_list_hits"),
                "attendance_list_hits": rerank_meta.get("attendance_list_hits"),
                "weak_name_signal": rerank_meta.get("weak_name_signal"),
                "needs_roster_source": rerank_meta.get("needs_roster_source"),
                "suggest_web_fallback": rerank_meta.get("suggest_web_fallback"),
                "is_board_member_query": rerank_meta.get("is_board_member_query"),
                "is_role_title_query": rerank_meta.get("is_role_title_query"),
                "forced_role_title_fallback": rerank_meta.get("forced_role_title_fallback", False),
                "matching_role_hits": rerank_meta.get("matching_role_hits", 0),
            },
        )

    hits: List[RagHit] = [RagHit(score=float(score), chunk=chunk) for score, chunk in results]

    total_ms = (time.monotonic() - start_time) * 1000.0

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
        "top_k_effective": effective_top_k,
        "result_count": len(results),
        "context_chars": 0,
        "elapsed_ms_total": total_ms,
        "elapsed_ms_search": search_ms,
        "elapsed_ms_embed": embed_ms,
        "embed_model": EMBED_MODEL,
        "embed_url": EMBED_URL,
        "reranker_applied": rerank_meta.get("applied", False),
        "build": rerank_meta.get("build", RAG_DEBUG_BUILD),
        "is_name_query": rerank_meta.get("is_name_query", False),
        "is_board_member_query": rerank_meta.get("is_board_member_query", False),
        "is_role_title_query": rerank_meta.get("is_role_title_query", False),
        "name_hits": rerank_meta.get("name_hits", 0),
        "distinct_name_count": rerank_meta.get("distinct_name_count", 0),
        "filename_hint_hits": rerank_meta.get("filename_hint_hits", 0),
        "board_member_list_hits": rerank_meta.get("board_member_list_hits", 0),
        "attendance_list_hits": rerank_meta.get("attendance_list_hits", 0),
        "weak_name_signal": rerank_meta.get("weak_name_signal", False),
        "needs_roster_source": rerank_meta.get("needs_roster_source", False),
        "suggest_web_fallback": rerank_meta.get("suggest_web_fallback", False),
        "forced_board_member_fallback": rerank_meta.get("forced_board_member_fallback", False),
        "forced_role_title_fallback": rerank_meta.get("forced_role_title_fallback", False),
        "matching_role_hits": rerank_meta.get("matching_role_hits", 0),
        "distinct_names_preview": rerank_meta.get("distinct_names_preview", []),
        "rerank_debug": rerank_meta.get("top_debug", []),
    }

    return RagResult(combined_text="", hits=hits, meta=meta)


async def rag_prefetch_additional(
    query: str,
    index: str = "main",
    top_k: int = 6,
) -> RagResult:
    base_result = await search_additional_index(query=query, index=index, top_k=top_k)

    index_name = str(base_result.meta.get("index", index))
    score_chunk_pairs: List[Tuple[float, IndexedChunk]] = [
        (hit.score, hit.chunk) for hit in base_result.hits
    ]
    combined_text = _format_results(score_chunk_pairs, index=index_name)

    meta_with_ctx = dict(base_result.meta)
    meta_with_ctx["context_chars"] = len(combined_text or "")

    web_fallback = await _maybe_web_fallback(query=query, index=index_name, rag_meta=meta_with_ctx)
    if web_fallback:
        answer_text = (web_fallback.get("answer") or "").strip()
        if answer_text:
            meta_with_ctx["rag_combined_text"] = combined_text
            combined_text = answer_text
            meta_with_ctx["used_web_fallback"] = True
            meta_with_ctx["web_fallback_confidence"] = web_fallback.get("confidence")
            meta_with_ctx["web_fallback_sources"] = web_fallback.get("sources", [])
            meta_with_ctx["web_fallback_names"] = web_fallback.get("extracted_names", [])
            meta_with_ctx["context_chars"] = len(combined_text)
    else:
        meta_with_ctx["used_web_fallback"] = False

    logger.info(
        "[additional_index_rag] RAG prefetch completed",
        extra={
            "index": index_name,
            "top_k": meta_with_ctx.get("top_k_effective", top_k),
            "result_count": len(base_result.hits),
            "context_chars": len(combined_text),
            "elapsed_ms": meta_with_ctx.get("elapsed_ms_total"),
            "suggest_web_fallback": meta_with_ctx.get("suggest_web_fallback", False),
            "needs_roster_source": meta_with_ctx.get("needs_roster_source", False),
            "used_web_fallback": meta_with_ctx.get("used_web_fallback", False),
            "build": meta_with_ctx.get("build", RAG_DEBUG_BUILD),
            "board_member_list_hits": meta_with_ctx.get("board_member_list_hits", 0),
            "attendance_list_hits": meta_with_ctx.get("attendance_list_hits", 0),
        },
    )

    return RagResult(combined_text=combined_text, hits=base_result.hits, meta=meta_with_ctx)


async def rag_prefetch_additional_index(
    query: str,
    index: str = "main",
    top_k: int = 8,
) -> RagResult:
    logger.debug(
        "[additional_index_rag] rag_prefetch_additional_index alias invoked",
        extra={"index": index, "top_k": top_k},
    )
    return await rag_prefetch_additional(query=query, index=index, top_k=top_k)