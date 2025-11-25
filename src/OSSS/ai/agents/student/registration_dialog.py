from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from OSSS.ai.agents.base import AgentContext

from .registration_state import RegistrationSessionState
from .registration_state_store import RegistrationStateStore

# Shared dialog helpers
from OSSS.ai.agents.utils.dialog_utils import (
    parse_yes_no_choice,
    parse_numeric_yes_no,
    extract_school_year,
    get_default_school_year_options,
    parse_school_year_choice,
    wants_new_registration,
    wants_continue_registration,
)

logger = logging.getLogger("OSSS.ai.agents.registration.dialog")

# ----------------------------------------------------------------------
# Session mode
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


def decide_session_mode(
    ctx: AgentContext,
) -> Tuple[Optional[SessionMode], Optional[str]]:
    """
    Decide whether this turn is a NEW or CONTINUE registration interaction,
    and which session_id to use.

    Simplified:
    - If there is no existing subagent_session_id -> start NEW
    - If there *is* an existing subagent_session_id -> always CONTINUE
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

    # Existing session: always continue the same registration flow.
    logger.info(
        "[decide_session_mode] Existing session found; CONTINUE session %s",
        existing_id,
    )
    return "continue", existing_id


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
# JSON-driven dialog engine
# ----------------------------------------------------------------------


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


# ----------------- parser helpers -----------------
def _parser_yes_no_numeric(
    text: str,
    state: RegistrationSessionState,
) -> Optional[bool]:
    """Use shared numeric 1/2 -> True/False parser."""
    return parse_numeric_yes_no(text)


def _parser_yes_no_any(
    text: str,
    state: RegistrationSessionState,
) -> Optional[bool]:
    """Allow 1/2 and yes/no/y/n."""
    return parse_yes_no_choice(text)


def _parser_school_year_choice(
    text: str,
    state: RegistrationSessionState,
) -> Optional[str]:
    """
    Use existing school-year choice logic on top of our default options.
    """
    options = get_default_school_year_options()
    # First see if they typed an explicit year
    direct = infer_school_year_from_query(text, None)
    if direct:
        # If it's a valid-looking year, accept as-is (even if not in menu)
        return direct

    return parse_school_year_choice(text, options)


def _parser_non_empty_text(
    text: str,
    state: RegistrationSessionState,
) -> Optional[str]:
    value = (text or "").strip()
    return value or None


def _parser_email(
    text: str,
    state: RegistrationSessionState,
) -> Optional[str]:
    value = (text or "").strip()
    if "@" not in value or "." not in value:
        return None
    return value


def _parser_file_upload(
    text: str,
    state: RegistrationSessionState,
) -> Optional[str]:
    """
    File-upload slot parser.

    The router/agent should attach the uploaded file path to
    state.proof_of_residency_upload before this runs.

    We:
    - Prefer that pre-attached value if present.
    - Otherwise, fall back to any non-empty text (for manual testing).
    """
    existing = getattr(state, "proof_of_residency_upload", None)
    if existing:
        return existing

    value = (text or "").strip()
    return value or None


PARSERS = {
    "yes_no_numeric": _parser_yes_no_numeric,
    "yes_no_any": _parser_yes_no_any,
    "school_year_choice": _parser_school_year_choice,
    "non_empty_text": _parser_non_empty_text,
    "email": _parser_email,
    "file_upload": _parser_file_upload,
}

class DialogEngine:
    """
    Generic, JSON-driven dialog engine.

    Expects a flow dict with:

    {
      "id": "dcg_registration_v1",
      "steps": [
        {
          "id": "documents",
          "slot": "student_documents_confirmed",  # or null
          "prompt": "...",
          "retry_prompt": "...",
          "parser": "yes_no_numeric",
          "next": "school_year",                  # optional
          "on_result": { "true": "school_year",
                         "false": "documents_blocked" }
        },
        ...
      ]
    }
    """

    def __init__(self, flow: Dict[str, Any]):
        self.flow = flow
        self.steps_by_id: Dict[str, Dict[str, Any]] = {
            step["id"]: step for step in flow.get("steps", [])
        }

    # ----------------- core helpers -----------------

    def _render_template(
        self,
        text: str,
        state: RegistrationSessionState,
    ) -> str:
        """
        Tiny template helper that replaces simple {{slot_name}} placeholders
        using attributes on RegistrationSessionState.
        Also supports {{school_year_menu}} which we render dynamically.
        """
        if not text:
            return text

        result = text

        # Structured menu for school-year
        if "{{school_year_menu}}" in result:
            options = get_default_school_year_options()
            menu_lines = [f"{idx}. **{opt}**" for idx, opt in enumerate(options, start=1)]
            result = result.replace("{{school_year_menu}}", "\n".join(menu_lines))

        # Generic {{slot_name}} replacements
        # (add more as needed; we keep it simple for now)
        replacements = {
            "school_year": state.school_year or "",
            "parent_first_name": state.parent_first_name or "",
            "parent_last_name": state.parent_last_name or "",
        }
        for key, value in replacements.items():
            result = result.replace(f"{{{{{key}}}}}", value)

        return result

    def render_prompt(
        self,
        step_id: str,
        state: RegistrationSessionState,
        retry: bool = False,
    ) -> str:
        step = self.steps_by_id[step_id]
        raw = step.get("retry_prompt") if retry and step.get("retry_prompt") else step.get("prompt", "")
        return self._render_template(raw, state)

    def step_for_state(self, state: RegistrationSessionState) -> Optional[str]:
        """
        Default "next missing slot" policy. Steps that don't declare a slot
        are only entered via explicit transitions.
        """
        for step in self.flow.get("steps", []):
            slot = step.get("slot")
            if not slot:
                continue
            if getattr(state, slot, None) is None:
                return step["id"]
        return None

    # ----------------- main turn handler -----------------

    def handle_turn(
        self,
        state: RegistrationSessionState,
        user_query: str,
        last_step_id: Optional[str],
    ) -> Tuple[str, RegistrationSessionState, Optional[str]]:
        """
        Returns: (prompt_to_show, updated_state, next_step_id)

        - If last_step_id is not None, we interpret user_query as the
          answer to that step (parse + store), then choose the next step.
        - If last_step_id is None, we pick the first missing-slot step.
        - If next_step_id is None, the engine is done → proceed.
        """
        next_step_id: Optional[str] = None
        query = user_query or ""

        # 1) Handle answer to last step
        if last_step_id is not None:
            step = self.steps_by_id.get(last_step_id)
            if not step:
                logger.warning(
                    "[DialogEngine] Unknown step_id=%r in state; clearing last_step_id.",
                    last_step_id,
                )
                # Fall through to "pick first missing slot"
                next_step_id = self.step_for_state(state)
            else:
                parser_name = step.get("parser")
                slot = step.get("slot")
                parsed: Any = query.strip()

                if parser_name:
                    parser_fn = PARSERS.get(parser_name)
                    if parser_fn is None:
                        logger.warning(
                            "[DialogEngine] Missing parser=%r for step=%s; "
                            "using raw text.",
                            parser_name,
                            last_step_id,
                        )
                    else:
                        parsed = parser_fn(query, state)

                # If this step is intended to fill a slot and parsing failed,
                # re-prompt with retry.
                if slot and parsed is None:
                    prompt = self.render_prompt(last_step_id, state, retry=True)
                    return prompt, state, last_step_id

                # Store the parsed slot value if relevant
                if slot:
                    setattr(state, slot, parsed)

                # Branch on result if on_result is declared
                on_result = step.get("on_result")
                if on_result:
                    key: str
                    if isinstance(parsed, bool):
                        key = "true" if parsed else "false"
                    else:
                        key = str(parsed).lower()

                    next_step_id = on_result.get(key)

                # If no branch-specific next step, fall back to explicit "next"
                if not next_step_id:
                    next_step_id = step.get("next")

                # If still nothing, fall back to "first missing slot" rule
                if not next_step_id:
                    next_step_id = self.step_for_state(state)

        else:
            # 2) No last step: start with first missing-slot step
            next_step_id = self.step_for_state(state)

        # 3) If there's no next step, the engine is done
        if not next_step_id:
            logger.info(
                "[DialogEngine] No further steps required; dialog flow is complete "
                "for session=%s",
                state.session_id,
            )
            return "", state, None

        # 4) Render the prompt for next_step_id
        prompt = self.render_prompt(next_step_id, state, retry=False)
        return prompt, state, next_step_id


# ----------------------------------------------------------------------
# Load registration_flow.json and create a global DialogEngine
# ----------------------------------------------------------------------

_ENGINE: Optional[DialogEngine] = None

_flow_path = Path(__file__).with_name("registration_flow.json")
try:
    with _flow_path.open("r", encoding="utf-8") as f:
        flow_data = json.load(f)
    _ENGINE = DialogEngine(flow_data)
    logger.info(
        "[registration_dialog] Loaded JSON dialog flow from %s (id=%s)",
        _flow_path,
        flow_data.get("id"),
    )
except Exception as exc:
    logger.error(
        "[registration_dialog] Failed to load registration_flow.json from %s: %s",
        _flow_path,
        exc,
    )
    _ENGINE = None


def _dialog_via_engine_pure(
    ctx: AgentContext,
    session_state: RegistrationSessionState,
) -> Tuple[DialogStepResult, RegistrationSessionState]:
    """
    Small wrapper around the DialogEngine that:
      - Uses inner_data['last_step_id'] to know which step we’re answering.
      - Stores updated last_step_id back into inner_data.
      - Returns a DialogStepResult with proceed=False (prompt) or True (done).
    """
    if _ENGINE is None:
        # Fallback: if the JSON flow can't be loaded, just proceed and let the
        # caller decide what to do.
        logger.warning(
            "[registration_dialog] DialogEngine is not initialized; "
            "skipping dialog and proceeding for session=%s",
            session_state.session_id,
        )
        return (
            DialogStepResult(
                proceed=True,
                session_state=session_state,
            ),
            session_state,
        )

    inner = session_state.inner_data or {}
    last_step_id = inner.get("last_step_id")

    # 🔹 SPECIAL CASE: file upload step
    # If we are currently on the upload_proof_of_residency step AND there
    # is a file attached for this turn, attach it to the state so that
    # the 'file_upload' parser can succeed even if ctx.query == "".
    try:
        if last_step_id == "upload_proof_of_residency":
            files = getattr(ctx, "session_files", None) or []
            if files and getattr(session_state, "proof_of_residency_upload", None) is None:
                # You are saving uploads under:
                #   /tmp/osss_rag_uploads/<agent_session_id>/<filename>
                agent_session_id = getattr(ctx, "agent_session_id", None)
                if agent_session_id:
                    upload_dir = Path("/tmp/osss_rag_uploads") / agent_session_id
                    full_path = str(upload_dir / files[0])
                else:
                    # Fallback: just store the filename
                    full_path = files[0]

                session_state.proof_of_residency_upload = full_path
                logger.info(
                    "[registration_dialog] Attached uploaded proof-of-residency "
                    "file to state: %s",
                    full_path,
                )
    except Exception as exc:
        logger.exception(
            "[registration_dialog] Failed to attach uploaded file to state: %s",
            exc,
        )

    # Now run the JSON-driven engine as usual
    prompt, updated_state, next_step_id = _ENGINE.handle_turn(
        state=session_state,
        user_query=ctx.query or "",
        last_step_id=last_step_id,
    )

    # Persist the new last_step_id for the next turn
    updated_inner = updated_state.inner_data or {}
    updated_inner["last_step_id"] = next_step_id
    updated_state.inner_data = updated_inner

    # If next_step_id is None, the flow is complete → proceed
    if next_step_id is None:
        return (
            DialogStepResult(
                proceed=True,
                session_state=updated_state,
            ),
            updated_state,
        )

    # Otherwise, we have a prompt to show
    return (
        DialogStepResult(
            prompt_answer_text=prompt,
            prompt_phase=f"step:{next_step_id}",
            prompt_status="needs_input",
            prompt_reason=f"step:{next_step_id}",
            proceed=False,
            session_state=updated_state,
        ),
        updated_state,
    )


# ----------------------------------------------------------------------
# Dialog wrappers used by the agent
# ----------------------------------------------------------------------


def dialog_for_continue_mode_pure(
    ctx: AgentContext,
    session_state: RegistrationSessionState,
) -> Tuple[DialogStepResult, RegistrationSessionState]:
    """
    CONTINUE mode: we simply feed the current turn into the JSON-driven engine.

    The engine itself is responsible for seeing which slots are still missing
    (documents, school_year, parent info, attended-before flag, etc.) and
    producing either:
      - a prompt (proceed=False), or
      - a "we're done" result (proceed=True).
    """
    logger.debug(
        "[dialog_for_continue_mode_pure] CONTINUE for session=%s",
        session_state.session_id,
    )
    return _dialog_via_engine_pure(ctx, session_state)


def dialog_for_new_mode_pure(
    ctx: AgentContext,
    session_state: RegistrationSessionState,
) -> Tuple[DialogStepResult, RegistrationSessionState]:
    """
    NEW mode: same as CONTINUE, but semantically represents a fresh flow.

    The JSON-driven engine is fully responsible for:
      - asking for document confirmation,
      - asking for school_year,
      - asking for parent first/last/email,
      - asking attended-before,
      - and deciding when the dialog is complete.
    """
    logger.debug(
        "[dialog_for_new_mode_pure] NEW mode for session=%s",
        session_state.session_id,
    )
    return _dialog_via_engine_pure(ctx, session_state)


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

    - Delegates to JSON-driven dialog helpers (easy to update via registration_flow.json).
    - Handles persistence via RegistrationStateStore.
    """

    # ------------------------------------------------------
    # Special handling: file upload for proof_of_residency
    # ------------------------------------------------------
    inner = session_state.inner_data or {}
    last_step_id = inner.get("last_step_id")

    uploaded_files = getattr(ctx, "session_files", None) or []
    logger.debug(
        "[evaluate_dialog_slots] last_step_id=%r uploaded_files=%r",
        last_step_id,
        uploaded_files,
    )

    if last_step_id == "upload_proof_of_residency" and uploaded_files:
        # Use the first uploaded file as the stored proof-of-residency token.
        file_label = uploaded_files[0]
        logger.info(
            "[evaluate_dialog_slots] Captured proof_of_residency_upload=%r "
            "for session=%s",
            file_label,
            session_state.session_id,
        )

        session_state.proof_of_residency_upload = file_label

        # Clear last_step_id so the engine won't retry this step
        inner["last_step_id"] = None
        session_state.inner_data = inner

        await state_store.save(session_state)

    # ------------------------------------------------------
    # CONTINUE mode
    # ------------------------------------------------------
    if session_mode == "continue":
        result, updated_state = dialog_for_continue_mode_pure(ctx, session_state)
        await state_store.save(updated_state)
        return result

    # NEW mode
    if session_mode == "new":
        result, updated_state = dialog_for_new_mode_pure(ctx, session_state)
        await state_store.save(updated_state)
        return result

    logger.debug(
        "[evaluate_dialog_slots] Fallback path; proceeding with session=%s "
        "(session_mode=%r)",
        session_state.session_id,
        session_mode,
    )
    return DialogStepResult(proceed=True, session_state=session_state)
