from __future__ import annotations

from typing import Any, Dict, Optional

from OSSS.ai.context import AgentContext
from OSSS.ai.observability import get_logger
from OSSS.ai.agents.data_query.wizard import utils

logger = get_logger(__name__)

# If JSON_PATH lives in utils, wire it through here
try:
    JSON_PATH = utils.JSON_PATH
except AttributeError:
    JSON_PATH = "$.data"


# ---------------------------------------------------------------------------
# MODULE-LEVEL WIZARD HELPERS (expected by DataQueryAgent)
#
# Option B (post-migration / step-only):
# - CrudWizard reads ONLY wizard_state["step"].
# - Legacy keys (pending_action/status) are NOT read here anymore.
# - confirm_table/pending_confirmation are NOT wizard steps; if they appear
#   in wizard_state["step"], treat as invalid/no-op.
# - During the migration window, DataQueryAgent (TurnController) is the only
#   place that heals legacy fields -> wizard_state["step"].
# ---------------------------------------------------------------------------


def wizard_channel_key(agent_name: str, collection: Optional[str] = None) -> str:
    """Single logical channel for wizard UX, optionally namespaced by collection."""
    if collection:
        return f"{agent_name}:wizard:{collection}"
    return f"{agent_name}:wizard"


def get_wizard_state(context: AgentContext) -> Dict[str, Any]:
    """Read wizard state from execution_state."""
    exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}
    wiz = exec_state.get("wizard") or {}
    return wiz if isinstance(wiz, dict) else {}


def set_wizard_state(context: AgentContext, state: Optional[Dict[str, Any]]) -> None:
    """Write (or clear) wizard state on execution_state."""
    exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}
    if state:
        exec_state["wizard"] = state
    else:
        exec_state.pop("wizard", None)
    context.execution_state = exec_state


async def continue_wizard(
    agent_name: str,
    context: AgentContext,
    wizard_state: Dict[str, Any],
    user_text: str,
) -> AgentContext:
    """
    Backwards-compatible entrypoint used by DataQueryAgent.
    """
    wizard = CrudWizard(agent_name=agent_name, context=context, wizard_state=wizard_state)
    return await wizard.handle(user_text)


CANCEL_HINT = (
    "\n\nYou can type **cancel** at any time to end this workflow "
    "and return to a blank prompt."
)


