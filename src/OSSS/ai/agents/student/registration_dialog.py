from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from typing import List, Literal, Optional, Tuple
from datetime import date

from OSSS.ai.agents.base import AgentContext

from .registration_state import RegistrationSessionState
from .registration_state_store import RegistrationStateStore

logger = logging.getLogger("OSSS.ai.agents.registration.dialog")

# ----------------------------------------------------------------------
# Trigger helpers (pure / testable)
# ----------------------------------------------------------------------


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

    # Match patterns like "2024-25", "2025/26", etc.
    m = re.search(r"(20[2-9][0-9])[-/](?:20[2-9][0-9]|[0-9]{2})", q_norm)
    if m:
        logger.info("[extract_school_year] matched school_year=%s", m.group(0))
        return m.group(0)

    logger.debug("[extract_school_year] no match found.")
    return None


# ----------------------------------------------------------------------
# Helpers for numeric menus
# ----------------------------------------------------------------------

SessionMode = Literal["new", "continue"]


def parse_continue_or_new_choice(query: str) -> Optional[SessionMode]:
    """
    Parse numeric answer for NEW vs CONTINUE registration when we show:

      1. Continue this registration
      2. Start a new registration

    Accepts:
      - "1", "1.", "1)" => "continue"
      - "2", "2.", "2)" => "new"
    """
    q = (query or "").strip().lower()
    if not q:
        return None

    normalized = q
    if normalized.endswith((".", ")")):
        normalized = normalized[:-1].strip()

    if normalized == "1":
        return "continue"
    if normalized == "2":
        return "new"

    return None


def get_default_school_year_options() -> List[str]:
    """
    Build a small list of upcoming school-year strings like:
      ["2025-26", "2026-27", "2027-28"]
    """
    today = date.today()
    start_year = max(today.year, 2024)

    options: List[str] = []
    for i in range(3):
        y = start_year + i
        next_y = y + 1
        # e.g. 2025-26
        options.append(f"{y}-{str(next_y % 100).zfill(2)}")

    return options


def parse_school_year_choice(query: str, options: List[str]) -> Optional[str]:
    """
    Parse numeric or textual answer for school_year after we've shown options.

    Accepts:
      - "1", "1.", "1)" => options[0]
      - "2", "2.", "2)" => options[1]
      - "3", ...         => options[2]
      - or a textual year like "2025-26" that we detect with extract_school_year.
    """
    q = (query or "").strip().lower()
    if not q:
        return None

    normalized = q
    if normalized.endswith((".", ")")):
        normalized = normalized[:-1].strip()

    # Numeric choice
    if normalized.isdigit():
        idx = int(normalized) - 1
        if 0 <= idx < len(options):
            return options[idx]

    # Textual / explicit year
    detected = extract_school_year(query)
    if detected:
        # If it's in the menu, return as-is; otherwise accept the detected value anyway.
        if detected in options:
            return detected
        return detected

    return None


# ----------------------------------------------------------------------
# Session mode / dialog orchestration
# ----------------------------------------------------------------------


def decide_session_mode(
    ctx: AgentContext,
) -> Tuple[Optional[SessionMode], Optional[str]]:
    """
    Decide whether this turn is a NEW or CONTINUE registration interaction,
    and which session_id to use.

    This is about the *dialog session* (new vs continue), NOT about
    whether the student themselves is "new" vs "existing".
    """
    existing_id = ctx.subagent_session_id
    logger.debug(
        "[decide_session_mode] subagent_session_id=%r query=%r",
        existing_id,
        ctx.query,
    )

    # No existing dialog session: always start a NEW session_id.
    if not existing_id:
        new_id = str(uuid.uuid4())
        logger.info(
            "[decide_session_mode] No existing session; starting NEW session %s",
            new_id,
        )
        return "new", new_id

    # We *have* an existing dialog session.

    # First, see if the user answered with a numeric choice (1 or 2).
    numeric_choice = parse_continue_or_new_choice(ctx.query)
    if numeric_choice == "continue":
        logger.info(
            "[decide_session_mode] Numeric choice=1 => CONTINUE existing session %s",
            existing_id,
        )
        return "continue", existing_id
    if numeric_choice == "new":
        new_id = str(uuid.uuid4())
        logger.info(
            "[decide_session_mode] Numeric choice=2 => NEW session %s (previous=%s)",
            new_id,
            existing_id,
        )
        return "new", new_id

    # Otherwise, fall back to text triggers (continue / start new).
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

    # Ambiguous: we keep the existing_id but signal that we need a clarification
    logger.info(
        "[decide_session_mode] Ambiguous new/continue for existing_session=%s; "
        "will prompt user.",
        existing_id,
    )
    return None, existing_id


