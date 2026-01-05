from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from OSSS.ai.observability import get_logger
from OSSS.ai.orchestration.protocol.pending_action import (
    PendingAction,
    PendingActionResult,
    set_pending_confirm_yes_no,
    consume_pending_action_result,
)

logger = get_logger(__name__)


@dataclass
class NormalizeResult:
    handled: bool
    canonical_user_text: str
    prompt_text: Optional[str] = None


class TurnController:
    """
    TurnController (InteractionProtocolService)

    Owns ONLY mechanical turn protocol:
      - interpret pending_action yes/no/cancel replies
      - write pending_action_result
      - clear pending_action awaiting flag
      - route-lock
      - suppress_history
      - decide canonical_user_text

    Does NOT:
      - classify intent
      - choose DB tables
      - run business logic
      - mutate wizard steps (beyond optional migration healing)
    """

    YES_TOKENS = {"yes", "y", "yep", "yeah", "ok", "okay", "sure", "do it", "go ahead", "confirm"}
    NO_TOKENS = {"no", "n", "nope", "nah", "negative"}
    CANCEL_TOKENS = {"cancel", "stop", "quit", "exit", "abort", "nevermind", "never mind"}

    def __init__(self) -> None:
        # Keep this service stateless; no config stored here unless you pass it each call.
        pass

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------

    def preprocess(self, exec_state: Dict[str, Any], raw_user_text: str) -> NormalizeResult:
        """
        Entry point called at the TOP of TurnNormalizer.normalize().

        REQUIRED FIX:
        - Treat "yes"/"no"/"cancel" specially ONLY if we have an *awaiting* pending_action.
        - Never resume based on leftover helper fields like pending_action_last/pending_action_result.

        Concretely:
            pending = exec_state.get("pending_action")
            if isinstance(pending, dict) and pending.get("awaiting") is True:
                ...
        """
        pa = exec_state.get("pending_action")
        if not (isinstance(pa, dict) and pa.get("awaiting") is True):
            return NormalizeResult(handled=False, canonical_user_text=raw_user_text or "")

        # Only then do we validate type/shape
        if not self._is_confirm_yes_no_awaiting(pa):
            return NormalizeResult(handled=False, canonical_user_text=raw_user_text or "")

        owner = str(pa.get("owner") or "").strip().lower() or "unknown"
        pending_q = str(pa.get("pending_question") or "").strip()

        ctx = pa.get("context")
        ctx_dict: Dict[str, Any] = ctx if isinstance(ctx, dict) else {}

        resume_route = str(pa.get("resume_route") or "").strip().lower() or "data_query"
        resume_pattern = str(pa.get("resume_pattern") or "").strip().lower() or "data_query"

        # YES
        if self._is_yes(raw_user_text):
            self._set_pending_action_result(exec_state, owner=owner, decision="yes", context=ctx_dict)
            self._clear_pending_action(exec_state, pa, reason="confirm_yes_no_yes")

            self.lock_route(
                exec_state,
                route=resume_route,
                pattern=resume_pattern,
                key=f"pending_action_yes:{owner}",
                reason="pending_action_yes_resume",
            )
            exec_state["suppress_history"] = True

            logger.info(
                "turn_controller_yes",
                extra={
                    "event": "turn_controller_yes",
                    "owner": owner,
                    "resume_route": resume_route,
                    "resume_pattern": resume_pattern,
                    "pending_question_preview": pending_q[:200],
                },
            )
            return NormalizeResult(handled=True, canonical_user_text=pending_q)

        # NO / CANCEL
        if self._is_no(raw_user_text) or self._is_cancel(raw_user_text):
            decision = "cancel" if self._is_cancel(raw_user_text) else "no"
            self._set_pending_action_result(exec_state, owner=owner, decision=decision, context=ctx_dict)
            self._clear_pending_action(exec_state, pa, reason=f"confirm_yes_no_{decision}")

            exec_state["suppress_history"] = True
            exec_state["pending_action_bailed"] = True
            exec_state["pending_action_bail_reason"] = f"user_{decision}"

            logger.info(
                "turn_controller_no",
                extra={"event": "turn_controller_no", "owner": owner, "decision": decision},
            )
            return NormalizeResult(handled=True, canonical_user_text="")

        # UNCLEAR
        # Prefer a stashed UX prompt if provided by ask_confirm_yes_no()
        display_prompt = ""
        if isinstance(pa, dict):
            dp = pa.get("display_prompt")
            display_prompt = str(dp).strip() if isinstance(dp, str) else ""

        logger.info(
            "turn_controller_unclear",
            extra={"event": "turn_controller_unclear", "owner": owner},
        )
        return NormalizeResult(
            handled=True,
            canonical_user_text="",
            prompt_text=display_prompt or "Please reply **yes** or **no**.",
        )

    def consume(self, exec_state: Dict[str, Any], *, owner: str) -> Optional[PendingActionResult]:
        """
        Agent entry helper: consume one-shot pending_action_result for this owner.
        """
        par = consume_pending_action_result(exec_state, owner=owner)
        if not par:
            return None

        # ✅ Patch 2 (best-practice): once delivered to the owner, clear protocol state.
        # Otherwise the conversation can keep persisting "has_pending_action=true" and
        # the system will loop back to the first-turn confirmation prompt.
        exec_state.pop("pending_action", None)
        exec_state.pop("pending_action_result", None)
        exec_state.pop("pending_action_resume_turn", None)

        # Clear any legacy/compat fields that can re-trigger confirm flows.
        exec_state.pop("pending_confirmation", None)
        exec_state.pop("confirm_table", None)
        exec_state.pop("pending_action_last", None)

        return par

    def ask_confirm_yes_no(
        self,
        exec_state: Dict[str, Any],
        *,
        owner: str,
        pending_question: str,
        prompt: str,
        resume_route: str,
        resume_pattern: str,
        context: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None,  # ✅ required by helper
    ) -> None:
        """
        Convenience wrapper to create a confirm_yes_no pending action.

        Notes:
        - set_pending_confirm_yes_no() requires kw-only `reason`.
        - Preserve UI prompt by stashing it as an optional field on pending_action.
        """
        reason = (reason or "confirm_yes_no").strip()

        set_pending_confirm_yes_no(
            exec_state,
            owner=owner,
            pending_question=pending_question,
            resume_route=resume_route,
            resume_pattern=resume_pattern,
            context=context or {},
            reason=reason,
        )

        # Optional: stash prompt for UX without changing helper signature
        pa = exec_state.get("pending_action")
        if isinstance(pa, dict) and prompt:
            pa2 = dict(pa)
            pa2["display_prompt"] = prompt
            exec_state["pending_action"] = pa2

    def lock_route(
        self,
        exec_state: Dict[str, Any],
        *,
        route: str,
        pattern: str,
        key: str,
        reason: str,
    ) -> None:
        exec_state["route"] = route
        exec_state["graph_pattern"] = pattern
        exec_state["route_locked"] = True
        exec_state["route_key"] = key
        exec_state["route_reason"] = reason

    def wizard_step_migration_heal(self, wizard_state: Dict[str, Any]) -> Tuple[str, bool]:
        """
        Migration-window helper:
          - prefer step
          - fallback legacy pending_action/status
          - block confirm_table/pending_confirmation
          - optionally return 'healed' flag so caller can persist wizard_state["step"]
        """
        if not isinstance(wizard_state, dict) or not wizard_state:
            return "", False

        step_raw = wizard_state.get("step") or wizard_state.get("pending_action") or wizard_state.get("status") or ""
        step = str(step_raw or "").strip().lower()

        if step in {"confirm_table", "pending_confirmation"}:
            return step, False

        healed = False
        if step and "step" not in wizard_state:
            wizard_state["step"] = step
            healed = True
        return step, healed

    # ---------------------------------------------------------------------
    # Internals (small + boring)
    # ---------------------------------------------------------------------

    def _is_confirm_yes_no_awaiting(self, pa: Optional[PendingAction]) -> bool:
        if not pa:
            return False
        if pa.get("type") != "confirm_yes_no":
            return False
        # REQUIRED FIX: awaiting must be True to qualify as "resume"
        if pa.get("awaiting") is not True:
            return False
        pq = pa.get("pending_question")
        return isinstance(pq, str) and bool(pq.strip())

    def _set_pending_action_result(
        self,
        exec_state: Dict[str, Any],
        *,
        owner: str,
        decision: str,
        context: Dict[str, Any],
    ) -> None:
        d = (decision or "").strip().lower()
        if d not in {"yes", "no", "cancel"}:
            d = "cancel"

        exec_state["pending_action_result"] = {
            "type": "confirm_yes_no",
            "owner": (owner or "").strip().lower(),
            "decision": d,
            "context": dict(context or {}),
        }

        # IMPORTANT: do not let stale helper fields influence later turns
        # (resume is gated by pending_action.awaiting only)
        exec_state.pop("pending_action_last", None)

    def _clear_pending_action(self, exec_state: Dict[str, Any], pa: Optional[PendingAction], *, reason: str) -> None:
        """
        Mark the pending action as cleared by flipping awaiting=False.

        NOTE: We intentionally keep the pending_action object (awaiting=False) in exec_state
        so that upstream merges can't "resurrect" an old awaiting=True action.
        """
        if isinstance(pa, dict):
            pa2 = dict(pa)
            pa2["awaiting"] = False
            pa2["cleared_reason"] = reason
            exec_state["pending_action"] = pa2

        # ✅ clear helper fields that can linger
        exec_state.pop("pending_action_resume_turn", None)
        exec_state.pop("pending_action_last", None)

    # Token parsing
    def _norm(self, s: str) -> str:
        t = (s or "").strip().lower()
        # simple punctuation trim; you can keep your regex approach if preferred
        return t.strip(" \t\r\n.!?;,:()[]{}\"'")

    def _is_yes(self, s: str) -> bool:
        t = self._norm(s)
        return t in self.YES_TOKENS or t.startswith("yes ")

    def _is_no(self, s: str) -> bool:
        t = self._norm(s)
        return t in self.NO_TOKENS or t.startswith("no ")

    def _is_cancel(self, s: str) -> bool:
        t = self._norm(s)
        return t in self.CANCEL_TOKENS or t.startswith(("cancel ", "stop ", "quit "))
