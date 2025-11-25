from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, replace
from typing import List, Literal, Optional, Tuple

from OSSS.ai.agents.base import AgentContext

from .registration_state import RegistrationSessionState, RegistrationStateStore

# Dedicated logger for dialog-policy decisions and slot-filling.
# All "thinking" about what to ask next or how to interpret the user's
# message should show up here, not in the agent or HTTP client.
logger = logging.getLogger("OSSS.ai.agents.registration.dialog")


# ======================================================================
# Trigger helpers
# ======================================================================
def _has_trigger(query: str, triggers: List[str]) -> bool:
    """
    Return True if any of the provided trigger phrases appear in the query.

    Parameters
    ----------
    query : str
        The user query or message text.
    triggers : List[str]
        A list of substrings to look for in the lowercased query.

    Notes
    -----
    - This helper treats the query as a plain string and performs a simple
      substring check using `in`.
    - It does not account for word boundaries, synonyms, or fuzzy matches.
      That is intentional: we want predictable, debuggable behavior, not
      an opaque ML model.
    - For more advanced behavior, you could replace this with a proper
      intent classifier, but this function is deliberately "dumb and obvious."
    """
    # Normalize to lowercase to make substring checks case-insensitive.
    q = (query or "").lower()

    # `any()` short-circuits as soon as one trigger matches.
    hit = any(t in q for t in triggers)

    # We log every call at DEBUG so it's easy to understand why the dialog
    # engine decided that a particular phrase meant "new" / "continue".
    logger.debug(
        "[_has_trigger] query=%r triggers=%r -> hit=%s",
        q,
        triggers,
        hit,
    )
    return hit


def wants_new_registration(query: str) -> bool:
    """
    Determine whether the user is explicitly asking to start a *new*
    registration workflow (as opposed to continuing an existing one).

    Examples that should match:
        - "start a new registration"
        - "register another student"
        - "new registration"

    Implementation
    --------------
    - Delegates to `_has_trigger` with a curated set of phrases.
    - If *any* of these phrases appears, we treat that as a signal that
      the user wants to begin a distinct registration workflow.
    """
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
    """
    Determine whether the user intends to *continue* an already
    existing registration session.

    Examples that should match:
        - "continue current registration"
        - "resume registration"
        - "pick up where we left off"

    Design
    ------
    - This is used in conjunction with `wants_new_registration` to
      disambiguate the user's intent when a session already exists.
    - If both "new" and "continue" triggers match, we treat it as ambiguous
      and delegate back to the agent to prompt the user explicitly.
    """
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
    """
    Determine whether the user is specifying that the student is NEW
    to the district, as opposed to a returning/existing student.

    Examples that should match:
        - "new student"
        - "register a new student"
        - "brand new student"
    """
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
    """
    Determine whether the user is specifying that the student is a
    returning/existing student (has attended DC-G in the past).

    Examples that should match:
        - "existing student"
        - "previously enrolled"
        - "returning student"
        - "attended dc-g in the past"
    """
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
    """
    Extract a normalized school year token from free text.

    Supported formats include:
        - "2025-26"
        - "2025/26"
        - "2025–26" (en dash)
        - "2025—26" (em dash -> normalized to "-")

    Regex design
    ------------
    Pattern: (20[2-9][0-9])[-/](?:20[2-9][0-9]|[0-9]{2})

    - (20[2-9][0-9]):
        * Matches a 4-digit year starting with "20".
        * The third digit is [2-9], so years 2020+ are allowed.
          (This avoids matching 2000–2019 unless you explicitly want them.)
    - [-/]:
        * Accepts either a dash "-" or slash "/" as the separator.
    - (?:20[2-9][0-9]|[0-9]{2}):
        * Either a full 4-digit year starting with "20" and [2-9],
          or a 2-digit year.
        * This covers both "2025-2026" and "2025-26".

    Returns
    -------
    str or None
        The matched year string (as it appears in the normalized text),
        or None if nothing matches.

    Normalization
    -------------
    - En dash "–" and em dash "—" are normalized to simple "-" to make
      the regex easier and more robust against copy/paste artifacts.
    """
    if not query:
        logger.debug("[extract_school_year] no query; returning None.")
        return None

    # Normalize any fancy dashes to '-' and trim leading/trailing whitespace.
    q_norm = query.strip().replace("–", "-").replace("—", "-")
    logger.debug(
        "[extract_school_year] raw_query=%r normalized=%r",
        query,
        q_norm,
    )

    # Pattern:
    #   20xx-2x   (e.g., 2025-26)
    #   20xx-20xx (e.g., 2025-2026)
    #   same with '/'
    m = re.search(r"(20[2-9][0-9])[-/](?:20[2-9][0-9]|[0-9]{2})", q_norm)
    if m:
        logger.info("[extract_school_year] matched school_year=%s", m.group(0))
        return m.group(0)

    logger.debug("[extract_school_year] no match found.")
    return None


