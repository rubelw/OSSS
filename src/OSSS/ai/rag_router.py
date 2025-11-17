# src/OSSS/ai/rag_router.py
from __future__ import annotations

from typing import Optional, List

import httpx
import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from OSSS.ai.additional_index import top_k

# Try to reuse the same ChatMessage model from your gateway
try:
    from OSSS.api.routers.ai_gateway import ChatMessage, redact_pii  # type: ignore
except Exception:
    # Fallback minimal definitions (won't be used if import above works)
    class ChatMessage(BaseModel):
        role: str
        content: str

    def redact_pii(text: str) -> str:
        return text


# Try to reuse your real settings; if not, fall back like the gateway does
try:
    from OSSS.config import settings as _settings  # type: ignore
    settings = _settings
except Exception:  # fallback, same as in your ai_gateway
    class _Settings:
        VLLM_ENDPOINT: str = "http://host.containers.internal:11434"
        TUTOR_TEMPERATURE: float = 0.2
        TUTOR_MAX_TOKENS: int = 512
        DEFAULT_MODEL: str = "mistral"

    settings = _Settings()  # type: ignore


router = APIRouter(
    prefix="/ai",
    tags=["ai-rag"],
)


# ---- auth guard: reuse your real auth if available ----
try:
    from OSSS.auth.deps import require_user  # or require_auth / require_admin in your repo

    def _auth_guard(user=Depends(require_user)):
        return user

except Exception:
    # dev fallback: no auth
    def _auth_guard():
        return None


class RAGRequest(BaseModel):
    model: Optional[str] = "mistral"
    messages: List[ChatMessage]
    max_tokens: Optional[int] = 512
    temperature: Optional[float] = 0.1
    debug: Optional[bool] = True


