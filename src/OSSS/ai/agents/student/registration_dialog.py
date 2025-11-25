from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass  # NOTE: no more `replace`
from typing import List, Literal, Optional, Tuple

from OSSS.ai.agents.base import AgentContext

from .registration_state import RegistrationSessionState
from .registration_state_store import RegistrationStateStore

# Dedicated logger for dialog-policy decisions and slot-filling.
logger = logging.getLogger("OSSS.ai.agents.registration.dialog")


# ======================================================================
# Trigger helpers
# ======================================================================
def _has_trigger(query: str, triggers: List[str]) -> bool:
    q = (query or "").lower()
    hit = any(t in q for t in triggers)
    logger.debug(
        "[_has_trigger] query=%r triggers=%r -> hit=%s",
        q,
        triggers,
        hit,
    )
    return hit


def wants_new_registration(query: str) -> bool:
    result = _has_trigger(
        query,
        [
            "start a new registration",
            "start another registration",
            "another registration",
            "new registration",
            "register another student",
            "register a different student",
        ],
    )
    logger.debug("[wants_new_registration] query=%r -> %s", query, result)
    return result


def wants_continue_registration(query: str) -> bool:
    result = _has_trigger(
        query,
        [
            "continue",
            "resume",
            "pick up where we left off",
            "continue current registration",
            "resume registration",
            "same registration",
            "same student",
        ],
    )
    logger.debug("[wants_continue_registration] query=%r -> %s", query, result)
    return result


def wants_new_student(query: str) -> bool:
    result = _has_trigger(
        query,
        [
            "new student",
            "register a new student",
            "register new student",
            "brand new student",
        ],
    )
    logger.debug("[wants_new_student] query=%r -> %s", query, result)
    return result


def wants_existing_student(query: str) -> bool:
    result = _has_trigger(
        query,
        [
            "existing student",
            "previously enrolled",
            "returning student",
            "student who attended before",
            "attended dc-g in the past",
            "attended dc-g schools in the past",
        ],
    )
    logger.debug("[wants_existing_student] query=%r -> %s", query, result)
    return result


def extract_school_year(query: str) -> Optional[str]:
    if not query:
        logger.debug("[extract_school_year] no query; returning None.")
        return None

    q_norm = query.strip().replace("–", "-").replace("—", "-")
    logger.debug(
        "[extract_school_year] raw_query=%r normalized=%r",
        query,
        q_norm,
    )

    m = re.search(r"(20[2-9][0-9])[-/](?:20[2-9][0-9]|[0-9]{2})", q_norm)
    if m:
        logger.info("[extract_school_year] matched school_year=%s", m.group(0))
        return m.group(0)

    logger.debug("[extract_school_year] no match found.")
    return None


# ======================================================================
# Session mode / dialog orchestration
# ======================================================================

SessionMode = Literal["new", "continue"]


def decide_session_mode(
    ctx: AgentContext,
) -> Tuple[Optional[SessionMode], Optional[str]]:
    existing_id = ctx.subagent_session_id
    logger.debug(
        "[decide_session_mode] subagent_session_id=%r query=%r",
        existing_id,
        ctx.query,
    )

    if not existing_id:
        new_id = str(uuid.uuid4())
        logger.info(
            "[decide_session_mode] No existing session; starting NEW session %s",
            new_id,
        )
        return "new", new_id

    is_new = wants_new_registration(ctx.query)
    is_continue = wants_continue_registration(ctx.query)
    logger.info(
        "[decide_session_mode] existing_session=%s wants_new=%s wants_continue=%s",
        existing_id,
        is_new,
        is_continue,
    )

    if is_continue and not is_new:
        logger.info(
            "[decide_session_mode] User chose CONTINUE on existing session %s",
            existing_id,
        )
        return "continue", existing_id

    if is_new and not is_continue:
        new_id = str(uuid.uuid4())
        logger.info(
            "[decide_session_mode] User chose NEW; new_session=%s previous=%s",
            new_id,
            existing_id,
        )
        return "new", new_id

    logger.info(
        "[decide_session_mode] Ambiguous new/continue for existing_session=%s; "
        "will prompt user.",
        existing_id,
    )
    return None, existing_id


# ======================================================================
# DialogStepResult — what the dialog engine decided
# ======================================================================
@dataclass
class DialogStepResult:
    prompt_answer_text: Optional[str] = None
    prompt_phase: Optional[str] = None
    prompt_status: Optional[str] = None
    prompt_reason: Optional[str] = None

    proceed: bool = False
    session_state: Optional[RegistrationSessionState] = None


