# OSSS/ai/agents/student/upload_agent.py

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Optional

from OSSS.ai.agents import register_agent
from OSSS.ai.agents.base import AgentContext, AgentResult

from .registration_state_store import RegistrationStateStore

logger = logging.getLogger("OSSS.ai.agents.registration.upload")


def _get_base_session_id(ctx: AgentContext) -> str:
    """
    Prefer the 'base' / top-level agent session id if available,
    fall back to subagent_session_id (which we know exists).
    """
    return (
        getattr(ctx, "agent_session_id", None)
        or getattr(ctx, "session_id", None)
        or ctx.subagent_session_id
    )


async def _store_file_for_session(
    ctx: AgentContext,
    state_store: RegistrationStateStore,
    slot_name: str = "proof_of_residency_upload",
) -> Optional[str]:
    """
    Core logic: take the first uploaded file from ctx, write it to
    /tmp/osss_uploads/<base_session_id>/, and update the registration
    session state (by subagent_session_id) with the stored path.
    """
    # ⚠️ Adjust this to your real file interface:
    # e.g. ctx.files[0].path, ctx.files[0].content, etc.
    if not getattr(ctx, "files", None):
        logger.warning("[upload] No files present on ctx.files")
        return None

    file_obj = ctx.files[0]

    # These attribute names (filename, path, content) are examples —
    # adjust based on your actual AgentContext file representation.
    original_name = getattr(file_obj, "filename", "uploaded_file")
    tmp_path = getattr(file_obj, "path", None)
    content_bytes = getattr(file_obj, "content", None)

    if tmp_path is None and content_bytes is None:
        logger.error("[upload] File object has no 'path' or 'content'; cannot persist.")
        return None

    base_session_id = _get_base_session_id(ctx)
    base_dir = Path("/tmp/osss_uploads") / base_session_id / "proof_of_residency"
    base_dir.mkdir(parents=True, exist_ok=True)

    ext = os.path.splitext(original_name)[1]
    stored_name = f"{uuid.uuid4().hex}{ext or ''}"
    dest_path = base_dir / stored_name

    if tmp_path is not None:
        # File already on disk; copy/move from tmp path.
        from shutil import copyfile

        copyfile(tmp_path, dest_path)
    else:
        # Write from raw bytes
        with open(dest_path, "wb") as f:
            f.write(content_bytes)

    stored_path_str = str(dest_path)
    logger.info(
        "[upload] Stored proof_of_residency file for base_session_id=%s at %s",
        base_session_id,
        stored_path_str,
    )

    # --- Update the registration state for THIS registration session ---
    registration_session_id = ctx.subagent_session_id
    state = await state_store.get(registration_session_id)

    if state is None:
        from .registration_state import RegistrationSessionState

        state = RegistrationSessionState(
            session_id=registration_session_id,
            session_mode="new",
        )

    # Make sure the state has this attribute (you'll add it to the dataclass)
    setattr(state, slot_name, stored_path_str)
    await state_store.save(state)

    return stored_path_str


@register_agent("upload_proof_of_residency")
class UploadProofOfResidencyAgent:
    """
    Utility agent that takes an uploaded file from the user, stores it in temporary
    storage keyed by the *base agent session id*, and updates the registration
    session state slot 'proof_of_residency_upload'.
    """

    def __init__(self) -> None:
        # You may want a singleton/persistent store here instead of a new one.
        self.state_store = RegistrationStateStore()

    async def __call__(self, ctx: AgentContext) -> AgentResult:
        stored_path = await _store_file_for_session(
            ctx,
            state_store=self.state_store,
            slot_name="proof_of_residency_upload",
        )

        if stored_path is None:
            return AgentResult(
                answer_text=(
                    "I didn't receive a valid file. "
                    "Please upload a **Proof of Residency** document and try again."
                ),
                inner_data={"upload_ok": False},
            )

        return AgentResult(
            answer_text=(
                "Thanks — I’ve received your **Proof of Residency** document.\n\n"
                "You can continue with the registration now."
            ),
            inner_data={
                "upload_ok": True,
                "proof_of_residency_upload": stored_path,
            },
        )