@router.post("/chat/rag")
async def chat_rag(
    payload: RAGRequest,
    _: dict | None = Depends(_auth_guard),
):
    """
    Retrieval-Augmented Chat using the additional_llm_data index (embeddings.jsonl).

    1) Embed user query with nomic-embed-text
    2) Retrieve top-k chunks from embeddings.jsonl
    3) Prepend those as grounded system context
    4) Call Ollama /v1/chat/completions with that context
    """

    base = getattr(settings, "VLLM_ENDPOINT", "http://host.containers.internal:11434").rstrip("/")
    embed_url = f"{base}/api/embeddings"
    chat_url = f"{base}/v1/chat/completions"

    # ---- model / params ----
    model = (payload.model or getattr(settings, "DEFAULT_MODEL", "mistral")).strip()
    debug = bool(getattr(payload, "debug", False))

    if model == "mistral":
        model = "mistral"

    temperature = (
        payload.temperature
        if payload.temperature is not None
        else getattr(settings, "TUTOR_TEMPERATURE", 0.1)
    )
    max_tokens = payload.max_tokens or getattr(settings, "TUTOR_MAX_TOKENS", 512)

    # ---- 1) last user message ----
    user_messages = [m for m in payload.messages if m.role == "user"]
    if not user_messages:
        raise HTTPException(status_code=400, detail="No user message found")
    query = user_messages[-1].content

    # ---- 2) embed query ----
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Ollama /api/embeddings expects {"model": "...", "prompt": "..."}
        embed_req = {"model": "nomic-embed-text", "prompt": query}
        er = await client.post(embed_url, json=embed_req)
        if er.status_code >= 400:
            raise HTTPException(status_code=er.status_code, detail=er.text)

        ej = er.json()
        print("[/ai/chat/rag] embed_raw:", ej)

        # Handle multiple possible schemas:
        # 1) OpenAI-style: {"data":[{"embedding":[...]}]}
        # 2) Ollama-style: {"embedding":[...]}
        # 3) Some servers: {"embeddings":[[...], [...]]}
        if isinstance(ej, dict) and "data" in ej:
            vec = ej["data"][0]["embedding"]
        elif isinstance(ej, dict) and "embedding" in ej:
            vec = ej["embedding"]
        elif isinstance(ej, dict) and "embeddings" in ej:
            vec = ej["embeddings"][0]
        else:
            # Surface the full response so you can see what's going on
            raise HTTPException(
                status_code=500,
                detail={"error": "Unexpected embedding response schema", "response": ej},
            )

        query_emb = np.array(vec, dtype="float32")

    # ---- 3) top-k neighbors ----
    neighbors = top_k(query_emb, k=8)

    # Detailed debug of retrieval
    print("[/ai/chat/rag] retrieved_neighbors_count=", len(neighbors))
    for i, (score, chunk) in enumerate(neighbors[:3]):
        print(
            f"[/ai/chat/rag] hit#{i} score={score:.4f} file={getattr(chunk, 'filename', '?')} "
            f"idx={getattr(chunk, 'chunk_index', '?')} snippet={repr(chunk.text[:200])}"
        )

    if not neighbors:
        context = "No relevant local context found in the DCG PDFs."
    else:
        parts = []
        for score, chunk in neighbors:
            parts.append(
                f"[score={score:.3f} | file={chunk.filename} | idx={chunk.chunk_index}]\n{chunk.text}"
            )
        context = "\n\n".join(parts)

    # DEBUG: log what we retrieved so you can verify it’s using staff directory
    print("[/ai/chat/rag] retrieved_chunks=", len(neighbors))
    if neighbors:
        first_score, first_chunk = neighbors[0]
        print(
            "[/ai/chat/rag] first_chunk_snippet=",
            f"score={first_score:.3f} file={getattr(first_chunk, 'filename', '?')} "
            f"idx={getattr(first_chunk, 'chunk_index', '?')} ",
            repr(first_chunk.text[:300]),
        )

    # ---- 4) build grounded system prompt ----
    system_text = (
        "You are a local assistant for the Dallas Center-Grimes (DCG) Community School District.\n"
        "Use ONLY the information in the CONTEXT below when answering questions about staff, "
        "roles, titles, or district details.\n"
        "If the answer is not explicitly in the context, reply exactly:\n"
        "\"I'm not sure from the local directory.\"\n"
        "Do NOT guess. Do NOT use outside web knowledge.\n\n"
        f"CONTEXT:\n{context}\n\n"
        "Answer clearly. If you mention a staff role (like Superintendent), give the name and role."
    )

    messages = [
        {"role": "system", "content": system_text},
        *[m.model_dump() for m in payload.messages],
    ]

    chat_req = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(chat_url, json=chat_req)

        print(
            "[/ai/chat/rag] upstream_v1 status=",
            r.status_code,
            " bytes=",
            len(r.content),
        )

        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)

        data = r.json()

        # quick debug on model behavior
        try:
            choices = data.get("choices") or []
            first = choices[0] if choices else {}
            finish_reason = first.get("finish_reason")
            usage = data.get("usage") or {}
            msg = first.get("message") or {}
            content = msg.get("content", "")

            print(
                "[/ai/chat/rag] finish_reason=",
                finish_reason,
                " prompt_tokens=",
                usage.get("prompt_tokens"),
                " completion_tokens=",
                usage.get("completion_tokens"),
                " content_len=",
                len(content),
            )
            print("[/ai/chat/rag] content tail:", repr(content[-200:]))
        except Exception as e:
            print("[/ai/chat/rag] debug inspection failed:", e)

        # redact outbound if needed
        for choice in data.get("choices", []):
            msg = choice.get("message") or {}
            if isinstance(msg.get("content"), str):
                msg["content"] = redact_pii(msg["content"])

        # ---- debug payload: return neighbors along with the answer ----
        if debug:
            debug_neighbors = []
            for score, chunk in neighbors:
                debug_neighbors.append(
                    {
                        "score": float(score),
                        "filename": getattr(chunk, "filename", None),
                        "chunk_index": getattr(chunk, "chunk_index", None),
                        "text_preview": chunk.text[:800],
                    }
                )
            return {
                "answer": data,
                "retrieved_chunks": debug_neighbors,
            }

        return data
