# ai_gateway.py

from __future__ import annotations

import json
import os
import math
import re
from pathlib import Path
from typing import Any, Optional, List, Literal, Dict

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Request,
)
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.exceptions import HTTPException as StarletteHTTPException

# If you have a real redactor, import it here
def redact_pii(text: str) -> str:
    return text

# ---------- Auth (safe fallback) ----------
async def require_auth() -> Optional[dict]:
    return None

# ---------- Settings (safe fallback) ----------
try:
    from OSSS.config import settings  # type: ignore
except Exception:
    class _Settings:
        PROMETHEUS_ENABLED: bool = os.getenv("PROMETHEUS_ENABLED", "1") not in ("0", "false", "False")
        VLLM_ENDPOINT: str = os.getenv("VLLM_ENDPOINT", "http://host.containers.internal:11434")
        TUTOR_TEMPERATURE: float = float(os.getenv("TUTOR_TEMPERATURE", "0.2"))
        TUTOR_MAX_TOKENS: int = int(os.getenv("TUTOR_MAX_TOKENS", "2048"))
        DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "llama3.1")

        # RAG toggles (safe defaults)
        RAG_ENABLED: bool = os.getenv("RAG_ENABLED", "1") not in ("0", "false", "False")
        RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "6"))
        RAG_MIN_SCORE: float = float(os.getenv("RAG_MIN_SCORE", "0.0"))

        # Optional: allow override of embeddings path
        EMBEDDINGS_PATH: str = os.getenv("EMBEDDINGS_PATH", "/workspace/vector_indexes/main/embeddings.jsonl")

    settings = _Settings()  # type: ignore

# ---------- Metrics (optional) ----------
try:
    from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
except Exception:
    class _DummyCounter:
        def __init__(self, *a, **kw): pass
        def labels(self, *a, **kw): return self
        def inc(self, *a, **kw): return None
    def generate_latest() -> bytes: return b"# metrics disabled\n"
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4"
    Counter = _DummyCounter  # type: ignore

REQS = Counter("gateway_requests_total", "HTTP requests", ["path"])
TOKENS_IN = Counter("gateway_tokens_in_total", "Prompt tokens in")
TOKENS_OUT = Counter("gateway_tokens_out_total", "Completion tokens out")

# ---------- HTTP client ----------
import httpx
from pydantic import BaseModel, Field

# ---------- Router ----------
router = APIRouter()

# ---------- Exception helpers ----------
def _to_str(x: Any) -> str:
    if isinstance(x, (bytes, bytearray)):
        try:
            return x.decode("utf-8")
        except Exception:
            return x.decode("utf-8", "replace")
    return str(x)

async def _http_exc_to_json(request: Request, exc: StarletteHTTPException):
    detail: Any = exc.detail
    try:
        json.dumps(detail)
    except Exception:
        detail = _to_str(detail)
    return JSONResponse({"detail": detail}, status_code=exc.status_code, headers=exc.headers)

async def _unexpected_exc(request: Request, exc: Exception):
    return JSONResponse({"detail": _to_str(exc)}, status_code=500)

try:
    router.add_exception_handler(StarletteHTTPException, _http_exc_to_json)  # type: ignore[attr-defined]
    router.add_exception_handler(Exception, _unexpected_exc)  # type: ignore[attr-defined]
except Exception:
    pass

# ---------- RAG helpers ----------
class RetrievedChunk(BaseModel):
    """
    A normalized retrieval result.
    """
    id: str
    text: str
    source: str
    score: float = 0.0
    meta: Optional[Dict[str, Any]] = None


# ---------- RAG vector utilities ----------
# Prefer settings.EMBEDDINGS_PATH if present, else default to the known location.
_EMBEDDINGS_PATH_STR = getattr(settings, "EMBEDDINGS_PATH", "/workspace/vector_indexes/main/embeddings.jsonl")
EMBEDDINGS_PATH = Path(_EMBEDDINGS_PATH_STR)

# Cache rows (dicts) loaded from embeddings.jsonl
_VECTOR_CACHE: list[dict] | None = None


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _load_embeddings_once() -> list[dict]:
    """
    Load embeddings.jsonl into memory once per process.
    Expected rows are JSON objects (one per line).
    """
    global _VECTOR_CACHE
    if _VECTOR_CACHE is not None:
        return _VECTOR_CACHE

    rows: list[dict] = []
    if not EMBEDDINGS_PATH.exists():
        print(f"[rag] embeddings file not found: {EMBEDDINGS_PATH}")
        _VECTOR_CACHE = []
        return _VECTOR_CACHE

    with EMBEDDINGS_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    rows.append(obj)
            except Exception:
                continue

    _VECTOR_CACHE = rows
    print(f"[rag] loaded {len(rows)} embeddings from disk: {EMBEDDINGS_PATH}")
    return rows


