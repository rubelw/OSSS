# src/OSSS/ai/rag_router.py
from __future__ import annotations

from operator import truediv
from typing import Optional, List
import logging
import httpx
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile
from pydantic import BaseModel, Field

import requests
import json
import sys

sys.path.append('/workspace/src/MetaGPT')

from MetaGPT.roles_registry import ROLE_REGISTRY
from MetaGPT.roles.registration import RegistrationRole  # Import the registration role

from OSSS.ai import additional_index
from OSSS.ai.intent_classifier import classify_intent
from OSSS.ai.intents import Intent

logger = logging.getLogger("OSSS.ai.rag_router")

from OSSS.ai.additional_index import top_k, INDEX_KINDS, get_docs

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
        # Allow up to 2048 tokens by default
        TUTOR_MAX_TOKENS: int = 2048
        DEFAULT_MODEL: str = "llama3.2-vision"

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
    model: Optional[str] = "llama3.2-vision"
    messages: List[ChatMessage] = Field(
        default_factory=lambda: [
            ChatMessage(
                role="system",
                content="You are a helpful assistant."
            )
        ],
        description="Conversation messages for the model",
    )
    # Default to 2048 if the client doesn't specify
    max_tokens: Optional[int] = 2048
    temperature: Optional[float] = 0.1
    debug: Optional[bool] = False
    # NEW: which additional index to query ("main", "tutor", or "agent")
    index: Optional[str] = "main"
    agent_session_id: Optional[str] = None  # Context ID for session tracking
    intent: Optional[str] = None  # Optional field to override intent classification



def _normalize_dcg_expansion(text: str) -> str:
    """
    Force 'DCG' to only mean Dallas Center-Grimes Community School District
    in the final answer. Fixes common wrong expansions from the model.
    """
    if not isinstance(text, str):
        return text

    wrong_phrases = [
        "Des Moines Christian School",
        "Des Moines Christian Schools",
        "Des Moines Christian",
        "Des Moines Community School District",
        "Des Moines Community Schools",
        "Des Moines Community School",
    ]

    for wrong in wrong_phrases:
        if wrong in text:
            text = text.replace(
                wrong,
                "Dallas Center-Grimes Community School District",
            )

    # Optional: make the expansion nice when it's used with DCG
    text = text.replace(
        "DCG (Dallas Center-Grimes Community School District)",
        "DCG (Dallas Center-Grimes Community School District)",
    )

    return text

DEFAULT_PAYLOAD = (
    '{"model":"llama3.2-vision",'
    '"messages":[{"role":"system","content":"You are a helpful assistant."}],'
    '"max_tokens":2048,'
    '"temperature":0.1,'
    '"debug":false,'
    '"index":"main"}'
)


@router.get("/debug/rag-sample")
def rag_sample(index: str = "main"):
    """
    Quick debug endpoint to inspect a few chunks from the loaded in-memory index.

    Effective URL: /ai/debug/rag-sample  (because router has prefix="/ai")
    """
    # Ensure the index name is valid; raises ValueError if not
    if index not in INDEX_KINDS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown index '{index}'. Valid values: {', '.join(INDEX_KINDS)}",
        )

    # This will lazy-load from JSONL on first call, then re-use _DOCS cache
    chunks = get_docs(index=index)

    if not chunks:
        return {
            "index": index,
            "samples": [],
            "message": "Index loaded but contains no chunks. Check your embeddings.jsonl.",
        }

    samples = []
    for c in chunks[:5]:
        samples.append(
            {
                "source": getattr(c, "source", None),
                "filename": getattr(c, "filename", None),
                "chunk_index": getattr(c, "chunk_index", None),
                "text_preview": getattr(c, "text", "")[:200],
            }
        )

    return {"index": index, "samples": samples}