class CrudWizard:
    """
    CRUD wizard stub for read, create, update, and delete.

    Option B (post-migration / step-only):
      - confirm_table / pending_confirmation are NOT wizard steps.
      - Wizard reads ONLY wizard_state["step"].
      - Wizard only handles real steps like collect_details.
    """

    CANCEL_TOKENS = {
        "cancel",
        "stop",
        "never mind",
        "nevermind",
        "abort",
        "exit",
        "quit",
    }

    INVALID_STATES = {"confirm_table", "pending_confirmation"}

    def __init__(
        self,
        agent_name: str,
        context: AgentContext,
        wizard_state: Dict[str, Any],
    ) -> None:
        self.agent_name = agent_name
        self.context = context
        self.state: Dict[str, Any] = wizard_state or {}

        self.collection: Optional[str] = self.state.get("collection")
        self.channel_key: str = wizard_channel_key(agent_name, self.collection)

        operation_raw = str(self.state.get("operation") or "read").strip().lower()
        self.operation = "read" if operation_raw == "query" else operation_raw

    # ---------------- normalization ----------------

    def _canon(self, s: str) -> str:
        t = (s or "").strip().lower()
        return t.strip(" \t\r\n.!?;,:()[]{}\"'")

    # ---------------- protocol contract helpers ----------------

    def _get_exec_state(self) -> Dict[str, Any]:
        return getattr(self.context, "execution_state", {}) or {}

    def _clear_pending_action_contract(self, exec_state: Dict[str, Any], *, reason: str) -> None:
        """
        Safety net: clear protocol-level pending action contract.

        IMPORTANT DESIGN RULE:
        - DO NOT delete pending_action. Keep it with awaiting=False so merges
          cannot resurrect an older awaiting=True action.
        """
        pa = exec_state.get("pending_action")
        if isinstance(pa, dict):
            pa_done = dict(pa)
            pa_done["awaiting"] = False
            pa_done["cleared_reason"] = reason

            # snapshot (optional but useful for debugging)
            exec_state["pending_action_last"] = pa_done

            # keep the object, but ensure awaiting is false + reason is recorded
            exec_state["pending_action"] = pa_done

        # pending_action_result is one-shot; safe to remove (for this owner only)
        par = exec_state.get("pending_action_result")
        if isinstance(par, dict):
            owner = str(par.get("owner") or "").strip().lower()
            if owner == str(self.agent_name or "").strip().lower():
                exec_state.pop("pending_action_result", None)

    # ---------------- step sourcing (step-only) ----------------

    def _get_pending_step(self) -> str:
        """
        Step-only: read ONLY wizard_state["step"].
        Legacy keys (pending_action/status) are not read here anymore.
        """
        step = self.state.get("step") if isinstance(self.state, dict) else ""
        return str(step or "").strip().lower()

    # ------------------------ public entrypoint -----------------------------

    async def handle(self, user_text: str) -> AgentContext:
        """
        Main entrypoint: route to the correct step based on wizard_state["step"].

        Option B:
          - If confirm_table shows up in wizard_state["step"], it is invalid.
            Log and return context unchanged. Do NOT interpret yes/no.
        """
        answer_raw = (user_text or "").strip()
        answer_lower = self._canon(answer_raw)

        # Global cancel handler
        if self._is_cancel(answer_lower):
            return self._handle_cancel(answer_raw)

        pending = self._get_pending_step()

        # confirm_table/pending_confirmation are protocol-only (no-op if leaked in)
        if pending in self.INVALID_STATES:
            logger.warning(
                "[wizard] invalid wizard_state.step: confirm_table/pending_confirmation are protocol-only. No-op.",
                extra={
                    "event": "wizard_invalid_state_confirm_table",
                    "collection": self.collection,
                    "operation": self.operation,
                    "pending": pending,
                    "wizard_keys": list(self.state.keys()) if isinstance(self.state, dict) else [],
                    "user_text_preview": answer_raw[:160],
                },
            )
            return self.context

        if pending == "collect_details":
            return self._handle_collect_details(answer_raw)

        # Unknown step → graceful cancel
        return self._handle_unknown(pending=pending)

    # ------------------------ internal helpers -----------------------------

    @classmethod
    def _is_cancel(cls, answer_lower: str) -> bool:
        return (answer_lower or "").strip().lower() in cls.CANCEL_TOKENS

    # ---------------------------------------------------------------------
    # CANCEL HANDLER
    # ---------------------------------------------------------------------

    def _handle_cancel(self, answer_raw: str) -> AgentContext:
        logger.info(
            "[wizard] user cancelled wizard",
            extra={
                "event": "wizard_user_cancel",
                "collection": self.collection,
                "operation": self.operation,
                "pending": self._get_pending_step(),
            },
        )

        exec_state = self._get_exec_state()

        exec_state["wizard_cancelled"] = True
        exec_state["wizard_bailed"] = True
        exec_state["wizard_bail_reason"] = "user_cancelled_wizard"

        # Clear protocol contract (safety) — keep pending_action with awaiting=False
        self._clear_pending_action_contract(exec_state, reason="wizard_cancelled")

        exec_state["suppress_history"] = True

        cancel_message = "Okay — I cancelled this CRUD wizard. No changes were made."
        exec_state["final_answer"] = cancel_message
        self.context.execution_state = exec_state

        set_wizard_state(self.context, None)

        self.context.add_agent_output(
            agent_name=self.channel_key,
            logical_name=self.agent_name,
            content=cancel_message,
            role="assistant",
            meta={
                "action": "wizard",
                "step": "cancelled",
                "collection": self.collection,
                "operation": self.operation,
                "reason": "user_cancelled",
                "pending": self._get_pending_step(),
            },
            action="wizard_cancelled",
            intent="action",
        )
        return self.context

    # ---------------------------------------------------------------------
    # DETAILS COLLECTION STEP
    # ---------------------------------------------------------------------

    def _handle_collect_details(self, answer_raw: str) -> AgentContext:
        details_text = answer_raw

        exec_state = self._get_exec_state()
        table_name = (
            self.state.get("table_name")
            or (self.state.get("entity_meta") or {}).get("table")
            or self.collection
            or "unknown_table"
        )
        entity_meta: Dict[str, Any] = self.state.get("entity_meta") or {}

        payload_stub: Dict[str, Any] = {
            "ok": True,
            "source": "wizard_stub",
            "operation": self.operation,
            "collection": self.collection,
            "table_name": table_name,
            "entity": entity_meta,
            "base_url": self.state.get("base_url"),
            "route": self.state.get("route_info") or {},
            "details_text": details_text,
        }

        key_collection = self.collection or "unknown_collection"
        exec_state[f"{key_collection}_{self.operation}_wizard_stub"] = payload_stub
        self.context.execution_state = exec_state

        structured = exec_state.setdefault("structured_outputs", {})
        structured[self.channel_key] = payload_stub
        if not isinstance(structured.get(self.agent_name), dict):
            structured[self.agent_name] = payload_stub

        if self.operation == "read":
            stub_message = (
                f"[STUB] I’ve captured your **READ/QUERY** request for `{table_name}`.\n\n"
                "Here’s what I understood about the filters/conditions you want:\n\n"
                f"> {details_text or '_(no additional filters specified_)'}\n\n"
                "In a full implementation, I would now translate this into query parameters, "
                "call the backend API, and show you the matching rows."
            )
        elif self.operation == "create":
            stub_message = (
                f"[STUB] I’ve captured your **CREATE** request for `{table_name}`.\n\n"
                "Here’s the record description you provided:\n\n"
                f"> {details_text or '_(no field details specified_)'}\n\n"
                "In a full implementation, I would now build a JSON payload and POST it to the backend."
            )
        elif self.operation == "update":
            stub_message = (
                f"[STUB] I’ve captured your **UPDATE** request for `{table_name}`.\n\n"
                "Here’s how you described the records and changes:\n\n"
                f"> {details_text or '_(no update details specified_)'}\n\n"
                "In a full implementation, I would now construct an update payload and "
                "send it to the backend API."
            )
        elif self.operation == "delete":
            stub_message = (
                f"[STUB] I’ve captured your **DELETE** request for `{table_name}`.\n\n"
                "Here’s how you described the records to delete:\n\n"
                f"> {details_text or '_(no delete criteria specified_)'}\n\n"
                "In a full implementation, I would now construct a delete request and "
                "send it to the backend API after an explicit confirmation."
            )
        else:
            stub_message = (
                f"[STUB] I’ve captured your request for `{table_name}` with operation `{self.operation}`.\n\n"
                "Details:\n\n"
                f"> {details_text or '_(no details specified_)'}\n\n"
                "In a full implementation, I would now translate this into a backend call."
            )

        stub_message = stub_message + CANCEL_HINT

        self.context.add_agent_output(
            agent_name=self.channel_key,
            logical_name=self.agent_name,
            content=stub_message,
            role="assistant",
            meta=payload_stub,
            action=self.operation,
            intent="action",
        )

        # Wizard ends here: clear wizard state and protocol contract (safety)
        exec_state = self._get_exec_state()
        self._clear_pending_action_contract(exec_state, reason="wizard_completed")
        self.context.execution_state = exec_state

        set_wizard_state(self.context, None)
        return self.context

    # ---------------------------------------------------------------------
    # Fallback: unknown step → cancel with error
    # ---------------------------------------------------------------------

    def _handle_unknown(self, *, pending: str) -> AgentContext:
        logger.warning(
            "[wizard] unknown wizard step; cancelling wizard",
            extra={
                "event": "wizard_unknown_step",
                "pending": pending,
                "collection": self.collection,
                "operation": self.operation,
            },
        )

        exec_state = self._get_exec_state()
        exec_state["wizard_bailed"] = True
        exec_state["wizard_bail_reason"] = "unknown_wizard_step"

        self._clear_pending_action_contract(exec_state, reason="wizard_unknown_step")
        self.context.execution_state = exec_state

        set_wizard_state(self.context, None)
        self.context.add_agent_output(
            agent_name=self.channel_key,
            logical_name=self.agent_name,
            content=(
                "Sorry, I lost track of this CRUD wizard’s state, so I’ve cancelled it. "
                "You can start again with a new query if you like."
            ),
            role="assistant",
            meta={
                "action": "wizard",
                "step": "error",
                "collection": self.collection,
                "operation": self.operation,
                "pending": pending,
            },
            action="wizard_error",
            intent="action",
        )
        return self.context

