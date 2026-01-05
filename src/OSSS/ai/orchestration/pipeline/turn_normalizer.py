from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, Optional, cast, Tuple

from OSSS.ai.orchestration.interaction_state import (
    get_interaction,
    mark_no,
    mark_yes,
    InteractionMode,
    WizardType,
)
from OSSS.ai.observability import get_logger

# ✅ Step B: use protocol helpers/types (still used by legacy helpers below)
from OSSS.ai.orchestration.protocol.pending_action import (
    PendingAction,
    PendingActionResult,
)

# ✅ NEW: central protocol/turn service
from OSSS.ai.orchestration.protocol.turn_controller import TurnController

logger = get_logger(__name__)

# Single shared controller instance (stateless)
_turns = TurnController()

YES_TOKENS = {"yes", "y", "yep", "yeah", "ok", "okay", "sure", "do it", "go ahead", "confirm"}
NO_TOKENS = {"no", "n", "nope", "nah", "negative"}
CANCEL_TOKENS = {"cancel", "stop", "quit", "exit", "abort", "nevermind", "never mind"}

# ------------------------------------------------------------------
# ✅ A) Robust yes/no normalization (accept punctuation like "y.", "yes!")
# ------------------------------------------------------------------
_TRAIL_PUNCT = re.compile(r"[.!?;,:\)\]]+$")
_LEAD_PUNCT = re.compile(r"^[\(\[]+")


def _norm(s: str) -> str:
    t = (s or "").strip().lower()
    t = _LEAD_PUNCT.sub("", t)
    t = _TRAIL_PUNCT.sub("", t)
    return t.strip()


def _is_yes(s: str) -> bool:
    t = _norm(s)
    return t in YES_TOKENS or t.startswith("yes ")


def _is_no(s: str) -> bool:
    t = _norm(s)
    return t in NO_TOKENS or t.startswith("no ")


def _is_cancel(s: str) -> bool:
    t = _norm(s)
    return t in CANCEL_TOKENS or t.startswith(("cancel ", "stop ", "quit "))


# ------------------------------------------------------------------
# Protocol helpers (pending_action contract lives in exec_state)
# NOTE: with TurnController in place, these are now legacy helpers.
# You can delete them once you're confident TurnController is stable.
# ------------------------------------------------------------------

def _get_pending_action(exec_state: Dict[str, Any]) -> Optional[PendingAction]:
    pa = exec_state.get("pending_action")
    return cast(PendingAction, pa) if isinstance(pa, dict) else None


def _pending_confirm_yes_no_awaiting(pa: PendingAction | None) -> bool:
    if not pa:
        return False
    if pa.get("type") != "confirm_yes_no":
        return False
    if not bool(pa.get("awaiting")):
        return False
    pq = pa.get("pending_question")
    return isinstance(pq, str) and bool(pq.strip())


def _set_pending_action_result(
    exec_state: Dict[str, Any],
    *,
    owner: str,
    decision: str,
    context: Dict[str, Any],
) -> None:
    """
    Store a one-shot result that the owning agent can consume.
    This is the ONLY output of interpreting the user's yes/no/cancel.
    """
    owner_canon = (owner or "").strip().lower()
    d = (decision or "").strip().lower()
    if d not in {"yes", "no", "cancel"}:
        d = "cancel"

    par: PendingActionResult = {
        "type": "confirm_yes_no",
        "owner": owner_canon,
        "decision": cast(Any, d),
        "context": dict(context or {}),
    }
    exec_state["pending_action_result"] = par


def _clear_pending_action(exec_state: Dict[str, Any], pa: PendingAction | None, *, reason: str) -> None:
    """
    Clear the contract so downstream routers/agents never see "awaiting" after
    we have already consumed the user reply.

    Best-practice: snapshot to pending_action_last for debugging.
    """
    if isinstance(pa, dict):
        last = dict(pa)
        last["awaiting"] = False
        last["cleared_reason"] = reason
        exec_state["pending_action_last"] = last
    exec_state.pop("pending_action", None)


# ------------------------------------------------------------------

@dataclass
class NormalizeResult:
    handled: bool
    canonical_user_text: str
    prompt_text: Optional[str] = None


