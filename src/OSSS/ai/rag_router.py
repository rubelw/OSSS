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


# Try to reuse your real settings; if not, fall back like the gateway does
try:
    from OSSS.config import settings as _settings  # type: ignore

    settings = _settings
except Exception:  # fallback, same as in your ai_gateway
    class _Settings:
        RAG_UPLOAD_ROOT: str = "/tmp/osss_rag_uploads"

    settings = _Settings()  # type: ignore

logger = logging.getLogger("OSSS.ai.rag_router")

RAG_UPLOAD_ROOT = Path(getattr(settings, "RAG_UPLOAD_ROOT", "/tmp/osss_rag_uploads"))

router = APIRouter(
    prefix="/ai",
    tags=["ai-rag"],
)

# ---- auth guard: reuse your real auth if available ----
try:
    from OSSS.auth.deps import require_user  # type: ignore

    def _auth_guard(user=Depends(require_user)):
        return user

except Exception:
    def _auth_guard():
        return None


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
    files: list[UploadFile] | None = File(default=None),
    user=Depends(_auth_guard),  # noqa: F841  - reserved for later user-based logic
):
    """
    FastAPI wrapper around the RouterAgent.

    Responsibilities here are ONLY:
      1) Parse RAGRequest from the incoming form field.
      2) Manage session lifecycle + temp file storage.
      3) Call RouterAgent.run(...) and return its payload.
    """

    # Convert raw JSON string from form field into pydantic model
    try:
        rag = RAGRequest.model_validate_json(payload)
    except Exception as e:
        raise HTTPException(400, f"Invalid rag JSON: {e}")

    # --- Session pruning + temp-file cleanup -------------------------
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

    # Handle file processing: store under a per-session temp directory
    if files:
        session_dir = RAG_UPLOAD_ROOT / agent_session_id
        try:
            session_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(
                f"[RAG] failed to create session upload dir {session_dir}: {e}"
            )
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

    # ---- Call the RouterAgent orchestrator ---------------------------
    router_agent = RouterAgent()
    try:
        response_payload = await router_agent.run(
            rag=rag,
            session=session,
            session_files=session_files,
        )
    except ValueError as e:
        # For simple validation issues inside RouterAgent (e.g. no user msg)
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        # Upstream LLM/embedding errors
        raise HTTPException(status_code=502, detail=str(e))

    # 🔍 Log the final response going back to ChatClient.tsx
    try:
        logger.info(
            "[RAG] response to client: %s",
            json.dumps(response_payload, ensure_ascii=False)[:4000],
        )
    except Exception as e:
        logger.warning(f"[RAG] failed to json.dumps response_payload: {e}")

    return response_payload
