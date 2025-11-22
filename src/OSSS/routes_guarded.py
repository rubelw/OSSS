# src/OSSS/routes_guarded.py
import os
import time
import json
import logging
from pathlib import Path
from typing import Literal, List, Optional, Any
from fastapi.responses import JSONResponse

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .safety import guarded_chat

log = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["guarded"])


# ---- Request/response schemas ----
class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    model: str = Field(
        default="llama3.1",
        description="Target model (default: llama3.1)",
    )
    messages: List[Message] = Field(
        default=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "How do I cook pasta al dente?"},
        ],
        description="Conversation messages for the model",
    )
    temperature: float = Field(default=0.2, description="Sampling temperature")
    max_tokens: int = Field(default=256, description="Maximum tokens to generate")
    stream: bool = Field(default=False, description="Whether to stream the response")


class RetrievedChunk(BaseModel):
    filename: str
    chunk_index: int
    text_preview: str
    image_paths: List[str] = []
    score: Optional[float] = None
    page_index: Optional[int] = None
    page_chunk_index: Optional[int] = None


class ChatSafeResponse(BaseModel):
    """
    Wrapper response for /v1/chat/safe:

    {
      "answer": { ...OpenAI-style chat.completion... },
      "retrieved_chunks": [ { filename, chunk_index, text_preview, image_paths } ]
    }
    """
    answer: Any
    retrieved_chunks: List[RetrievedChunk] = []


def to_public_image_url(path: str, request: Request) -> str:
    """
    Convert a stored path like:
        "vector_indexes/main/images/foo_p2_abcd.png"
    into a public URL like:
        "http://localhost:8081/rag-images/main/foo_p2_abcd.png"
    """
    p = Path(path)
    parts = p.parts  # e.g. ['vector_indexes', 'main', 'images', 'foo_p2_abcd.png']

    # index name is 'main' / 'tutor' / 'agent'
    index_name = parts[1] if len(parts) > 1 else "main"
    filename = parts[-1]

    base_url = os.getenv("OSSS_PUBLIC_BASE_URL", str(request.base_url).rstrip("/"))
    # e.g. "http://localhost:8081"
    return f"{base_url}/rag-images/{index_name}/{filename}"


# ---- Very simple JSONL-based retrieval -------------------------------------
# This is intentionally dumb: it just reads embeddings.jsonl and returns
# the first top_k entries that have text/image metadata.
#
# Once you confirm images flow through to the UI, you can replace this with
# your real vector search.
# ---------------------------------------------------------------------------
def _index_path_for(index_name: str) -> Path:
    """
    For now we only care about the 'main' index; tune this later for tutor/agent.
    """
    env_path = os.getenv("OSSS_ADDITIONAL_INDEX_PATH")
    if env_path:
        return Path(env_path)

    # Fallback to your likely default
    return Path("/workspace/vector_indexes/main/embeddings.jsonl")


