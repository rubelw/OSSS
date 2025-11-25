# src/OSSS/ai/rag_router.py
from __future__ import annotations

from typing import Optional, List
import logging
import shutil
import json
import shutil

from pathlib import Path
from datetime import datetime
from typing import List

from pydantic import BaseModel
import os


from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile, Query

from OSSS.ai.router_agent import RAGRequest, RouterAgent
from OSSS.ai.additional_index import INDEX_KINDS, get_docs
from OSSS.ai.session_store import (
    get_or_create_session,
    prune_expired_sessions,
)


# Try to reuse your real settings; if not, fall back like the gateway does

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

class UploadedFileInfo(BaseModel):
    name: str
    path: str          # full local path (for debugging)
    size_bytes: int
    modified_at: datetime


class SessionFilesResponse(BaseModel):
    agent_session_id: str
    files: List[UploadedFileInfo]

class UploadedFileWithSession(BaseModel):
    agent_session_id: str
    filename: str
    path: str
    size_bytes: int
    modified_at: datetime

class UploadedFileInfo(BaseModel):
    filename: str
    path: str
    size_bytes: int
    modified_at: datetime

# ======================================================================
# DEBUG ENDPOINT — VIEW SOME INDEX CHUNKS
# ======================================================================
@router.get("/chat/files", response_model=SessionFilesResponse)
async def list_uploaded_files(
    agent_session_id: str = Query(..., description="RAG agent_session_id to inspect"),
) -> SessionFilesResponse:
    """
    List files uploaded for a given agent_session_id.

    Files are read from /tmp/osss_rag_uploads/<agent_session_id>/.
    """
    session_dir = RAG_UPLOAD_ROOT / agent_session_id

    if not session_dir.exists() or not session_dir.is_dir():
        # No files uploaded for this session (or bad id) – return empty set
        return SessionFilesResponse(agent_session_id=agent_session_id, files=[])

    files: List[UploadedFileInfo] = []
    for p in sorted(session_dir.iterdir()):
        if not p.is_file():
            continue
        st = p.stat()
        files.append(
            UploadedFileInfo(
                name=p.name,
                path=str(p),  # local path; your front-end / tools can transform this to a URL
                size_bytes=st.st_size,
                modified_at=datetime.fromtimestamp(st.st_mtime),
            )
        )

    return SessionFilesResponse(agent_session_id=agent_session_id, files=files)

@router.get("/chat/files/all", response_model=List[UploadedFileWithSession])
async def list_all_uploaded_files() -> List[UploadedFileWithSession]:
    """
    List all uploaded files under UPLOAD_ROOT across all agent_session_ids.

    Directory layout:
        UPLOAD_ROOT / <agent_session_id> / <filename>
    """
    results: List[UploadedFileWithSession] = []

    if not RAG_UPLOAD_ROOT.exists() or not RAG_UPLOAD_ROOT.is_dir():
        logger.info(
            "[RAG] list_all_uploaded_files: upload root %s does not exist or is not a dir",
            RAG_UPLOAD_ROOT,
        )
        return results

    for session_dir in RAG_UPLOAD_ROOT.iterdir():
        if not session_dir.is_dir():
            continue

        agent_session_id = session_dir.name

        for p in session_dir.iterdir():
            if not p.is_file():
                continue

            stat = p.stat()
            results.append(
                UploadedFileWithSession(
                    agent_session_id=agent_session_id,
                    filename=p.name,
                    path=str(p),
                    size_bytes=stat.st_size,
                    modified_at=datetime.fromtimestamp(stat.st_mtime),
                )
            )

    logger.info(
        "[RAG] list_all_uploaded_files: returning %d files from %s",
        len(results),
        RAG_UPLOAD_ROOT,
    )
    return results