def _extract_text(row: dict) -> str:
    """
    Best-effort extraction of chunk text from various embedding row schemas.
    """
    for key in ("text", "chunk", "content", "document", "page_content"):
        v = row.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _extract_source(row: dict) -> str:
    """
    Best-effort source field.
    """
    for key in ("source", "path", "uri", "url", "file", "doc_id"):
        v = row.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return "embeddings.jsonl"


def _extract_id(row: dict, fallback_idx: int) -> str:
    for key in ("id", "chunk_id", "doc_chunk_id", "uuid"):
        v = row.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, (int, float)):
            return str(v)
    return f"row:{fallback_idx}"


def _extract_embedding(row: dict) -> Optional[list[float]]:
    """
    Best-effort extraction of embedding vector from common schemas.
    """
    for key in ("embedding", "vector", "values", "embeddings"):
        v = row.get(key)
        if isinstance(v, list) and v and all(isinstance(x, (int, float)) for x in v):
            return [float(x) for x in v]
    return None


# -----------------------
# Fix #2 + Fix #3 helpers
# -----------------------
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by",
    "for", "from", "has", "have", "he", "her", "his", "i",
    "in", "into", "is", "it", "its", "me", "my", "of",
    "on", "or", "our", "she", "that", "the", "their", "them",
    "there", "these", "they", "this", "to", "was", "we",
    "were", "what", "when", "where", "which", "who", "why",
    "with", "you", "your", "yours",
}

def _tokenize(s: str) -> list[str]:
    # keep alnum tokens; lowercased
    return re.findall(r"[a-z0-9]+", (s or "").lower())

def _normalize_query_terms(q: str) -> list[str]:
    toks = [t for t in _tokenize(q) if t and t not in _STOPWORDS]
    # basic light normalization: singularize very common plural forms
    norm: list[str] = []
    for t in toks:
        if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            norm.append(t[:-1])
        norm.append(t)
    # unique while preserving order
    seen = set()
    out: list[str] = []
    for t in norm:
        if t not in seen:
            out.append(t)
            seen.add(t)
    return out

def _keyword_overlap_score(q_terms: list[str], text: str) -> float:
    """
    Fix #2: word-overlap scoring instead of strict substring match.
    Returns a score in roughly [0, 1.5] (we clamp later).
    """
    if not q_terms or not text:
        return 0.0

    t_lower = text.lower()
    t_terms = set(_normalize_query_terms(t_lower))

    overlap = sum(1 for t in q_terms if t in t_terms)
    if overlap <= 0:
        return 0.0

    # Base: fraction of query terms matched
    base = overlap / max(1, len(q_terms))

    # Bonus: exact substring of the raw query (helps for names/phrases)
    # (small bonus so overlap still matters most)
    phrase_bonus = 0.15 if " ".join(q_terms) in t_lower else 0.0

    # Bonus: consecutive bigram hits (helps “dcg teacher”)
    bigram_bonus = 0.0
    if len(q_terms) >= 2:
        for i in range(len(q_terms) - 1):
            bg = f"{q_terms[i]} {q_terms[i+1]}"
            if bg in t_lower:
                bigram_bonus += 0.05

    return base + phrase_bonus + bigram_bonus

def _apply_simple_domain_boosts(q_terms: list[str], row: dict, text: str, score: float) -> float:
    """
    Fix #3: lightweight boosts so “teachers” queries prefer teacher-like chunks and
    DCG queries prefer DCG-like chunks, without needing query embeddings.
    """
    if score <= 0.0:
        return score

    t_lower = (text or "").lower()
    src_lower = _extract_source(row).lower()

    # Teacher intent boost
    teacher_terms = {"teacher", "teachers", "staff", "faculty", "instructor", "educator"}
    if any(t in teacher_terms for t in q_terms):
        if any(x in t_lower for x in ("teacher", "staff", "faculty", "instructor", "educator")):
            score += 0.20
        if any(x in src_lower for x in ("teacher", "staff", "faculty")):
            score += 0.10

    # DCG boost (your district keyword)
    if "dcg" in q_terms:
        if "dcg" in t_lower:
            score += 0.15
        if "dcg" in src_lower:
            score += 0.10

    # Slight preference for structured sources over generic if meta indicates type
    meta = row.get("meta")
    if isinstance(meta, dict):
        doc_type = str(meta.get("type") or meta.get("doc_type") or "").lower()
        if doc_type in ("teacher", "teachers"):
            score += 0.10

    return score