async def retrieve_context_with_chunks(
    query: str,
    index_name: str = "main",
    top_k: int = 5,
) -> List[dict]:
    """
    Naive retrieval over your embeddings.jsonl format.

    Each line in embeddings.jsonl (from your sample) looks like:

      {
        "id": "...",
        "source": "school_board/2025-3-10/Board Workshop Strategic Planning.pdf",
        "filename": "Board Workshop Strategic Planning.pdf",
        "chunk_index": 0,
        "page_index": 0,
        "page_chunk_index": 0,
        "text": "BoardWorkshopStrategicPlanning ... The image is a logo ...",
        "embedding": [...],
        "image_paths": ["vector_indexes/main/images/Board ...jpeg"],
        "image_ocr_texts": ["..."]
      }

    We ignore `embedding` here and just surface filename/text/image_paths.
    """

    path = _index_path_for(index_name)
    if not path.exists():
        log.warning("RAG index not found at %s; returning no chunks", path)
        return []

    chunks: List[dict] = []

    try:
        with path.open("r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue

                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    log.warning(
                        "Skipping bad JSONL line %s in %s", line_idx, path
                    )
                    continue

                text = obj.get("text") or ""
                if not text:
                    continue

                filename = (
                    obj.get("filename")
                    or obj.get("source")
                    or f"{index_name}.jsonl"
                )

                image_paths = obj.get("image_paths") or []

                # Simple keyword bump: prefer chunks that mention the query tokens
                score = 0.0
                if query:
                    q = query.lower()
                    score = sum(1.0 for token in q.split() if token in text.lower())

                chunk = {
                    "filename": filename,
                    "chunk_index": obj.get("chunk_index", line_idx),
                    "text_preview": text[:500],
                    "image_paths": image_paths,
                    "score": score,
                    "page_index": obj.get("page_index"),
                    "page_chunk_index": obj.get("page_chunk_index"),
                }
                chunks.append(chunk)

    except Exception as e:
        log.exception("Error reading RAG index %s: %s", path, e)
        return []

    # Sort by our dumb score so queries like "logo" float the right chunks up
    chunks.sort(key=lambda c: c.get("score") or 0.0, reverse=True)

    result = chunks[:top_k]
    log.info(
        "retrieve_context_with_chunks: returning %d chunks from %s",
        len(result),
        path,
    )
    return result

# ---- Route -----------------------------------------------------------------
@router.post("/chat/safe")
async def chat_safe(req: ChatRequest, request: Request) -> JSONResponse:
    """
    Protected chat endpoint with input/output safety checks + RAG/image metadata.

    Response shape (matches what your ChatClient.tsx expects):

    {
      "answer": { ...OpenAI-style chat.completion... },
      "retrieved_chunks": [
        {
          "filename": "...",
          "chunk_index": 0,
          "text_preview": "...",
          "image_paths": ["http://localhost:8081/rag-images/main/....jpeg", ...],
          "score": 5.0,
          "page_index": 4,
          "page_chunk_index": 0
        },
        ...
      ]
    }
    """
    # ---- 1) Guarded model call -------------------------------------------------
    blocked, content = await guarded_chat([m.model_dump() for m in req.messages])
    #if blocked:
    #    raise HTTPException(
    #        status_code=400,
    #        detail={"blocked": True, "reason": content},
    #    )

    if not content or not content.strip():
        content = "(Guarded chat returned an empty reply from the model.)"

    # ---- 2) RAG retrieval based on the latest user message ---------------------
    try:
        last_user = next(
            (m for m in reversed(req.messages) if m.role == "user"),
            None,
        )
        query = last_user.content if last_user else ""
        raw_chunks = await retrieve_context_with_chunks(
            query=query,
            index_name="main",
            top_k=5,
        )
    except Exception:
        log.exception("Error during retrieve_context_with_chunks; returning no RAG chunks.")
        raw_chunks = []

    # ---- 3) Normalize into RetrievedChunk models, mapping image paths -> URLs --
    retrieved_chunks: List[RetrievedChunk] = []
    for i, ch in enumerate(raw_chunks):
        raw_image_paths: List[str] = ch.get("image_paths") or []
        public_image_urls = [
            to_public_image_url(p, request)
            for p in raw_image_paths
            if p
        ]

        retrieved_chunks.append(
            RetrievedChunk(
                filename=ch.get("filename") or "unknown",
                chunk_index=ch.get("chunk_index") or i,
                text_preview=ch.get("text_preview") or "",
                image_paths=public_image_urls,
                score=ch.get("score"),
                page_index=ch.get("page_index"),
                page_chunk_index=ch.get("page_chunk_index"),
            )
        )

    # ---- 4) OpenAI-style "answer" object (what the client already understands) -
    answer_payload: dict = {
        "id": "chatcmpl-safe-1",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": req.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
        "meta": {
            "guarded": True,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
            "stream": req.stream,
        },
    }

    # ---- 5) Combine into the exact JSON shape the React client expects ---------
    combined = {
      "answer": answer_payload,
      "retrieved_chunks": [c.model_dump() for c in retrieved_chunks],
    }

    log.debug("chat_safe combined response: %s", combined)

    return JSONResponse(content=combined)