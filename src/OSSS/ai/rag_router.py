# src/OSSS/ai/rag_router.py
from __future__ import annotations

from typing import Optional, List
import logging
from pathlib import Path
import shutil
import json

from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile

from OSSS.ai.router_agent import RAGRequest, RouterAgent
from OSSS.ai.additional_index import INDEX_KINDS, get_docs
from OSSS.ai.session_store import (
    get_or_create_session,
    prune_expired_sessions,
)

# ----------------------------------------------------------------------
# SETTINGS LOADING
# ----------------------------------------------------------------------
# We attempt to import the real OSSS settings module. If this fails
# (e.g., tests, dev shells, or partial installations), we fall back
# to a minimal inline settings object to avoid import failures.

try:
    from OSSS.config import settings as _settings  # type: ignore
    settings = _settings
except Exception:
    # Fallback for tests / debug environments.
    class _Settings:
        RAG_UPLOAD_ROOT: str = "/tmp/osss_rag_uploads"

    settings = _Settings()  # type: ignore


# ----------------------------------------------------------------------
# LOGGER INITIALIZATION
# ----------------------------------------------------------------------
logger = logging.getLogger("OSSS.ai.rag_router")

# Root folder where all temporary uploaded files (for RAG context)
# will be stored. Each chat session gets its own sub-folder.
RAG_UPLOAD_ROOT = Path(getattr(settings, "RAG_UPLOAD_ROOT", "/tmp/osss_rag_uploads"))


# ----------------------------------------------------------------------
# ROUTER SETUP
# ----------------------------------------------------------------------
# This router handles *all* “RAG chat” entrypoints for the OSSS AI API.
router = APIRouter(
    prefix="/ai",
    tags=["ai-rag"],
)


# ----------------------------------------------------------------------
# OPTIONAL AUTH GUARD
# ----------------------------------------------------------------------
# If OSSS.auth.deps.require_user exists, we enforce user authentication.
# If not available (tests or standalone dev), we silently disable auth.
try:
    from OSSS.auth.deps import require_user  # type: ignore

    def _auth_guard(user=Depends(require_user)):
        return user
except Exception:
    def _auth_guard():
        return None


# ----------------------------------------------------------------------
# DEFAULT MODEL PAYLOAD (used when no payload provided in HTML form)
# ----------------------------------------------------------------------
# This mirrors the typical JSON the client-side ChatClient.tsx sends.
DEFAULT_PAYLOAD = (
    '{"model":"llama3.2-vision",'
    '"messages":[{"role":"system","content":"You are a helpful assistant."}],'
    '"max_tokens":8192,'
    '"temperature":0.1,'
    '"debug":false,'
    '"index":"main"}'
)


# ======================================================================
# DEBUG ENDPOINT — VIEW SOME INDEX CHUNKS
# ======================================================================
@router.get("/debug/rag-sample")
def rag_sample(index: str = "main"):
    """
    Return 5 sample chunks from the loaded RAG index.
    Helps you validate that embeddings.jsonl parsed correctly.

    This is especially useful in development when you're unsure if
    your vector index loaded, or want to inspect chunk structure.

    Example:
        GET /ai/debug/rag-sample?index=main
    """

    # Validate index
    if index not in INDEX_KINDS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown index '{index}'. Valid values: {', '.join(INDEX_KINDS)}",
        )

    chunks = get_docs(index=index)
    if not chunks:
        return {
            "index": index,
            "samples": [],
            "message": (
                "Index loaded but contains no chunks. "
                "This usually means embeddings.jsonl is empty or failed to load."
            ),
        }

    # Take first 5 chunks (lightweight preview, not the whole index)
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