# ----------------------------------------------------------------------
# DialogStepResult — what the dialog engine decided
# ----------------------------------------------------------------------


@dataclass
class DialogStepResult:
    """
    PURE result object: no side-effects, just "what should we say/do?"
    """

    prompt_answer_text: Optional[str] = None
    prompt_phase: Optional[str] = None
    prompt_status: Optional[str] = None
    prompt_reason: Optional[str] = None

    proceed: bool = False
    session_state: Optional[RegistrationSessionState] = None


# ----------------------------------------------------------------------
# Pure helpers for slot-filling
# ----------------------------------------------------------------------


def infer_student_type_from_query(
    query: str,
    current: Optional[str],
) -> Optional[str]:
    """
    Pure helper: infer student_type ('new'/'existing') from the query,
    given the current stored value.
    """
    if current is not None:
        return current

    if wants_new_student(query):
        return "new"
    if wants_existing_student(query):
        return "existing"
    return None


def parse_student_type_choice(
    query: str,
    current: Optional[str],
) -> Optional[str]:
    """
    Parse numeric or textual answer for student_type after we've prompted.

    Accepts:
      - "1", "1.", "1)" => "new"
      - "2", "2.", "2)" => "existing"
      - or falls back to text-based inference.
    """
    if current is not None:
        return current

    q = (query or "").strip().lower()
    if not q:
        return None

    normalized = q
    if normalized.endswith((".", ")")):
        normalized = normalized[:-1].strip()

    if normalized == "1":
        return "new"
    if normalized == "2":
        return "existing"

    # Fallback: look for textual cues ("new student", "existing student")
    return infer_student_type_from_query(query, None)


def infer_school_year_from_query(
    query: str,
    current: Optional[str],
) -> Optional[str]:
    """
    Pure helper: infer school_year from the query,
    given the current stored value.
    """
    if current is not None:
        return current
    return extract_school_year(query)


def dialog_for_continue_mode_pure(
    ctx: AgentContext,
    session_state: RegistrationSessionState,
) -> Tuple[DialogStepResult, RegistrationSessionState]:
    """
    Pure logic for CONTINUE mode.

    - Best-effort inference of student_type and school_year.
    - If we actually have usable state, we proceed.
    - If we have *no* meaningful state yet (fresh session), we fall back
      to prompting, exactly like NEW mode, instead of calling the service
      with empty fields.
    """
    logger.debug(
        "[dialog_for_continue_mode_pure] CONTINUE for session=%s",
        session_state.session_id,
    )

    st_before = session_state.student_type
    sy_before = session_state.school_year

    st = infer_student_type_from_query(ctx.query, session_state.student_type)
    sy = infer_school_year_from_query(ctx.query, session_state.school_year)

    session_state.student_type = st
    session_state.school_year = sy

    logger.info(
        "[dialog_for_continue_mode_pure] inferred student_type=%r school_year=%r (before: st=%r sy=%r)",
        st,
        sy,
        st_before,
        sy_before,
    )

    # Treat a state that only has internal flags (like student_type_prompted /
    # school_year_prompted) as "empty" so we reuse NEW-mode prompting.
    inner = session_state.inner_data or {}
    meaningful_inner = {
        k: v
        for k, v in inner.items()
        if k not in ("student_type_prompted", "school_year_prompted")
    }

    is_effectively_empty = (
        session_state.student_type is None
        and session_state.school_year is None
        and session_state.parent_first_name is None
        and session_state.parent_last_name is None
        and session_state.parent_email is None
        and not meaningful_inner
    )

    if is_effectively_empty:
        logger.info(
            "[dialog_for_continue_mode_pure] State is effectively empty for CONTINUE; "
            "falling back to NEW-mode prompting for session=%s",
            session_state.session_id,
        )
        # Reuse NEW-mode logic to start prompting, but keep the same session_state.
        result, updated_state = dialog_for_new_mode_pure(ctx, session_state)
        return result, updated_state

    # Otherwise, we have at least some useful state; best-effort proceed.
    result = DialogStepResult(
        proceed=True,
        session_state=session_state,
    )
    return result, session_state