# -----------------------


async def rag_retrieve(
    query: str,
    *,
    top_k: int,
    min_score: float,
    filters: Optional[Dict[str, Any]] = None,
) -> List[RetrievedChunk]:
    """
    Best-effort local vector retrieval over embeddings.jsonl.

    For now, we:
      - use cosine similarity if filters["query_embedding"] is provided and row has embeddings
      - else do keyword retrieval

    Fix #1 (already present):
      - If we're in keyword-fallback mode, do NOT return 0.0-score chunks.

    Fix #2:
      - Replace strict substring scoring with word-overlap scoring (plus small phrase/bigram bonuses).

    Fix #3:
      - Add lightweight domain boosts (e.g., “teachers” queries prefer teacher-like chunks).
    """
    rows = _load_embeddings_once()
    if not rows:
        return []

    # Optional: user can pass query embedding in rag_filters, e.g.
    #   "rag_filters": {"query_embedding": [ ... floats ... ]}
    query_vec: Optional[list[float]] = None
    if isinstance(filters, dict):
        qv = filters.get("query_embedding")
        if isinstance(qv, list) and qv and all(isinstance(x, (int, float)) for x in qv):
            query_vec = [float(x) for x in qv]

    q = (query or "").strip()
    if not q:
        return []

    scored: list[tuple[float, dict, int]] = []

    # --- keyword term prep for Fix #2/#3 ---
    q_terms = _normalize_query_terms(q)

    # --- Fix #1: in keyword-only mode, never allow 0.0 results through ---
    effective_min_score = float(min_score)
    keyword_only_mode = query_vec is None
    if keyword_only_mode and effective_min_score <= 0.0:
        effective_min_score = 1e-9  # require strictly > 0.0 to pass
    # -------------------------------------------------------------------

    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            continue

        text = _extract_text(row)
        if not text:
            continue

        score = 0.0

        # Vector mode if possible
        if query_vec is not None:
            emb = _extract_embedding(row)
            if emb is not None and len(emb) == len(query_vec):
                score = _cosine_similarity(query_vec, emb)
            else:
                # No usable embedding; use keyword overlap instead (Fix #2)
                score = _keyword_overlap_score(q_terms, text)
                score = _apply_simple_domain_boosts(q_terms, row, text, score)
        else:
            # Keyword mode (Fix #2 + Fix #3)
            score = _keyword_overlap_score(q_terms, text)
            score = _apply_simple_domain_boosts(q_terms, row, text, score)

        # Clamp to a sane range so min_score remains meaningful
        if score < 0.0:
            score = 0.0
        if score > 1.5:
            score = 1.5

        if score >= effective_min_score:
            scored.append((score, row, idx))

    if not scored:
        return []

    scored.sort(key=lambda t: t[0], reverse=True)
    top = scored[: max(1, int(top_k))]

    out: list[RetrievedChunk] = []
    for score, row, idx in top:
        out.append(
            RetrievedChunk(
                id=_extract_id(row, idx),
                text=_extract_text(row),
                source=_extract_source(row),
                score=float(score),
                meta=row.get("meta") if isinstance(row.get("meta"), dict) else None,
            )
        )
    return out


def _extract_last_user_query(messages: List[Dict[str, str]]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            return (m.get("content") or "").strip()
    return ""


def _inject_rag_context_messages(
    *,
    messages: List[Dict[str, str]],
    chunks: List[RetrievedChunk],
) -> List[Dict[str, str]]:
    if not chunks:
        return messages

    context_blocks: List[str] = []
    for i, c in enumerate(chunks, start=1):
        context_blocks.append(
            f"[{i}] source={c.source} score={c.score:.3f} id={c.id}\n{c.text}"
        )

    context_msg = {
        "role": "system",
        "content": (
            "CONTEXT:\n\n"
            + "\n\n---\n\n".join(context_blocks)
            + "\n\n"
            "Instructions:\n"
            "- Use the CONTEXT above when it is relevant.\n"
            "- If the context is insufficient, say so.\n"
            "- When you use a fact from context, cite it like [1], [2], etc.\n"
        ),
    }

    out: List[Dict[str, str]] = []
    last_system_idx = -1
    for idx, m in enumerate(messages):
        out.append(m)
        if m.get("role") == "system":
            last_system_idx = idx

    if last_system_idx >= 0:
        out.insert(last_system_idx + 1, context_msg)
        return out

    return [context_msg, *messages]


# ---------- Models ----------
class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"] = Field(
        description="The role of the message sender (system, user, or assistant).",
        examples=["system", "user", "assistant"],
    )
    content: str = Field(
        description="The text content of the message.",
        examples=["You are a helpful assistant.", "How do I cook pasta al dente?"],
    )