# ======================================================================
# Dialog policy: slot-filling for student_type and school_year
# ======================================================================
async def evaluate_dialog_slots(
    ctx: AgentContext,
    session_mode: Optional[SessionMode],
    session_state: RegistrationSessionState,
    state_store: RegistrationStateStore,
) -> DialogStepResult:
    """
    Decide whether to:
      - Prompt the user for more info, OR
      - Proceed to call the registration service.

    Uses RegistrationStateStore.get/save under the hood; the caller
    is responsible for passing the loaded session_state in.
    """

    # ------------------------------------------------------------------
    # CONTINUE mode: best-effort inference, never block
    # ------------------------------------------------------------------
    if session_mode == "continue":
        logger.debug(
            "[evaluate_dialog_slots] CONTINUE mode for session=%s",
            session_state.session_id,
        )
        st = session_state.student_type
        sy = session_state.school_year

        # Infer student_type if missing
        if not st:
            if wants_new_student(ctx.query):
                st = "new"
            elif wants_existing_student(ctx.query):
                st = "existing"

        # Infer school_year if missing
        if not sy:
            sy = extract_school_year(ctx.query)

        # Mutate the Pydantic model and persist
        session_state.student_type = st
        session_state.school_year = sy
        await state_store.save(session_state)

        logger.info(
            "[evaluate_dialog_slots] CONTINUE mode inferred student_type=%r school_year=%r",
            st,
            sy,
        )
        # Always proceed in CONTINUE mode
        return DialogStepResult(proceed=True, session_state=session_state)

    # ------------------------------------------------------------------
    # NEW mode: explicit slot-filling flow (student_type + school_year)
    # ------------------------------------------------------------------
    if session_mode == "new":
        logger.debug(
            "[evaluate_dialog_slots] NEW mode for session=%s",
            session_state.session_id,
        )
        st = session_state.student_type
        sy = session_state.school_year

        # 1) student_type (new vs existing)
        if st is None:
            if wants_new_student(ctx.query):
                st = "new"
            elif wants_existing_student(ctx.query):
                st = "existing"

        if st is None:
            prompt = (
                "Before we begin the registration process, please confirm:\n\n"
                "**Is this registration for a:**\n"
                "- **NEW student**, or\n"
                "- **EXISTING student** (previously enrolled)?\n\n"
                "Please reply with:\n"
                "- \"new student\"\n"
                "- \"existing student\""
            )
            logger.info(
                "[evaluate_dialog_slots] Missing student_type for NEW session=%s; prompting user.",
                session_state.session_id,
            )
            return DialogStepResult(
                prompt_answer_text=prompt,
                prompt_phase="prompt_for_student_type",
                prompt_status="needs_student_type",
                prompt_reason="prompt_for_student_type",
            )

        # 2) For NEW students, require school year
        if st == "new" and sy is None:
            sy = extract_school_year(ctx.query)
            if sy is None:
                prompt = (
                    "Great — you're registering a **new student**.\n\n"
                    "**What school year are you registering for?**\n"
                    "For example:\n"
                    "- \"2024-25\"\n"
                    "- \"2025-26\"\n"
                    "- \"2026-27\""
                )
                logger.info(
                    "[evaluate_dialog_slots] NEW student but missing school_year for session=%s; prompting user.",
                    session_state.session_id,
                )
                # We *don't* persist partial state here (same behavior as before)
                return DialogStepResult(
                    prompt_answer_text=prompt,
                    prompt_phase="prompt_for_school_year",
                    prompt_status="needs_school_year",
                    prompt_reason="prompt_for_school_year",
                )

        # 3) Persist updated state (we have at least student_type, maybe school_year)
        session_state.student_type = st
        session_state.school_year = sy
        await state_store.save(session_state)

        logger.info(
            "[evaluate_dialog_slots] NEW mode resolved student_type=%r school_year=%r",
            st,
            sy,
        )

        # 4) For NEW student with known school_year, prompt for parent info
        if st == "new" and sy:
            prompt_parent = (
                "Please complete the information below to begin the registration process.\n\n"
                f"Registration Year\n{sy}\n\n"
                "Parent/Guardian First Name\n"
                "Parent/Guardian Last Name\n"
                "Parent/Guardian Email Address\n"
                "Verify Email Address\n"
                "Has any student you are registering attended DC-G Schools in the past?"
            )
            logger.info(
                "[evaluate_dialog_slots] Prompting for parent info for NEW session=%s",
                session_state.session_id,
            )
            return DialogStepResult(
                prompt_answer_text=prompt_parent,
                prompt_phase="prompt_for_parent_info",
                prompt_status="needs_parent_info",
                prompt_reason="prompt_for_parent_info",
            )

        # 5) Otherwise, proceed to service (e.g., EXISTING student)
        return DialogStepResult(proceed=True, session_state=session_state)

    # ------------------------------------------------------------------
    # Ambiguous mode (session_mode is None) with existing session
    # ------------------------------------------------------------------
    if session_mode is None and ctx.subagent_session_id:
        prompt = (
            f"You already have a registration in progress.\n\n"
            f"Existing registration session ID: **{ctx.subagent_session_id}**\n\n"
            "Would you like to:\n"
            "- **Continue** this registration, or\n"
            "- **Start a new registration** for a different student?\n\n"
            "Please reply with one of these phrases:\n"
            "- \"continue current registration\"\n"
            "- \"start a new registration\""
        )
        logger.info(
            "[evaluate_dialog_slots] Ambiguous session_mode with existing_session=%s; prompting user.",
            ctx.subagent_session_id,
        )
        return DialogStepResult(
            prompt_answer_text=prompt,
            prompt_phase="prompt_for_continue_or_new",
            prompt_status="needs_choice",
            prompt_reason="prompt_for_continue_or_new",
        )

    # ------------------------------------------------------------------
    # Fallback: session_mode is None and no existing session; just proceed
    # ------------------------------------------------------------------
    logger.debug(
        "[evaluate_dialog_slots] Fallback path; proceeding with session=%s",
        session_state.session_id,
    )
    return DialogStepResult(proceed=True, session_state=session_state)