def dialog_for_new_mode_pure(
    ctx: AgentContext,
    session_state: RegistrationSessionState,
) -> Tuple[DialogStepResult, RegistrationSessionState]:
    """
    Pure logic for NEW mode (slot-filling student_type + school_year).

    REQUIREMENT:
    - Always explicitly prompt for NEW vs EXISTING at least once.
    - After the prompt, user can answer with a number (1 / 2).
    - For school-year, allow direct year or numeric choice from a menu (1 / 2 / 3).
    """
    logger.debug(
        "[dialog_for_new_mode_pure] NEW mode for session=%s",
        session_state.session_id,
    )

    # Ensure inner_data exists
    inner = session_state.inner_data or {}
    already_prompted_student_type = bool(inner.get("student_type_prompted", False))
    school_year_prompted = bool(inner.get("school_year_prompted", False))

    st = session_state.student_type
    sy = session_state.school_year

    # ---- 1) Ensure we ALWAYS explicitly ask once for new vs existing ----
    if st is None and not already_prompted_student_type:
        inner["student_type_prompted"] = True
        session_state.inner_data = inner

        prompt = (
            "Before we begin the registration process, please choose one option:\n\n"
            "1. **NEW student** (has not attended DC-G Schools before)\n"
            "2. **EXISTING student** (previously enrolled at DC-G)\n\n"
            "Reply with the **number** of your choice: 1 or 2."
        )
        logger.info(
            "[dialog_for_new_mode_pure] First-time student_type prompt for NEW "
            "session=%s; asking user new vs existing (numeric).",
            session_state.session_id,
        )
        result = DialogStepResult(
            prompt_answer_text=prompt,
            prompt_phase="prompt_for_student_type",
            prompt_status="needs_student_type",
            prompt_reason="prompt_for_student_type",
            proceed=False,
            session_state=session_state,
        )
        return result, session_state

    # ---- 2) We've already prompted; now interpret their reply (number or text) ----
    if st is None and already_prompted_student_type:
        inferred = parse_student_type_choice(ctx.query, None)
        if inferred is None:
            # Couldn't parse their answer; re-prompt with explicit numeric guidance.
            prompt = (
                "I wasn't able to tell if you meant a **NEW** or "
                "**EXISTING** student.\n\n"
                "Please reply with the **number** of your choice:\n"
                "1. NEW student\n"
                "2. EXISTING student"
            )
            logger.info(
                "[dialog_for_new_mode_pure] Could not infer student_type from "
                "reply after prompt; re-asking for session=%s",
                session_state.session_id,
            )
            result = DialogStepResult(
                prompt_answer_text=prompt,
                prompt_phase="prompt_for_student_type",
                prompt_status="needs_student_type",
                prompt_reason="prompt_for_student_type_retry",
                proceed=False,
                session_state=session_state,
            )
            return result, session_state

        st = inferred
        session_state.student_type = st
        logger.info(
            "[dialog_for_new_mode_pure] Resolved student_type=%r for session=%s "
            "from reply after explicit numeric/text prompt.",
            st,
            session_state.session_id,
        )

    # ---- 3) school_year for NEW students (with numeric menu support) ----
    if st == "new" and sy is None:
        # First: if we have NOT yet prompted for school year, try to parse a direct year
        if not school_year_prompted:
            direct_sy = infer_school_year_from_query(ctx.query, None)
            if direct_sy is not None:
                sy = direct_sy
                session_state.school_year = sy
                logger.info(
                    "[dialog_for_new_mode_pure] Directly inferred school_year=%r for "
                    "NEW session=%s from user text.",
                    sy,
                    session_state.session_id,
                )
            else:
                # No direct year; show numeric options.
                options = get_default_school_year_options()
                inner["school_year_prompted"] = True
                session_state.inner_data = inner

                # Build menu text
                menu_lines = []
                for idx, opt in enumerate(options, start=1):
                    menu_lines.append(f"{idx}. **{opt}**")

                menu_text = "\n".join(menu_lines)

                prompt = (
                    "Great — you're registering a **new student**.\n\n"
                    "**What school year are you registering for?**\n\n"
                    f"{menu_text}\n\n"
                    "Reply with the **number** of your choice (e.g., 1), "
                    "or type the school year (e.g., \"2025-26\")."
                )
                logger.info(
                    "[dialog_for_new_mode_pure] NEW student but missing school_year "
                    "for session=%s; prompting user with numeric menu.",
                    session_state.session_id,
                )
                result = DialogStepResult(
                    prompt_answer_text=prompt,
                    prompt_phase="prompt_for_school_year",
                    prompt_status="needs_school_year",
                    prompt_reason="prompt_for_school_year",
                    proceed=False,
                    session_state=session_state,
                )
                return result, session_state

        # If we still don't have sy, and we've already prompted, parse numeric/text response
        if sy is None and school_year_prompted:
            options = get_default_school_year_options()
            chosen = parse_school_year_choice(ctx.query, options)
            if chosen is None:
                # Re-prompt with same options
                menu_lines = []
                for idx, opt in enumerate(options, start=1):
                    menu_lines.append(f"{idx}. **{opt}**")
                menu_text = "\n".join(menu_lines)

                prompt = (
                    "I wasn't able to tell which **school year** you selected.\n\n"
                    "Please reply with the **number** of your choice, or type the "
                    "school year directly. For example:\n\n"
                    f"{menu_text}\n\n"
                    "Examples of valid replies:\n"
                    "- `1`\n"
                    "- `2025-26`"
                )
                logger.info(
                    "[dialog_for_new_mode_pure] Could not infer school_year after "
                    "menu prompt; re-asking for session=%s",
                    session_state.session_id,
                )
                result = DialogStepResult(
                    prompt_answer_text=prompt,
                    prompt_phase="prompt_for_school_year",
                    prompt_status="needs_school_year",
                    prompt_reason="prompt_for_school_year_retry",
                    proceed=False,
                    session_state=session_state,
                )
                return result, session_state

            sy = chosen
            session_state.school_year = sy
            logger.info(
                "[dialog_for_new_mode_pure] Resolved school_year=%r for NEW session=%s "
                "from numeric/text reply.",
                sy,
                session_state.session_id,
            )

    # ---- 4) Update state (we have at least student_type, maybe school_year) ----
    session_state.student_type = st
    session_state.school_year = sy
    session_state.inner_data = inner

    logger.info(
        "[dialog_for_new_mode_pure] resolved student_type=%r school_year=%r",
        st,
        sy,
    )

    # ---- 5) NEW + known school_year -> prompt for parent info ----
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
            "[dialog_for_new_mode_pure] Prompting for parent info for NEW session=%s",
            session_state.session_id,
        )
        result = DialogStepResult(
            prompt_answer_text=prompt_parent,
            prompt_phase="prompt_for_parent_info",
            prompt_status="needs_parent_info",
            prompt_reason="prompt_for_parent_info",
            proceed=False,
            session_state=session_state,
        )
        return result, session_state

    # ---- 6) Otherwise: proceed to service (e.g. existing student path) ----
    result = DialogStepResult(
        proceed=True,
        session_state=session_state,
    )
    return result, session_state