class ChatRequest(BaseModel):
    model: Optional[str] = Field(default="llama3.1", description="Model name (e.g., llama3.1)")
    messages: List[ChatMessage]
    temperature: Optional[float] = Field(default=None, ge=0, le=2)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    stream: Optional[bool] = False

    # ---- RAG controls (optional, backward compatible) ----
    use_rag: Optional[bool] = Field(default=None, description="Enable retrieval-augmented generation.")
    top_k: Optional[int] = Field(default=None, ge=1, le=50, description="How many chunks to retrieve.")
    min_score: Optional[float] = Field(default=None, description="Drop retrieved chunks below this score.")
    rag_filters: Optional[Dict[str, Any]] = Field(default=None, description="Optional retrieval filters.")


# ---------- Endpoints ----------
@router.get("/metrics")
async def metrics():
    if not getattr(settings, "PROMETHEUS_ENABLED", False):
        raise HTTPException(status_code=404, detail="metrics disabled")
    data = generate_latest()
    return PlainTextResponse(data.decode("utf-8"), media_type=CONTENT_TYPE_LATEST)


@router.get("/v1/models")
async def list_models(_: dict | None = Depends(require_auth)):
    REQS.labels("/v1/models").inc()
    base = getattr(settings, "VLLM_ENDPOINT", "http://host.containers.internal:11434").rstrip("/")
    upstream_v1 = f"{base}/v1/models"
    upstream_tags = f"{base}/api/tags"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.get(upstream_v1)
            if r.status_code == 404:
                t = await client.get(upstream_tags)
                t.raise_for_status()
                tags = t.json() or {}
                models = tags.get("models", [])
                data = {
                    "object": "list",
                    "data": [{"id": m.get("name"), "object": "model", "owned_by": "ollama"} for m in models],
                }
                return JSONResponse(data)
            r.raise_for_status()
            return JSONResponse(r.json())
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=str(e))