@router.delete("/chat/files")
async def delete_session_files(
    agent_session_id: str = Query(..., description="RAG agent_session_id whose files to delete"),
) -> dict:
    """
    Delete all uploaded files for a single RAG agent_session_id.

    This removes the session-specific directory:
        UPLOAD_ROOT / agent_session_id
    """
    session_dir = RAG_UPLOAD_ROOT / agent_session_id

    if not session_dir.exists():
        # Nothing to delete, but treat as success
        logger.info(
            "[RAG] delete_session_files: no session dir found for %s at %s",
            agent_session_id,
            session_dir,
        )
        return {
            "status": "ok",
            "message": f"No upload directory found for session {agent_session_id}",
            "agent_session_id": agent_session_id,
            "deleted": False,
            "deleted_entries": 0,
        }

    if not session_dir.is_dir():
        logger.warning(
            "[RAG] delete_session_files: path for %s is not a directory: %s",
            agent_session_id,
            session_dir,
        )
        raise HTTPException(
            status_code=400,
            detail=f"Upload path for {agent_session_id} is not a directory",
        )

    deleted_entries = 0
    for child in session_dir.iterdir():
        try:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
            deleted_entries += 1
        except Exception as exc:
            logger.exception(
                "[RAG] delete_session_files: failed to delete %s for session %s: %s",
                child,
                agent_session_id,
                exc,
            )

    # Optionally remove the now-empty session dir itself
    try:
        session_dir.rmdir()
    except OSError:
        # Not empty or some other issue — non-fatal
        logger.debug(
            "[RAG] delete_session_files: could not rmdir %s (may not be empty)",
            session_dir,
        )

    logger.info(
        "[RAG] delete_session_files: cleared %d entries for session %s under %s",
        deleted_entries,
        agent_session_id,
        session_dir,
    )

    return {
        "status": "ok",
        "message": f"Deleted uploaded files for session {agent_session_id}",
        "agent_session_id": agent_session_id,
        "deleted": deleted_entries > 0,
        "deleted_entries": deleted_entries,
    }

@router.delete("/chat/files/clear-all")
async def clear_all_uploaded_files() -> dict:
    """
    Danger zone: delete ALL uploaded RAG temp files for ALL sessions.

    This recursively removes everything under UPLOAD_ROOT
    (default: /tmp/osss_rag_uploads).
    """
    if not RAG_UPLOAD_ROOT.exists():
        # Nothing to clear
        return {
            "status": "ok",
            "message": f"No upload directory to clear at {RAG_UPLOAD_ROOT}",
            "deleted_root": False,
            "deleted_entries": 0,
        }

    deleted_entries = 0
    for child in RAG_UPLOAD_ROOT.iterdir():
        deleted_entries += 1
    shutil.rmtree(RAG_UPLOAD_ROOT)
    return {
        "status": "ok",
        "message": f"Removed upload root directory {RAG_UPLOAD_ROOT}",
        "deleted_root": True,
        "deleted_entries": deleted_entries,
    }

    return {
        "status": "ok",
        "message": f"Cleared all uploaded files under {UPLOAD_ROOT}",
        "deleted_root": False,
        "deleted_entries": deleted_entries,
    }


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
    """

    # ------------------------------------------------------------------
    # 1) Deserialize JSON payload into RAGRequest
    #    (now via dict so we can preserve extra fields like subagent_session_id)
    # ------------------------------------------------------------------
    try:
        raw_payload = json.loads(payload)
    except Exception as e:
        raise HTTPException(400, f"Invalid rag JSON (not JSON): {e}")

    try:
        rag = RAGRequest.model_validate(raw_payload)
    except Exception as e:
        raise HTTPException(400, f"Invalid rag JSON: {e}")

    # Extract subagent_session_id from the raw payload (what the client sent)
    raw_subagent_session_id = raw_payload.get("subagent_session_id")
    logger.info(
        "[RAG] incoming subagent_session_id=%r for agent_session_id=%r",
        raw_subagent_session_id,
        raw_payload.get("agent_session_id"),
    )

    # Force-attach it onto the RAGRequest model so RouterAgent can see it
    # even if RAGRequest doesn't formally declare this field.
    try:
        setattr(rag, "subagent_session_id", raw_subagent_session_id)
    except Exception as e:
        logger.warning(
            "[RAG] failed to set rag.subagent_session_id=%r: %s",
            raw_subagent_session_id,
            e,
        )

    # ------------------------------------------------------------------
    # 2) SESSION EXPIRATION & CLEANUP
    # ------------------------------------------------------------------
    expired_ids = prune_expired_sessions()
    if expired_ids:
        logger.info(f"[RAG] pruned {len(expired_ids)} expired sessions")

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
    router_agent = RouterAgent()

    try:
        response_payload = await router_agent.run(
            rag=rag,
            session=session,
            session_files=session_files,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
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