# ======================================================================
# Session mode / dialog orchestration
# ======================================================================

# Represented as a narrow string literal type:
#   - "new"      : we are starting a new registration
#   - "continue" : we are continuing an existing registration
# We never store "None" here; None is used externally to represent ambiguity.
SessionMode = Literal["new", "continue"]


def decide_session_mode(
    ctx: AgentContext,
) -> Tuple[Optional[SessionMode], Optional[str]]:
    """
    Decide whether this request is a NEW or CONTINUE registration
    interaction, and which session_id should be used.

    Parameters
    ----------
    ctx : AgentContext
        Provides access to:
          - ctx.query               : the user message text
          - ctx.subagent_session_id : an existing registration session id,
                                     if this is a follow-up turn.

    Returns
    -------
    (session_mode, session_id) : (Optional[SessionMode], Optional[str])
        session_mode:
            - "new"       : clearly starting a new registration
            - "continue"  : clearly continuing an existing registration
            - None        : ambiguous (e.g., existing session but user hasn't
                            indicated new vs continue explicitly)
        session_id:
            - A string identifying the active registration session.
            - None in pathological cases (should be rare; caller defensively
              generates one if needed).

    Behavior
    --------
    - If there is no existing subagent_session_id, we always treat this as
      a NEW session and generate a fresh UUID.
    - If there *is* an existing session:
        * If user clearly says "continue", we reuse it.
        * If user clearly says "new", we create a brand new session id.
        * If ambiguous, we return (None, existing_id) so the caller can
          prompt the user with a "new vs continue" choice.

    Logging
    -------
    - DEBUG: raw query and existing session id.
    - INFO : high-level mode decision and IDs.
    """
    existing_id = ctx.subagent_session_id
    logger.debug(
        "[decide_session_mode] subagent_session_id=%r query=%r",
        existing_id,
        ctx.query,
    )

    if not existing_id:
        # No prior session: clearly starting fresh. We don't need to ask whether
        # the user wants "new" vs "continue" because there's nothing to continue.
        new_id = str(uuid.uuid4())
        logger.info(
            "[decide_session_mode] No existing session; starting NEW session %s",
            new_id,
        )
        return "new", new_id

    # We have a prior session; use trigger helpers to interpret the query.
    is_new = wants_new_registration(ctx.query)
    is_continue = wants_continue_registration(ctx.query)
    logger.info(
        "[decide_session_mode] existing_session=%s wants_new=%s wants_continue=%s",
        existing_id,
        is_new,
        is_continue,
    )

    if is_continue and not is_new:
        # Unambiguously continuing the existing session.
        logger.info(
            "[decide_session_mode] User chose CONTINUE on existing session %s",
            existing_id,
        )
        return "continue", existing_id

    if is_new and not is_continue:
        # User explicitly wants a *new* registration even though one exists.
        new_id = str(uuid.uuid4())
        logger.info(
            "[decide_session_mode] User chose NEW; new_session=%s previous=%s",
            new_id,
            existing_id,
        )
        return "new", new_id

    # Ambiguous: we have an existing session but the query doesn't clearly
    # indicate whether to start fresh or keep going. The agent will use
    # this `(None, existing_id)` shape to prompt the user.
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
    """
    Represents the outcome of one dialog-policy evaluation step.

    There are two main modes:

    1. Prompt mode (blocking):
       - The agent needs more information (e.g. new vs existing student).
       - In this case, `prompt_answer_text` is non-None, and the caller
         should immediately return that text to the user (no A2A call).

    2. Proceed mode:
       - The agent has enough information to proceed with calling the
         A2A registration service.
       - In this case, `proceed=True` and `session_state` contains the
         (possibly updated) RegistrationSessionState.

    Design Notes
    ------------
    - This dataclass is intentionally minimal and explicit.
    - We do *not* try to encode all possible outcomes in a single enum,
      because it's easier to read boolean flags and optional fields
      than to juggle a complex state machine enum for this level of logic.
    """

    # If prompt_answer_text is not None, the agent should RETURN that to the user
    # instead of calling A2A. The phase/status/reason help the agent build
    # consistent AgentResult metadata and front-end behavior.
    prompt_answer_text: Optional[str] = None
    prompt_phase: Optional[str] = None
    prompt_status: Optional[str] = None
    prompt_reason: Optional[str] = None

    # If we should proceed to A2A:
    # - proceed=True means "agent is allowed to call the registration service".
    # - session_state carries the resolved state to use in the payload.
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
    Evaluate the current dialog turn and decide whether we need to:

      - Prompt the user for more information (student_type/school_year),
        OR
      - Proceed to call the A2A registration service.

    Parameters
    ----------
    ctx : AgentContext
        Provides the latest user query and metadata about the conversation.
    session_mode : Optional[SessionMode]
        "new", "continue", or None (ambiguous).
    session_state : RegistrationSessionState
        The current persisted state for this registration session.
    state_store : RegistrationStateStore
        Abstraction for reading/writing session_state.

    Returns
    -------
    DialogStepResult
        - If `prompt_answer_text` is set, the caller should
          return that prompt to the user and NOT call A2A yet.
        - If `proceed=True`, the caller should use `session_state`
          to build the A2A payload.

    Strategy
    --------
    - In "continue" mode, we never block — we do best-effort inference of
      student_type/school_year but always allow the flow to proceed.
    - In "new" mode, we enforce explicit slot filling:
        * student_type is required.
        * school_year is required for new students.
        * parent info is requested in a dedicated prompt.
    - When session_mode is None and there is already a session,
      we treat that as an ambiguity and ask the user to pick
      "continue" vs "start a new registration".
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

        # Try to infer student_type from this turn if missing. We don't force
        # the user to answer this; we just enrich the state if possible.
        if not st:
            if wants_new_student(ctx.query):
                st = "new"
            elif wants_existing_student(ctx.query):
                st = "existing"

        # Try to infer school_year from this turn if missing.
        if not sy:
            sy = extract_school_year(ctx.query)

        # Use dataclasses.replace to produce an updated copy (immutable style).
        new_state = replace(session_state, student_type=st, school_year=sy)
        # Persist updated hints, so subsequent turns can benefit from them.
        await state_store.upsert(new_state)

        logger.info(
            "[evaluate_dialog_slots] CONTINUE mode inferred student_type=%r school_year=%r",
            st,
            sy,
        )
        # In CONTINUE mode we always proceed; we never block on missing fields
        # because we assume the existing registration form can capture them.
        return DialogStepResult(proceed=True, session_state=new_state)

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
        #    If we don't already have a student_type in state, try to infer it
        #    from the current query, otherwise we must prompt explicitly.
        if st is None:
            if wants_new_student(ctx.query):
                st = "new"
            elif wants_existing_student(ctx.query):
                st = "existing"

        if st is None:
            # Still unknown: we must prompt the user. This is an explicit
            # blocking step in the "wizard" flow.
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

        # 2) For NEW students, we require a school year.
        #    For EXISTING students, the year may be known implicitly via A2A.
        if st == "new" and sy is None:
            sy = extract_school_year(ctx.query)
            if sy is None:
                # The user has confirmed "new student", but hasn't given a year.
                # We block here until they specify it.
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
                return DialogStepResult(
                    prompt_answer_text=prompt,
                    prompt_phase="prompt_for_school_year",
                    prompt_status="needs_school_year",
                    prompt_reason="prompt_for_school_year",
                )

        # 3) At this point we have at least a student_type, and possibly a school_year.
        #    We persist the updated state so further turns in this session
        #    benefit from it.
        new_state = replace(session_state, student_type=st, school_year=sy)
        await state_store.upsert(new_state)

        logger.info(
            "[evaluate_dialog_slots] NEW mode resolved student_type=%r school_year=%r",
            st,
            sy,
        )

        # 4) For NEW student with a known school_year, we mirror the original behavior:
        #    ask for parent/guardian info in a separate prompt step.
        #    This still returns a prompt (blocking step), so A2A is not yet called.
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

        # 5) Otherwise: we have enough to proceed to A2A (e.g., existing student
        #    with or without explicit school_year). We do not block further here.
        return DialogStepResult(proceed=True, session_state=new_state)

    # ------------------------------------------------------------------
    # Ambiguous mode (session_mode is None) with existing session
    # ------------------------------------------------------------------
    if session_mode is None and ctx.subagent_session_id:
        # We know a session exists, but user hasn't clarified new vs continue.
        # Instead of making an assumption, we force an explicit choice. This
        # avoids surprising the user by either overwriting or reusing a session.
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
    # This is an edge case: no explicit mode was resolved, but also no
    # existing session id is present. In that case, we choose not to block and
    # hand back the current state to the caller, who will typically treat it
    # as a newly started registration.
    logger.debug(
        "[evaluate_dialog_slots] Fallback path; proceeding with session=%s",
        session_state.session_id,
    )
    return DialogStepResult(proceed=True, session_state=session_state)