@router.post("/v1/chat/completions")
async def chat_completions(
    payload: ChatRequest = Body(
        ...,
        example={
            "model": "llama3.1",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "How do I cook pasta al dente?"}
            ],
            "temperature": 0.2,
            "max_tokens": 256,
            "stream": False,
            "use_rag": True,
            "top_k": 6,
        },
        description="OpenAI-style chat completion request body."
    ),
    _: dict | None = Depends(require_auth),
):
    """
    Accepts OpenAI-style JSON body (model, messages, …)
    """
    model = (payload.model or getattr(settings, "DEFAULT_MODEL", "llama3.1")).strip()
    if model == "llama3":
        model = "llama3.1"

    temperature = (
        payload.temperature
        if payload.temperature is not None
        else getattr(settings, "TUTOR_TEMPERATURE", 0.2)
    )

    DEFAULT_MAX_TOKENS = getattr(settings, "TUTOR_MAX_TOKENS", 2048)
    MIN_COMPLETION_TOKENS = getattr(settings, "MIN_COMPLETION_TOKENS", 512)

    requested = payload.max_tokens
    if requested is None:
        max_tokens = DEFAULT_MAX_TOKENS
    else:
        max_tokens = max(requested, MIN_COMPLETION_TOKENS)

    for m in payload.messages:
        m.content = redact_pii(m.content)

    REQS.labels("/v1/chat/completions").inc()

    rag_enabled_default = bool(getattr(settings, "RAG_ENABLED", True))
    use_rag = bool(payload.use_rag) if payload.use_rag is not None else rag_enabled_default

    top_k = int(payload.top_k) if payload.top_k is not None else int(getattr(settings, "RAG_TOP_K", 6))
    min_score = float(payload.min_score) if payload.min_score is not None else float(getattr(settings, "RAG_MIN_SCORE", 0.0))
    rag_filters = payload.rag_filters if isinstance(payload.rag_filters, dict) else None

    rag_chunks: List[RetrievedChunk] = []
    rag_query = ""

    try:
        if use_rag:
            rag_query = _extract_last_user_query([m.model_dump() for m in payload.messages])
            print("[rag] enabled query=", repr(rag_query), " top_k=", top_k, " min_score=", min_score)

            if rag_query:
                rag_chunks = await rag_retrieve(
                    rag_query,
                    top_k=top_k,
                    min_score=min_score,
                    filters=rag_filters,
                )
            print("[rag] retrieved chunks:", len(rag_chunks))

    except Exception as e:
        print(f"[/v1/chat/completions] RAG retrieval failed: {e}")
        rag_chunks = []

    final_messages_dicts: List[Dict[str, str]] = _inject_rag_context_messages(
        messages=[m.model_dump() for m in payload.messages],
        chunks=rag_chunks,
    )

    base = getattr(settings, "VLLM_ENDPOINT", "http://127.0.0.1:11434").rstrip("/")
    upstream_v1 = f"{base}/v1/chat/completions"
    upstream_api = f"{base}/api/chat"

    openai_req = {
        "model": model,
        "messages": final_messages_dicts,
        "temperature": temperature,
        "stream": False,
    }
    if max_tokens is not None:
        openai_req["max_tokens"] = max_tokens

    timeout = httpx.Timeout(connect=10.0, read=None, write=10.0, pool=10.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            r = await client.post(upstream_v1, json=openai_req)

            print(
                f"[chat_completions] upstream_v1 status={r.status_code} "
                f"bytes={len(r.content)} rag_enabled={use_rag} rag_chunks={len(rag_chunks)}"
            )

            fallback = False
            if r.status_code == 404:
                fallback = True
            elif r.status_code == 400:
                try:
                    j = r.json()
                    err = (j or {}).get("error") or {}
                    msg = (err.get("message") or "").lower()
                    if any(s in msg for s in (
                        "model is required",
                        "model not found",
                        "no such model",
                        "unknown model",
                    )):
                        fallback = True
                except Exception:
                    pass

            if fallback:
                options: dict = {"temperature": temperature}
                if max_tokens is not None:
                    options["num_predict"] = max_tokens

                ollama_req = {
                    "model": model,
                    "messages": final_messages_dicts,
                    "options": options,
                    "stream": False,
                }

                r = await client.post(upstream_api, json=ollama_req)
                if r.status_code >= 400:
                    raise HTTPException(
                        status_code=r.status_code,
                        detail=r.text or r.content.decode("utf-8", "replace"),
                    )

                data = r.json()
                msg = (data or {}).get("message") or {}
                out = {
                    "id": data.get("id") or "ollama-chat",
                    "object": "chat.completion",
                    "created": 0,
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": msg.get("role") or "assistant",
                            "content": redact_pii(msg.get("content") or ""),
                        },
                        "finish_reason": "stop",
                    }],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    "rag": {"enabled": use_rag, "query": rag_query, "top_k": top_k, "num_chunks": len(rag_chunks)},
                    "citations": [
                        {"index": i + 1, "source": c.source, "id": c.id, "score": c.score, "meta": c.meta}
                        for i, c in enumerate(rag_chunks)
                    ],
                }
                try:
                    TOKENS_IN.inc(0)
                    TOKENS_OUT.inc(0)
                except Exception:
                    pass
                return JSONResponse(out)

            if r.status_code >= 400:
                raise HTTPException(
                    status_code=r.status_code,
                    detail=r.text or r.content.decode("utf-8", "replace"),
                )

            data = r.json()

            # Metrics (OpenAI-style)
            usage = data.get("usage") or {}
            try:
                TOKENS_IN.inc(usage.get("prompt_tokens") or 0)
                TOKENS_OUT.inc(usage.get("completion_tokens") or 0)
            except Exception:
                pass

            # Redact outbound
            for choice in data.get("choices", []):
                msg = choice.get("message") or {}
                if isinstance(msg.get("content"), str):
                    msg["content"] = redact_pii(msg["content"])

            # Extra metadata
            data["rag"] = {"enabled": use_rag, "query": rag_query, "top_k": top_k, "num_chunks": len(rag_chunks)}
            data["citations"] = [
                {"index": i + 1, "source": c.source, "id": c.id, "score": c.score, "meta": c.meta}
                for i, c in enumerate(rag_chunks)
            ]

            return JSONResponse(data)

        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=str(e))
