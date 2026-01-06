from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Literal

from OSSS.ai.observability import get_logger
from OSSS.ai.orchestration.protocol.pending_action import (
    PendingAction,
    PendingActionResult,
    consume_pending_action_result,
    set_pending_confirm_yes_no,
)

logger = get_logger(__name__)


Decision = Literal["yes", "no", "cancel"]


@dataclass
class NormalizeResult:
    handled: bool
    canonical_user_text: str
    prompt_text: Optional[str] = None


class TurnController:
    """
    TurnController (InteractionProtocolService)

    Best-practice contract:
      - pending_action is the ONLY gate for “awaiting a reply”.
      - Interprets yes/no/cancel ONLY when:
          pending_action.type == "confirm_yes_no" AND pending_action.awaiting is True
      - On yes/no/cancel:
          * write a one-shot pending_action_result
          * consume the pending_action by setting awaiting=False
          * ensure future code does NOT treat presence of pending_action as "still pending"
            (we preserve the object but mark it as cleared)
          * clear any stale final/answer/response fields so the previous prompt can't be re-served
      - On unclear:
          * DO NOT consume; reprompt and keep awaiting=True
          * route-lock + suppress_history so planner/classifier doesn't drift
    """

    YES_TOKENS = {"yes", "y", "yep", "yeah", "ok", "okay", "sure", "do it", "go ahead", "confirm"}
    NO_TOKENS = {"no", "n", "nope", "nah", "negative"}
    CANCEL_TOKENS = {"cancel", "stop", "quit", "exit", "abort", "nevermind", "never mind"}

    # Keys that, if left around, commonly cause stale prompt/answer to be returned on next turn.
    _STALE_OUTPUT_KEYS = (
        "final",
        "response",
        "answer",
        "final_text_markdown",
        "answer_text_markdown",
        "assistant_message",
        "assistant_output",
    )

    def __init__(self) -> None:
        # Stateless service
        pass

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------

    def preprocess(self, exec_state: Dict[str, Any], raw_user_text: str) -> NormalizeResult:
        """
        Called at the TOP of TurnNormalizer.normalize().

        If we are awaiting a confirm_yes_no reply:
          - YES => emit pending_action_result(decision=yes) + consume gate + lock route + suppress_history
                   canonical_user_text = pending_question
          - NO/CANCEL => emit pending_action_result(decision=no|cancel) + consume gate + suppress_history
                         canonical_user_text = ""
          - UNCLEAR => keep awaiting=True, reprompt, lock route, suppress_history
        """

        # Clear any resume metadata from earlier turns (avoid confusing downstream logic).
        exec_state.pop("pending_action_resume_reason", None)
        exec_state.pop("pending_action_resume_owner", None)
        exec_state.pop("pending_action_resume_turn", None)

        pa = exec_state.get("pending_action")
        if not self._is_confirm_yes_no_awaiting(pa):
            return NormalizeResult(handled=False, canonical_user_text=raw_user_text or "")

        owner = self._norm_owner(pa.get("owner"))
        pending_q = str(pa.get("pending_question") or "").strip()

        ctx = pa.get("context")
        ctx_dict: Dict[str, Any] = ctx if isinstance(ctx, dict) else {}

        resume_route = self._norm_route(pa.get("resume_route")) or "data_query"
        resume_pattern = self._norm_route(pa.get("resume_pattern")) or resume_route

        # YES
        if self._is_yes(raw_user_text):
            self._clear_stale_outputs(exec_state)

            self._set_pending_action_result(
                exec_state,
                owner=owner,
                decision="yes",
                context=ctx_dict,
                resume_route=resume_route,
                resume_pattern=resume_pattern,
                pending_question=pending_q,
            )
            self._consume_pending_action(exec_state, reason="confirm_yes_no_yes")
            self._ensure_wizard_step_after_yes(exec_state)

            exec_state["pending_action_resume_turn"] = True
            exec_state["pending_action_resume_reason"] = "pending_action_yes_resume"
            exec_state["pending_action_resume_owner"] = owner

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
            decision: Decision = "cancel" if self._is_cancel(raw_user_text) else "no"

            self._clear_stale_outputs(exec_state)

            self._set_pending_action_result(
                exec_state,
                owner=owner,
                decision=decision,
                context=ctx_dict,
                resume_route=resume_route,
                resume_pattern=resume_pattern,
                pending_question=pending_q,
            )
            self._consume_pending_action(exec_state, reason=f"confirm_yes_no_{decision}")

            exec_state["suppress_history"] = True
            exec_state["pending_action_bailed"] = True
            exec_state["pending_action_bail_reason"] = f"user_{decision}"

            exec_state["pending_action_resume_turn"] = True
            exec_state["pending_action_resume_reason"] = f"pending_action_{decision}_resume"
            exec_state["pending_action_resume_owner"] = owner

            logger.info(
                "turn_controller_no",
                extra={"event": "turn_controller_no", "owner": owner, "decision": decision},
            )
            return NormalizeResult(handled=True, canonical_user_text="")

        # UNCLEAR (reprompt, do NOT consume)
        dp = pa.get("display_prompt")
        display_prompt = str(dp).strip() if isinstance(dp, str) else ""

        exec_state["suppress_history"] = True
        exec_state["pending_action_resume_turn"] = True
        exec_state["pending_action_resume_reason"] = "pending_action_unclear_reprompt"
        exec_state["pending_action_resume_owner"] = owner

        # Route-lock so classifier/planner doesn't wander.
        self.lock_route(
            exec_state,
            route=resume_route,
            pattern=resume_pattern,
            key=f"pending_action_unclear:{owner}",
            reason="pending_action_unclear_reprompt",
        )

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
        Agent helper: consume one-shot pending_action_result for this owner.
        """
        par = consume_pending_action_result(exec_state, owner=owner)
        if not par:
            return None

        # pending_action_result is one-shot; remove it once consumed.
        exec_state.pop("pending_action_result", None)

        # Clear legacy/compat fields that can re-trigger confirm flows.
        exec_state.pop("pending_confirmation", None)
        exec_state.pop("confirm_table", None)

        # NOTE: Do NOT delete pending_action_last by default; it is useful for debugging/telemetry.
        # If you want to cap size, do so in persistence, not here.

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
        reason: Optional[str] = None,
    ) -> None:
        """
        Convenience wrapper to create a confirm_yes_no pending action.
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
        Migration helper:
          - prefer step
          - fallback legacy pending_action/status
          - block confirm_table/pending_confirmation
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
    # Internals
    # ---------------------------------------------------------------------

    def _ensure_wizard_step_after_yes(self, exec_state: Dict[str, Any]) -> None:
        """
        Minimal healing: if wizard exists and step is missing/invalid, set a safe step.
        With your CrudWizard, "confirm" is a safe post-gate step.
        """
        wiz = exec_state.get("wizard")
        if not isinstance(wiz, dict) or not wiz:
            return

        step = str(wiz.get("step") or "").strip().lower()
        if step in {"collect_details", "confirm", "execute", "done", "cancelled"}:
            return

        wiz2 = dict(wiz)
        wiz2["step"] = "confirm"
        exec_state["wizard"] = wiz2

    def _clear_stale_outputs(self, exec_state: Dict[str, Any]) -> None:
        """
        Prevent stale confirm prompts / answers from being re-emitted on the next turn
        by clearing common output fields when we consume a protocol gate.
        """
        for k in self._STALE_OUTPUT_KEYS:
            exec_state.pop(k, None)

    def _is_confirm_yes_no_awaiting(self, pa: Any) -> bool:
        """
        Strict gate:
          - must be dict-like
          - type must be confirm_yes_no
          - awaiting must be boolean True (not truthy strings)
          - pending_question must be non-empty
        """
        if not isinstance(pa, dict):
            return False
        if pa.get("type") != "confirm_yes_no":
            return False
        if pa.get("awaiting") is not True:
            return False
        pq = pa.get("pending_question")
        return isinstance(pq, str) and bool(pq.strip())

    def _set_pending_action_result(
        self,
        exec_state: Dict[str, Any],
        *,
        owner: str,
        decision: Decision,
        context: Dict[str, Any],
        resume_route: str,
        resume_pattern: str,
        pending_question: str,
    ) -> None:
        owner_norm = self._norm_owner(owner)
        d: Decision = decision if decision in {"yes", "no", "cancel"} else "cancel"
        key = f"confirm_yes_no:{owner_norm}:{d}"

        exec_state["pending_action_result"] = {
            "type": "confirm_yes_no",
            "owner": owner_norm,
            "decision": d,
            "context": dict(context or {}),
            "key": key,
            "resume_route": self._norm_route(resume_route) or "data_query",
            "resume_pattern": self._norm_route(resume_pattern) or (self._norm_route(resume_route) or "data_query"),
            "pending_question": (pending_question or "").strip(),
        }

    def _consume_pending_action(self, exec_state: Dict[str, Any], *, reason: str) -> None:
        """
        Consume the gate in a way that:
          - prevents merge-resurrection (we keep an object)
          - prevents downstream code from treating "pending_action exists" as "still pending"
            by changing type to a cleared marker
        """
        r = (reason or "").strip() or "cleared"

        pa = exec_state.get("pending_action")
        if isinstance(pa, dict):
            last = dict(pa)
            last["awaiting"] = False
            last["cleared_reason"] = r
            # IMPORTANT: once cleared, it must no longer look like an active confirm gate.
            # This prevents "has_pending_action = bool(exec_state['pending_action'])" style bugs.
            last["type"] = f"cleared:{pa.get('type') or 'unknown'}"
            exec_state["pending_action_last"] = last
            exec_state["pending_action"] = last
        else:
            tombstone = {"type": "cleared:unknown", "awaiting": False, "cleared_reason": r}
            exec_state["pending_action_last"] = tombstone
            exec_state["pending_action"] = tombstone

        exec_state["pending_action_cleared_reason"] = r

        # Clear legacy fields that can re-trigger confirm flows.
        exec_state.pop("pending_confirmation", None)
        exec_state.pop("confirm_table", None)

    # Normalization helpers
    def _norm(self, s: str) -> str:
        t = (s or "").strip().lower()
        return t.strip(" \t\r\n.!?;,:()[]{}\"'")

    def _norm_owner(self, x: Any) -> str:
        return str(x or "").strip().lower() or "unknown"

    def _norm_route(self, x: Any) -> str:
        return str(x or "").strip().lower()

    # Token parsing
    def _is_yes(self, s: str) -> bool:
        t = self._norm(s)
        return t in self.YES_TOKENS or t.startswith("yes ")

    def _is_no(self, s: str) -> bool:
        t = self._norm(s)
        return t in self.NO_TOKENS or t.startswith("no ")

    def _is_cancel(self, s: str) -> bool:
        t = self._norm(s)
        return t in self.CANCEL_TOKENS or t.startswith(("cancel ", "stop ", "quit "))