@router.post("/chat/rag")
async def chat_rag(
    payload: str = Form(DEFAULT_PAYLOAD),
    files: list[UploadFile] | None = File(default=None)
):
    """
    Retrieval-Augmented Chat using the additional_llm_data index (embeddings.jsonl).

    1) Embed user query with nomic-embed-text
    2) Retrieve top-k chunks from embeddings.jsonl
    3) Prepend those as grounded system context
    4) Call Ollama /v1/chat/completions with that context
    """

    # Convert raw JSON string from form field into pydantic model
    try:
        rag = RAGRequest.model_validate_json(payload)
    except Exception as e:
        raise HTTPException(400, f"Invalid rag JSON: {e}")

    # Now you MUST use rag.model, rag.messages, rag.index, etc.
    print("MODEL:", rag.model)
    print("MESSAGES:", rag.messages)
    print("INDEX:", rag.index)
    print("RAG:", str(rag))

    base = getattr(settings, "VLLM_ENDPOINT", "http://host.containers.internal:11434").rstrip("/")
    embed_url = f"{base}/api/embeddings"
    chat_url = f"{base}/v1/chat/completions"

    # ---- model / params ----
    model = (rag.model or getattr(settings, "DEFAULT_MODEL", "llama3.2-vision")).strip()
    debug = bool(getattr(rag, "debug", False))

    if model == "llama3.2-vision":
        model = "llama3.2-vision"

    temperature = (
        rag.temperature
        if rag.temperature is not None
        else getattr(settings, "TUTOR_TEMPERATURE", 0.1)
    )

    # Handle file processing (you can save or process files here)
    if files:
        for file in files:
            contents = await file.read()
            logger.info(f"Processing file: {file.filename}")
            # Optionally save the file or use the contents for further processing
            # For example, you can save the file to disk:
            # with open(f"./uploads/{file.filename}", "wb") as f:
            #     f.write(contents)


    # Respect caller's max_tokens but cap at 2048, with sane defaults
    requested_max = (
        rag.max_tokens
        if rag.max_tokens is not None
        else getattr(settings, "TUTOR_MAX_TOKENS", 2048)
    )
    try:
        requested_max_int = int(requested_max)
    except (TypeError, ValueError):
        requested_max_int = 2048
    max_tokens = max(1, min(requested_max_int, 2048))

    # ---- 1) last user message ----
    user_messages = [m for m in rag.messages if m.role == "user"]
    if not user_messages:
        raise HTTPException(status_code=400, detail="No user message found")
    query = user_messages[-1].content

    # ---- Intent Classification ----
    intent = "general"  # Default to general intent if none specified
    try:
        # Use a function to classify the intent of the query
        intent_result = await classify_intent(query)
        intent = intent_result.intent
        logger.info(f"Classified intent: {intent}")
    except Exception as e:
        logger.error(f"Error classifying intent: {e}")

    logger.info(f"Intent for the query: {intent}")

    # ---- Handle special routing for specific intents (e.g., registration) ----
    if intent == "register_new_student":
        logger.info(f"Processing registration for new student with query: {query}")

        # Prepare action data as a dictionary
        action_data = {
            "query": query,
            "registration_agent_id": "registration-agent",
            "registration_skill": "registration",
        }

        registration_url = "http://a2a:8086/admin/registration"

        try:
            response = requests.post(
                registration_url,
                headers={"Content-Type": "application/json"},
                data=json.dumps(action_data),
                timeout=60,
            )

            if response.status_code == 200:
                result = response.json()
                result["intent"] = "register_new_student"

                logger.info(f"Registration raw result from A2A: {result}")

                registration_run = result.get("registration_run", {}) or {}
                registration_status = registration_run.get("status", "Unknown")
                registration_message = registration_run.get(
                    "output_preview",
                    "No details available.",
                )

                # Build a debug_neighbors-style list so the frontend can treat it
                # like retrieved_chunks from RAG.
                debug_neighbors = [
                    {
                        "score": 1.0,  # synthetic score – always 'most relevant'
                        "filename": "registration_run",
                        "chunk_index": None,
                        "text_preview": registration_message[:800],
                        "image_paths": None,
                        "page_index": None,
                        "page_chunk_index": None,
                    }
                ]

                # Shape the response exactly like the RAG debug format:
                # {
                #   "answer": <LLM-like object or message>,
                #   "retrieved_chunks": [...],
                #   "index": <str>,
                #   "intent": <str>
                # }
                user_response = {
                    "answer": {
                        # Minimal shape needed for ChatClient.tsx:
                        # it reads core?.message?.content
                        "message": {
                            "role": "assistant",
                            "content": registration_message,
                        },
                        # Optional extras if you want to mimic Ollama/OpenAI more closely:
                        "status": registration_status,
                    },
                    "retrieved_chunks": debug_neighbors,
                    "index": "registration",
                    "intent": "register_new_student",
                }

                logger.info(f"Registration user_response: {user_response}")
                return user_response

            else:
                logger.error(
                    f"Failed to register student: HTTP {response.status_code} {response.text}"
                )
                return {
                    "answer": {
                        "message": {
                            "role": "assistant",
                            "content": (
                                "Registration failed while contacting the registration service. "
                                "Please try again or contact support."
                            ),
                        }
                    },
                    "retrieved_chunks": [],
                    "index": "registration",
                    "intent": "register_new_student",
                    "error": "Registration failed",
                    "details": response.text,
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during registration: {e}")
            return {
                "answer": {
                    "message": {
                        "role": "assistant",
                        "content": (
                            "There was a network error while trying to start registration. "
                            "Please try again shortly."
                        ),
                    }
                },
                "retrieved_chunks": [],
                "index": "registration",
                "intent": "register_new_student",
                "error": "Network error",
                "details": str(e),
            }

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
    # Choose which additional index to query: main / tutor / agent
    requested_index = (rag.index or "main").strip()
    if requested_index not in INDEX_KINDS:
        print(
            f"[/ai/chat/rag] WARNING: unknown index '{requested_index}', "
            f"falling back to 'main'. Valid values: {', '.join(INDEX_KINDS)}"
        )
        requested_index = "main"

    # Broader retrieval so the model can see more staff-directory chunks
    neighbors = top_k(query_emb, k=12, index=requested_index)

    # Detailed debug of retrieval
    print(
        "[/ai/chat/rag] retrieved_neighbors_count=",
        len(neighbors),
        " index=",
        requested_index,
    )
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
            # image metadata in the context (for the model, optional)
            image_paths = getattr(chunk, "image_paths", None) or []
            meta = f"[score={score:.3f} | file={chunk.filename} | idx={chunk.chunk_index}]"
            if image_paths:
                meta += f" | images={len(image_paths)} attached"
            parts.append(f"{meta}\n{chunk.text}")
        context = "\n\n".join(parts)

    # DEBUG: log what we retrieved so you can verify it’s using the right index
    print("[/ai/chat/rag] retrieved_chunks=", len(neighbors))
    if neighbors:
        first_score, first_chunk = neighbors[0]
        print(
            "[/ai/chat/rag] first_chunk_snippet=",
            f"index={requested_index} "
            f"score={first_score:.3f} file={getattr(first_chunk, 'filename', '?')} "
            f"idx={getattr(first_chunk, 'chunk_index', '?')} ",
            repr(first_chunk.text[:300]),
        )

    # ---- 4) build grounded system prompt ----
    system_text = (
        "In this conversation, the acronym 'DCG' ALWAYS means 'Dallas Center-Grimes Community "
        "School District' and never anything else. It does NOT mean Des Moines Christian or any "
        "other organization. If you expand 'DCG', expand it only as 'Dallas Center-Grimes "
        "Community School District'.\n"
        "If the answer is not explicitly in the context, reply exactly:\n"
        "\"I'm not sure from the local directory.\"\n"
        "Do NOT guess. Do NOT use outside web knowledge.\n\n"
        f"CONTEXT:\n{context}\n\n"
        "Answer clearly. If you mention a staff role (like Superintendent), give the name and role."
    )

    messages = [
        {"role": "system", "content": system_text},
        *[m.model_dump() for m in rag.messages],
    ]

    chat_req = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        # ---- first completion call ----
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

        # ---- AUTO-CONTINUE LOOP: if finish_reason == 'length', keep going ----
        try:
            choices = data.get("choices") or []
            first = choices[0] if choices else {}
            finish_reason = first.get("finish_reason")
            msg = first.get("message") or {}
            content = msg.get("content", "") or ""

            full_content = content
            continue_count = 0
            max_continues = 5  # safety guard; bump if you want even more

            while finish_reason == "length" and continue_count < max_continues:
                continue_count += 1
                print(
                    f"[/ai/chat/rag] auto-continue pass={continue_count} "
                    f"current_len={len(full_content)}"
                )

                # Extend the conversation with the previous assistant text and a "continue" request
                messages.append({"role": "assistant", "content": content})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Continue the previous list from where you left off. "
                            "Do NOT repeat any previous names; only add new ones based on the same CONTEXT."
                        ),
                    }
                )
                chat_req["messages"] = messages

                r2 = await client.post(chat_url, json=chat_req)
                print(
                    "[/ai/chat/rag] upstream_v1 (continue) status=",
                    r2.status_code,
                    " bytes=",
                    len(r2.content),
                )
                if r2.status_code >= 400:
                    print(
                        "[/ai/chat/rag] auto-continue aborted: upstream error",
                        r2.status_code,
                    )
                    break

                data2 = r2.json()
                choices2 = data2.get("choices") or []
                first2 = choices2[0] if choices2 else {}
                finish_reason = first2.get("finish_reason")
                msg2 = first2.get("message") or {}
                content = msg2.get("content", "") or ""

                full_content += content
                data = data2  # keep latest metadata for usage / finish_reason logs

            # Ensure final `data` carries the stitched-together content
            if data.get("choices"):
                data["choices"][0].setdefault("message", {})
                data["choices"][0]["message"]["content"] = full_content

        except Exception as e:
            print("[/ai/chat/rag] auto-continue failed:", e)

        # ---- quick debug on final model behavior ----
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

        # normalize DCG expansion + redact outbound if needed
        for choice in data.get("choices", []):
            msg = choice.get("message") or {}
            if isinstance(msg.get("content"), str):
                content = msg["content"]
                # 1) fix any wrong DCG expansions
                content = _normalize_dcg_expansion(content)
                # 2) apply your existing PII redaction
                content = redact_pii(content)
                msg["content"] = content

        # ---- normalize intent for JSON payload back to the client ----
        intent_label: str | None = None
        try:
            # If you imported Intent at the top: from OSSS.ai.intents import Intent
            if isinstance(intent, Intent):
                intent_label = intent.value
            elif isinstance(intent, str):
                intent_label = intent
        except NameError:
            # 'intent' not defined in this code path
            intent_label = None

        # ---- debug rag: return neighbors along with the answer ----

        debug_neighbors = []
        for score, chunk in neighbors:
            debug_neighbors.append(
                {
                    "score": float(score),
                    "filename": getattr(chunk, "filename", None),
                    "chunk_index": getattr(chunk, "chunk_index", None),
                    "text_preview": chunk.text[:800],
                    # image paths from the indexer (relative to project root)
                    "image_paths": getattr(chunk, "image_paths", None),
                    "page_index": getattr(chunk, "page_index", None),
                    "page_chunk_index": getattr(chunk, "page_chunk_index", None),
                }
            )
        return {
            "answer": data,
            "retrieved_chunks": debug_neighbors,
            "index": requested_index,
            "intent": intent_label,
        }

