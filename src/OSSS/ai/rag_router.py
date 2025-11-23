# src/OSSS/ai/rag_router.py
from __future__ import annotations

from operator import truediv
from typing import Optional, List
import logging
import httpx
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile
from pydantic import BaseModel, Field
import ast

import requests
import json
import sys
from pathlib import Path
import shutil
import os

sys.path.append('/workspace/src/MetaGPT')

from MetaGPT.roles_registry import ROLE_REGISTRY
from MetaGPT.roles.registration import RegistrationRole  # Import the registration role

from OSSS.ai import additional_index
from OSSS.ai.intent_classifier import classify_intent
from OSSS.ai.intents import Intent

logger = logging.getLogger("OSSS.ai.rag_router")

from OSSS.ai.additional_index import top_k, INDEX_KINDS, get_docs

from OSSS.ai.session_store import (
    get_or_create_session,
    touch_session,
    prune_expired_sessions,
    RagSession,
)

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
        TUTOR_MAX_TOKENS: int = 8192
        DEFAULT_MODEL: str = "llama3.2-vision"
        RAG_UPLOAD_ROOT: str = "/tmp/osss_rag_uploads"

    settings = _Settings()  # type: ignore

# Root directory for per-session temp files
RAG_UPLOAD_ROOT = Path(getattr(settings, "RAG_UPLOAD_ROOT", "/tmp/osss_rag_uploads"))


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
    max_tokens: Optional[int] = 8192
    temperature: Optional[float] = 0.1
    debug: Optional[bool] = False
    # NEW: which additional index to query ("main", "tutor", or "agent")
    index: Optional[str] = "main"
    agent_session_id: Optional[str] = None  # Context ID for session tracking
    intent: Optional[str] = None  # Optional field to override intent classification
    # NEW: optional agent_id flag, echoed through to registration + response
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None


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
    '"max_tokens":8192,'
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

    # Extract optional agent_id from the request
    agent_id: Optional[str] = rag.agent_id
    agent_name: Optional[str] = rag.agent_name

    # Now you MUST use rag.model, rag.messages, rag.index, etc.
    print("MODEL:", rag.model)
    print("MESSAGES:", rag.messages)
    print("INDEX:", rag.index)
    print("AGENT_ID:", agent_id)
    print("RAG:", str(rag))

    # --- Session pruning + temp-file cleanup -------------------------
    expired_ids = prune_expired_sessions()
    if expired_ids:
        logger.info(f"[RAG] pruned {len(expired_ids)} expired sessions")
        for sid in expired_ids:
            sess_dir = RAG_UPLOAD_ROOT / sid
            if sess_dir.exists():
                try:
                    shutil.rmtree(sess_dir)
                    logger.info(f"[RAG] removed temp dir for expired session {sid}: {sess_dir}")
                except Exception as e:
                    logger.warning(
                        f"[RAG] failed to remove temp dir for session {sid} at {sess_dir}: {e}"
                    )

    # --- Session handling (persistent store) -------------------------
    session = get_or_create_session(rag.agent_session_id)
    agent_session_id = session.id

    logger.info(
        f"[RAG] agent_session_id={agent_session_id} "
        f"turns={session.turns} "
        f"created_at={session.created_at.isoformat()} "
        f"last_access={session.last_access.isoformat()}"
    )

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

    # Handle file processing: store under a per-session temp directory
    if files:
        session_dir = RAG_UPLOAD_ROOT / agent_session_id
        try:
            session_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"[RAG] failed to create session upload dir {session_dir}: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to create session upload directory",
            )

        for file in files:
            try:
                contents = await file.read()
                dest_path = session_dir / file.filename
                # Overwrite if exists (open with "wb") – ensures latest upload wins
                with open(dest_path, "wb") as f:
                    f.write(contents)
                logger.info(
                    f"[RAG] saved uploaded file for session {agent_session_id}: {dest_path}"
                )
            except Exception as e:
                logger.error(
                    f"[RAG] failed to save uploaded file {file.filename} "
                    f"for session {agent_session_id}: {e}"
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to save uploaded file {file.filename}",
                )

    # ---- Gather list of files currently in this session's temp dir ---
    session_files: list[str] = []
    session_dir = RAG_UPLOAD_ROOT / agent_session_id
    if session_dir.exists() and session_dir.is_dir():
        try:
            for p in session_dir.iterdir():
                if p.is_file():
                    session_files.append(p.name)
        except Exception as e:
            logger.warning(
                f"[RAG] failed to list files for session {agent_session_id} "
                f"at {session_dir}: {e}"
            )

    # Respect caller's max_tokens but cap at 8192, with sane defaults
    requested_max = (
        rag.max_tokens
        if rag.max_tokens is not None
        else getattr(settings, "TUTOR_MAX_TOKENS", 8192)
    )
    try:
        requested_max_int = int(requested_max)
    except (TypeError, ValueError):
        requested_max_int = 2048
    max_tokens = max(1, min(requested_max_int, 8192))

    # ---- 1) last user message ----
    user_messages = [m for m in rag.messages if m.role == "user"]
    if not user_messages:
        raise HTTPException(status_code=400, detail="No user message found")
    query = user_messages[-1].content

    # ---- Look at any prior session intent ---------------------------
    session_intent = getattr(session, "intent", None)

    # ---- Intent Classification (this turn) --------------------------
    classified: str | Intent | None = "general"
    action: str | None = "read"
    action_confidence: float | None = None

    try:
        intent_result = await classify_intent(query)
        classified = intent_result.intent
        # NEW: CRUD-style action, default to "read" if classifier returns None
        action = getattr(intent_result, "action", None) or "read"
        action_confidence = getattr(intent_result, "action_confidence", None)

        logger.info(
            "Classified intent=%s action=%s action_confidence=%s",
            getattr(classified, "value", classified),
            action,
            action_confidence,
        )
        logger.info(f"Classified intent: {classified}")
    except Exception as e:
        logger.error(f"Error classifying intent: {e}")

    # Normalize classified intent
    if isinstance(classified, Intent):
        classified_label: str | None = classified.value
    elif isinstance(classified, str):
        classified_label = classified
    else:
        classified_label = None

    # ---- Make registration intent "sticky" --------------------------
    # If the session was already in registration mode, stay there.
    if session_intent == "register_new_student":
        intent_label = "register_new_student"
    else:
        # Otherwise, use the freshly classified label (or fall back)
        intent_label = classified_label or session_intent or "general"

    logger.info(
        "Effective intent for this turn: %r (session_intent=%r, classified=%r)",
        intent_label,
        session_intent,
        classified_label,
    )

    # Update persistent session metadata (including last_access timestamp)
    touch_session(
        agent_session_id,
        intent=intent_label,
        query=query,
    )

    # ---- Handle special routing for specific intents (e.g., registration) ----
    if intent_label == "register_new_student":
        logger.info(f"Processing registration for new student with query: {query}")

        action_data = {
            "query": query,
            "registration_agent_id": "registration-agent",
            "registration_skill": "registration",
            "agent_session_id": agent_session_id,
            "agent_id": agent_id,  # may be None, caller can override
            "agent_name": "registration",
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
                logger.info("Registration raw result from A2A: %s", result)

                registration_run = result.get("registration_run", {}) or {}

                # ---- 1) Pull the inner payload from output_preview --------
                inner_payload = None

                # (a) If registration_run["answer"] is already a dict, use it
                if isinstance(registration_run.get("answer"), dict):
                    inner_payload = registration_run["answer"]
                else:
                    op = registration_run.get("output_preview")
                    if isinstance(op, dict):
                        inner_payload = op
                    elif isinstance(op, str):
                        # Always *try* to parse, don’t require perfect { ... } wrapping,
                        # since the service may truncate or pad the string.
                        try:
                            import ast
                            inner_payload = ast.literal_eval(op)
                        except Exception as e:
                            logger.warning(
                                "Failed to parse output_preview as dict: %s op=%r",
                                e,
                                op[:200],
                            )
                            inner_payload = None

                # ---- 2) Normalize to simple fields ------------------------
                if isinstance(inner_payload, dict):
                    registration_answer_text = (
                            inner_payload.get("answer")
                            or inner_payload.get("message")
                            or "No details available."
                    )

                    registration_intent = inner_payload.get(
                        "intent",
                        registration_run.get("intent", "register_new_student"),
                    )

                    # Prefer what the registration agent says; then run-level; then static fallback
                    registration_agent_id = (
                            inner_payload.get("agent_id")
                            or registration_run.get("agent_id")
                            or "registration-agent"
                    )

                    registration_agent_name = (
                            inner_payload.get("agent_name")
                            or registration_run.get("agent_name")
                            or "Registration"
                    )

                    registration_session_id = (
                            inner_payload.get("agent_session_id")
                            or registration_run.get("agent_session_id")
                            or agent_session_id
                    )
                else:
                    # Could not parse, fall back to the raw preview string
                    op = registration_run.get("output_preview") or "No details available."
                    registration_answer_text = str(op)

                    registration_intent = registration_run.get(
                        "intent",
                        "register_new_student",
                    )

                    registration_agent_id = (
                            registration_run.get("agent_id")
                            or "registration-agent"
                    )

                    registration_agent_name = (
                            registration_run.get("agent_name")
                            or "Registration"
                    )

                    registration_session_id = (
                            registration_run.get("agent_session_id")
                            or agent_session_id
                    )

                # After you have registration_answer_text set:
                if isinstance(registration_answer_text, str):
                    stripped = registration_answer_text.strip()
                    # If the *answer itself* still looks like a dict string, try to unwrap again
                    if stripped.startswith("{") and ("'answer'" in stripped or '"answer"' in stripped):
                        try:
                            maybe_dict = ast.literal_eval(stripped)
                            if isinstance(maybe_dict, dict) and "answer" in maybe_dict:
                                registration_answer_text = maybe_dict["answer"]
                        except Exception as e:
                            logger.warning(
                                "Failed to normalize registration_answer_text as dict: %s text=%r",
                                e,
                                stripped[:200],
                            )

                # ---- 3) Build retrieved_chunks -----------------------------
                debug_neighbors = [
                    {
                        "score": 1.0,
                        "filename": "registration_run",
                        "chunk_index": None,
                        "text_preview": str(registration_answer_text)[:800],
                        "image_paths": None,
                        "page_index": None,
                        "page_chunk_index": None,
                    }
                ]

                # ---- 4) FINAL payload: same shape as normal RAG -----------
                user_response = {
                    "answer": {
                        "message": {
                            "role": "assistant",
                            "content": registration_answer_text,
                        },
                        "status": registration_run.get("status", "ok"),
                    },
                    "retrieved_chunks": debug_neighbors,
                    "index": "registration",
                    "intent": registration_intent,
                    "agent_session_id": registration_session_id,
                    "session_files": session_files,
                    "agent_id": registration_agent_id,
                    "agent_name": registration_agent_name,
                    "action": action,
                    "action_confidence": action_confidence,
                }

                logger.info(
                    "[RAG] response to client (registration success): %s",
                    json.dumps(user_response, ensure_ascii=False)[:4000],
                )

                return user_response

            else:
                logger.error(
                    f"Failed to register student: HTTP {response.status_code} {response.text}"
                )
                error_response = {
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
                    "agent_session_id": agent_session_id,
                    "session_files": session_files,
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "action": action,
                    "action_confidence": action_confidence,
                }

                logger.info(
                    "[RAG] response to client (registration error): %s",
                    json.dumps(error_response, ensure_ascii=False)[:4000],
                )

                return error_response

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during registration: {e}")
            network_error_response = {
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
                "agent_session_id": agent_session_id,
                "session_files": session_files,
                "agent_id": agent_id,
                "agent_name": agent_name,
                "action": action,
                "action_confidence": action_confidence,
            }

            logger.info(
                "[RAG] response to client (registration network error): %s",
                json.dumps(network_error_response, ensure_ascii=False)[:4000],
            )

            return network_error_response

    # ---- 2) embed query ----
    async with httpx.AsyncClient(timeout=10.0) as client:
        embed_req = {"model": "nomic-embed-text", "prompt": query}
        er = await client.post(embed_url, json=embed_req)
        if er.status_code >= 400:
            raise HTTPException(status_code=er.status_code, detail=er.text)

        ej = er.json()
        print("[/ai/chat/rag] embed_raw:", ej)

        if isinstance(ej, dict) and "data" in ej:
            vec = ej["data"][0]["embedding"]
        elif isinstance(ej, dict) and "embedding" in ej:
            vec = ej["embedding"]
        elif isinstance(ej, dict) and "embeddings" in ej:
            vec = ej["embeddings"][0]
        else:
            raise HTTPException(
                status_code=500,
                detail={"error": "Unexpected embedding response schema", "response": ej},
            )

        query_emb = np.array(vec, dtype="float32")

    # ---- 3) top-k neighbors ----
    requested_index = (rag.index or "main").strip()
    if requested_index not in INDEX_KINDS:
        print(
            f"[/ai/chat/rag] WARNING: unknown index '{requested_index}', "
            f"falling back to 'main'. Valid values: {', '.join(INDEX_KINDS)}"
        )
        requested_index = "main"

    neighbors = top_k(query_emb, k=12, index=requested_index)

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
            image_paths = getattr(chunk, "image_paths", None) or []
            meta = f"[score={score:.3f} | file={chunk.filename} | idx={chunk.chunk_index}]"
            if image_paths:
                meta += f" | images={len(image_paths)} attached"
            parts.append(f"{meta}\n{chunk.text}")
        context = "\n\n".join(parts)

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

        try:
            choices = data.get("choices") or []
            first = choices[0] if choices else {}
            finish_reason = first.get("finish_reason")
            msg = first.get("message") or {}
            content = msg.get("content", "") or ""

            full_content = content
            continue_count = 0
            max_continues = 20

            while finish_reason == "length" and continue_count < max_continues:
                continue_count += 1
                print(
                    f"[/ai/chat/rag] auto-continue pass={continue_count} "
                    f"current_len={len(full_content)}"
                )

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
                data = data2

            if data.get("choices"):
                data["choices"][0].setdefault("message", {})
                data["choices"][0]["message"]["content"] = full_content

        except Exception as e:
            print("[/ai/chat/rag] auto-continue failed:", e)

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

        for choice in data.get("choices", []):
            msg = choice.get("message") or {}
            if isinstance(msg.get("content"), str):
                content = msg["content"]
                content = _normalize_dcg_expansion(content)
                content = redact_pii(content)
                msg["content"] = content

        debug_neighbors = []
        for score, chunk in neighbors:
            debug_neighbors.append(
                {
                    "score": float(score),
                    "filename": getattr(chunk, "filename", None),
                    "chunk_index": getattr(chunk, "chunk_index", None),
                    "text_preview": chunk.text[:800],
                    "image_paths": getattr(chunk, "image_paths", None),
                    "page_index": getattr(chunk, "page_index", None),
                    "page_chunk_index": getattr(chunk, "page_chunk_index", None),
                    "source": getattr(chunk, "source", None),
                    "pdf_index_path": getattr(chunk, "pdf_index_path", None),
                }
            )

        response_payload = {
            "answer": data,
            "retrieved_chunks": debug_neighbors,
            "index": requested_index,
            "intent": intent_label,
            "agent_session_id": agent_session_id,
            "session_files": session_files,  # list of filenames in temp dir for this session
            "agent_id": agent_id,            # echo agent_id to ChatClient.tsx
            "agent_name": agent_name,        # echo agent_name to ChatClient.tsx
            "action": action,
            "action_confidence": action_confidence,
        }

        # 🔍 Log the final response going back to ChatClient.tsx
        try:
            logger.info(
                "[RAG] response to client (rag): %s",
                json.dumps(response_payload, ensure_ascii=False)[:4000],
            )
        except Exception as e:
            logger.warning(f"[RAG] failed to json.dumps response_payload: {e}")

        return response_payload