# ======================================================================
# MAIN CHAT ENDPOINT — RAG + Agent Routing
# ======================================================================
@router.post("/chat/rag")
async def chat_rag(
    payload: str = Form(DEFAULT_PAYLOAD),
    files: list[UploadFile] | None = File(default=None),
    user=Depends(_auth_guard),  # noqa: F841 — we keep this for future personalization
):
    """
    Entry point for OSSS’s RAG-driven multipurpose assistant.

    This endpoint is responsible for:
      1. Parsing the RAG payload from the browser (ChatClient.tsx).
      2. Managing and maintaining a *persistent chat session*.
      3. Accepting user-uploaded files for ephemeral session-scoped RAG.
      4. Calling the RouterAgent, which:
            - performs intent classification
            - selects an agent
            - applies RAG retrieval
            - runs the LLM
            - optionally chains sub-agents
      5. Returning the unified structured payload back to the UI.

    The router SHOULD NOT:
      - perform RAG logic directly
      - classify intents
      - call LLMs
      - parse embeddings
      - route to multiple agents itself

    Those responsibilities live in RouterAgent or deeper in the agent stack.
    """

    # ------------------------------------------------------------------
    # 1) Deserialize JSON payload into RAGRequest
    # ------------------------------------------------------------------
    try:
        rag = RAGRequest.model_validate_json(payload)
    except Exception as e:
        raise HTTPException(400, f"Invalid rag JSON: {e}")

    # ------------------------------------------------------------------
    # 2) SESSION EXPIRATION & CLEANUP
    # ------------------------------------------------------------------
    # prune_expired_sessions returns a list of session IDs that exceeded expiry time.
    expired_ids = prune_expired_sessions()
    if expired_ids:
        logger.info(f"[RAG] pruned {len(expired_ids)} expired sessions")

        # For each expired session, remove its upload directory entirely.
        for sid in expired_ids:
            sess_dir = RAG_UPLOAD_ROOT / sid
            if sess_dir.exists():
                try:
                    shutil.rmtree(sess_dir)
                    logger.info(
                        f"[RAG] removed temp dir for expired session {sid}: {sess_dir}"
                    )
                except Exception as e:
                    logger.warning(
                        f"[RAG] failed to remove temp dir for session {sid} "
                        f"at {sess_dir}: {e}"
                    )

    # ------------------------------------------------------------------
    # 3) SESSION HANDLING (persistent conversation)
    # ------------------------------------------------------------------
    # get_or_create_session() either retrieves an existing session object
    # or creates a fresh one. This allows RAG + agents to maintain memory
    # across multiple turns.
    session = get_or_create_session(rag.agent_session_id)
    agent_session_id = session.id

    logger.info(
        f"[RAG] agent_session_id={agent_session_id}  "
        f"turns={session.turns}  "
        f"created_at={session.created_at.isoformat()}  "
        f"last_access={session.last_access.isoformat()}"
    )

    # ------------------------------------------------------------------
    # 4) PROCESS UPLOADED FILES (optional)
    # ------------------------------------------------------------------
    # These files (typically PDFs, images, docs) become immediate RAG sources.
    # Files are stored ONLY for the duration of this session, inside:
    #   RAG_UPLOAD_ROOT / <session_id> / <filename>
    # They are *not* indexed system-wide.
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
                with open(dest_path, "wb") as f:
                    f.write(contents)

                logger.info(
                    f"[RAG] saved uploaded file for session {agent_session_id}: "
                    f"{dest_path}"
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

    # ------------------------------------------------------------------
    # 5) GET LIST OF FILES ALREADY SAVED FOR THIS SESSION
    # ------------------------------------------------------------------
    # We gather filenames only (not absolute paths); RouterAgent
    # can convert these into public URLs or ingest as file contents.
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

    # ------------------------------------------------------------------
    # 6) INVOKE THE MAIN ROUTER AGENT
    # ------------------------------------------------------------------
    # RouterAgent handles:
    #   • Intent classification
    #   • Selecting the correct agent (registration, general RAG, safety, etc.)
    #   • Running embedding retrieval
    #   • Running the LLM
    #   • Returning structured results + metadata
    router_agent = RouterAgent()

    try:
        response_payload = await router_agent.run(
            rag=rag,
            session=session,
            session_files=session_files,
        )
    except ValueError as e:
        # RouterAgent raise ValueError for “bad input”
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        # RouterAgent raise RuntimeError for upstream embedding/LLM issues
        raise HTTPException(status_code=502, detail=str(e))

    # ------------------------------------------------------------------
    # 7) LOG FINAL RESPONSE (for debugging & observability)
    # ------------------------------------------------------------------
    try:
        logger.info(
            "[RAG] response to client: %s",
            json.dumps(response_payload, ensure_ascii=False)[:4000],
        )
    except Exception as e:
        logger.warning(f"[RAG] failed to json.dumps response_payload: {e}")

    # ------------------------------------------------------------------
    # 8) RETURN JSON PAYLOAD TO CLIENT (ChatClient.tsx)
    # ------------------------------------------------------------------
    return response_payload