def dialog_for_ambiguous_mode_pure(
    ctx: AgentContext,
    session_state: RegistrationSessionState,
) -> DialogStepResult:
    """
    Pure logic when session_mode is None but an existing session id is present.

    We now present numeric options:

      1. Continue this registration
      2. Start a new registration

    The numeric choice is interpreted in decide_session_mode via
    parse_continue_or_new_choice().
    """
    prompt = (
        f"You already have a registration in progress.\n\n"
        f"Existing registration session ID: **{ctx.subagent_session_id}**\n\n"
        "Please choose one option:\n\n"
        "1. **Continue** this registration\n"
        "2. **Start a new registration** for a different student\n\n"
        "Reply with the **number** of your choice: 1 or 2."
    )
    logger.info(
        "[dialog_for_ambiguous_mode_pure] Ambiguous session_mode with existing_session=%s; prompting user with numeric options.",
        ctx.subagent_session_id,
    )
    return DialogStepResult(
        prompt_answer_text=prompt,
        prompt_phase="prompt_for_continue_or_new",
        prompt_status="needs_choice",
        prompt_reason="prompt_for_continue_or_new",
        proceed=False,
        session_state=session_state,
    )


# ----------------------------------------------------------------------
# Async wrapper: uses pure functions + state store
# ----------------------------------------------------------------------


async def evaluate_dialog_slots(
    ctx: AgentContext,
    session_mode: Optional[SessionMode],
    session_state: RegistrationSessionState,
    state_store: RegistrationStateStore,
) -> DialogStepResult:
    """
    Orchestrator used by the agent.

    - Delegates to pure helpers (easy to unit-test).
    - Handles persistence via RegistrationStateStore.
    """
    # CONTINUE mode
    if session_mode == "continue":
        result, updated_state = dialog_for_continue_mode_pure(ctx, session_state)
        # In CONTINUE mode we always persist best-effort hints
        await state_store.save(updated_state)
        return result

    # NEW mode
    if session_mode == "new":
        result, updated_state = dialog_for_new_mode_pure(ctx, session_state)

        # Always persist updated_state, even when prompting, so that flags
        # like inner_data['student_type_prompted'] / ['school_year_prompted']
        # survive to the next turn.
        await state_store.save(updated_state)

        return result

    # Ambiguous mode (session_mode is None) with existing session
    if session_mode is None and ctx.subagent_session_id:
        result = dialog_for_ambiguous_mode_pure(ctx, session_state)
        # No persistence here; we're just asking for a choice.
        return result

    # Fallback: session_mode is None and no existing session; just proceed
    logger.debug(
        "[evaluate_dialog_slots] Fallback path; proceeding with session=%s",
        session_state.session_id,
    )
    return DialogStepResult(proceed=True, session_state=session_state)