def _as_payload(res: NormalizeResult, exec_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize output to the dict shape expected by orchestration_api hardening.
    """
    return {
        "handled": bool(res.handled),
        "canonical_user_text": (res.canonical_user_text or "").strip(),
        "prompt_text": res.prompt_text,
        "exec_state": exec_state,
    }


def _coerce_inputs(*args: Any, **kwargs: Any) -> Tuple[Dict[str, Any], str]:
    """
    Accept many call signatures without crashing.

    Supported shapes:
      - normalize(exec_state, raw_user_text)
      - normalize(raw_user_text, exec_state)
      - normalize(exec_state=..., raw_user_text=...)
      - normalize(exec_state=..., user_text=...)
      - normalize(exec_state=..., text=...)
      - normalize(exec_state=..., query=...)
      - normalize(state=..., text=...)  (legacy)
    """
    # Keyword-first
    exec_state = (
        kwargs.get("exec_state")
        or kwargs.get("execution_state")
        or kwargs.get("state")
    )
    raw_text = (
        kwargs.get("raw_user_text")
        or kwargs.get("user_text")
        or kwargs.get("text")
        or kwargs.get("query")
        or kwargs.get("raw_text")
    )

    if isinstance(exec_state, dict) and isinstance(raw_text, str):
        return exec_state, raw_text

    # Positional fallbacks
    if len(args) >= 2:
        a0, a1 = args[0], args[1]
        if isinstance(a0, dict) and isinstance(a1, str):
            return a0, a1
        if isinstance(a0, str) and isinstance(a1, dict):
            return a1, a0

    # Single positional (some impls pass just exec_state)
    if len(args) == 1 and isinstance(args[0], dict):
        st = args[0]
        return st, str(st.get("raw_user_text") or "")

    # Final safe defaults
    if not isinstance(exec_state, dict):
        exec_state = {}
    if not isinstance(raw_text, str):
        raw_text = str(raw_text or "")
    return exec_state, raw_text


class TurnNormalizer:
    """
    Runs BEFORE classification/routing/planning.

    Best-practice (Step B):
      - Pending actions are protocol contracts (wizard-agnostic).
      - Normalizer interprets ONLY yes/no/cancel while a contract is awaiting.
      - It writes exec_state["pending_action_result"] and clears exec_state["pending_action"].
      - It route-locks to the contract’s resume_route/resume_pattern.
      - suppress_history=True so "yes/no" doesn't pollute conversation history.
      - canonical_user_text:
          - YES  -> pending_question (so caller can treat it as the real user intent)
          - NO/CANCEL -> "" (so nothing is routed as a query)
    """

    @staticmethod
    def normalize(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        exec_state, raw_user_text = _coerce_inputs(*args, **kwargs)

        # ------------------------------------------------------------------
        # ✅ Apply 2): Use TurnController at the TOP
        # ------------------------------------------------------------------
        r = _turns.preprocess(exec_state, raw_user_text)
        if getattr(r, "handled", False):
            # r is your TurnController result object (kept opaque here)
            res = NormalizeResult(
                handled=True,
                canonical_user_text=getattr(r, "canonical_user_text", "") or "",
                prompt_text=getattr(r, "prompt_text", None),
            )
            return _as_payload(res, exec_state)

        # ------------------------------------------------------------------
        # ✅ Apply 3): Consume exec_state["pending_action"] (protocol contract)
        # ------------------------------------------------------------------
        pending = _get_pending_action(exec_state)
        if _pending_confirm_yes_no_awaiting(pending):
            owner = str((pending or {}).get("owner") or "").strip().lower() or "data_query"
            resume_route = str((pending or {}).get("resume_route") or "data_query").strip().lower()
            resume_pattern = str((pending or {}).get("resume_pattern") or resume_route).strip().lower()
            pending_question = str((pending or {}).get("pending_question") or "").strip()
            ctx = (pending or {}).get("context") or {}
            if not isinstance(ctx, dict):
                ctx = {}

            # YES -> resume original question
            if _is_yes(raw_user_text):
                if pending_question:
                    exec_state["route"] = resume_route
                    exec_state["route_locked"] = True
                    exec_state["route_key"] = "pending_action_yes"
                    exec_state["route_reason"] = "pending_action_resume"
                    exec_state["graph_pattern"] = resume_pattern
                    exec_state["suppress_history"] = True

                    _set_pending_action_result(exec_state, owner=owner, decision="yes", context=ctx)
                    _clear_pending_action(exec_state, pending, reason="user_yes")

                    logger.info(
                        "[turn_normalizer] pending_action YES handled",
                        extra={
                            "event": "turn_normalizer_pending_action_yes",
                            "owner": owner,
                            "resume_route": resume_route,
                            "resume_pattern": resume_pattern,
                            "pending_question_preview": pending_question[:200],
                            "route_locked": True,
                        },
                    )
                    return _as_payload(NormalizeResult(True, pending_question), exec_state)

                _set_pending_action_result(exec_state, owner=owner, decision="cancel", context=ctx)
                _clear_pending_action(exec_state, pending, reason="missing_pending_question")
                exec_state["suppress_history"] = True
                return _as_payload(NormalizeResult(True, ""), exec_state)

            # NO -> stop wizard; do not route as a query
            if _is_no(raw_user_text):
                exec_state["suppress_history"] = True
                _set_pending_action_result(exec_state, owner=owner, decision="no", context=ctx)
                _clear_pending_action(exec_state, pending, reason="user_no")

                logger.info(
                    "[turn_normalizer] pending_action NO handled",
                    extra={"event": "turn_normalizer_pending_action_no", "owner": owner},
                )
                return _as_payload(NormalizeResult(True, ""), exec_state)

            # CANCEL -> stop wizard; do not route as a query
            if _is_cancel(raw_user_text):
                exec_state["suppress_history"] = True
                _set_pending_action_result(exec_state, owner=owner, decision="cancel", context=ctx)
                _clear_pending_action(exec_state, pending, reason="user_cancel")

                logger.info(
                    "[turn_normalizer] pending_action CANCEL handled",
                    extra={"event": "turn_normalizer_pending_action_cancel", "owner": owner},
                )
                return _as_payload(NormalizeResult(True, ""), exec_state)

            # Unclear response while awaiting -> reprompt
            exec_state["suppress_history"] = True
            prompt = "Please reply **yes** or **no**."
            logger.info(
                "[turn_normalizer] pending_action unclear response; reprompt",
                extra={"event": "turn_normalizer_pending_action_unclear", "raw_norm": _norm(raw_user_text)[:80]},
            )
            return _as_payload(NormalizeResult(True, "", prompt_text=prompt), exec_state)

        # ------------------------------------------------------------------
        # Existing interaction_state path (backwards compatibility)
        # ------------------------------------------------------------------
        interaction = get_interaction(exec_state)

        if interaction.mode != InteractionMode.WIZARD_YES_NO or not interaction.awaiting:
            return _as_payload(NormalizeResult(False, raw_user_text or ""), exec_state)

        # we are awaiting yes/no for a wizard
        if _is_yes(raw_user_text):
            pending_q = interaction.pending_question.strip()
            mark_yes(exec_state)

            # **route lock** so "yes" never hits refiner/final as a query
            if interaction.wizard == WizardType.DATA_QUERY:
                exec_state["graph_pattern"] = "data_query"
                exec_state["route"] = "data_query"
                exec_state["route_locked"] = True
                exec_state["route_key"] = "wizard_yes"
                exec_state["route_reason"] = "wizard_yes_resume_data_query"

                exec_state["user_question"] = pending_q
                exec_state["query"] = pending_q
                exec_state["question"] = pending_q
                exec_state.setdefault("effective_queries", {})["user"] = pending_q

                exec_state["suppress_history"] = True

            logger.info(
                "turn_normalizer_wizard_yes",
                extra={
                    "event": "turn_normalizer_wizard_yes",
                    "wizard": interaction.wizard.value if interaction.wizard else None,
                    "raw_user_text_norm": _norm(raw_user_text)[:80],
                    "pending_question_preview": pending_q[:200],
                    "route": exec_state.get("route"),
                    "route_locked": bool(exec_state.get("route_locked")),
                    "graph_pattern": exec_state.get("graph_pattern"),
                    "route_key": exec_state.get("route_key"),
                    "route_reason": exec_state.get("route_reason"),
                },
            )
            return _as_payload(NormalizeResult(True, pending_q), exec_state)

        if _is_no(raw_user_text) or _is_cancel(raw_user_text):
            mark_no(exec_state)

            exec_state["wizard_bailed"] = True
            exec_state["wizard_bail_reason"] = (
                "user_cancelled_yes_no_prompt" if _is_cancel(raw_user_text) else "user_declined_yes_no_prompt"
            )
            exec_state["suppress_history"] = True

            logger.info(
                "[turn_normalizer] wizard NO handled",
                extra={
                    "event": "turn_normalizer_wizard_no",
                    "raw_user_text_norm": _norm(raw_user_text)[:80],
                    "cancel": _is_cancel(raw_user_text),
                },
            )
            return _as_payload(NormalizeResult(True, ""), exec_state)

        prompt = "Please reply **yes** or **no**."
        logger.info(
            "[turn_normalizer] wizard unclear response; reprompt",
            extra={
                "event": "turn_normalizer_wizard_unclear",
                "raw_norm": _norm(raw_user_text)[:80],
            },
        )
        return _as_payload(NormalizeResult(True, "", prompt_text=prompt), exec_state)
