from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from OSSS.ai.context import AgentContext
from OSSS.ai.observability import get_logger
from OSSS.ai.agents.data_query.wizard import utils

logger = get_logger(__name__)

# If JSON_PATH lives in utils, wire it through here
try:
    JSON_PATH = utils.JSON_PATH
except AttributeError:
    # Fallback so we don't crash if it's missing; adjust as needed
    JSON_PATH = "$.data"

# ---------------------------------------------------------------------------
# MODULE-LEVEL WIZARD HELPERS (expected by DataQueryAgent)
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

    Delegates to CrudWizard but keeps the old import/usage pattern:
      from ...crud_wizard import continue_wizard, get_wizard_state, set_wizard_state, ...
    """
    wizard = CrudWizard(agent_name=agent_name, context=context, wizard_state=wizard_state)
    return await wizard.handle(user_text)


# ---------------------------------------------------------------------------
# Shared hint text used in prompts and stub summaries.
# ---------------------------------------------------------------------------

CANCEL_HINT = (
    "\n\nYou can type **cancel** at any time to end this workflow "
    "and return to a blank prompt."
)


class CrudWizard:
    """
    3-turn CRUD wizard stub for read, create, update, and delete.
    (class body unchanged, see below)
    """

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
        # ✅ use module-level helper so it's consistent with DataQueryAgent
        self.channel_key: str = wizard_channel_key(agent_name, self.collection)
        self.pending_action: Optional[str] = self.state.get("pending_action")
        operation_raw = (self.state.get("operation") or "read").strip().lower()
        self.operation = "read" if operation_raw == "query" else operation_raw

    @classmethod
    async def continue_wizard(
        cls,
        agent_name: str,
        context: AgentContext,
        wizard_state: Dict[str, Any],
        user_text: str,
    ) -> AgentContext:
        # Keep this too, but DataQueryAgent will be calling the module-level
        # continue_wizard wrapper above.
        wizard = cls(agent_name=agent_name, context=context, wizard_state=wizard_state)
        return await wizard.handle(user_text)

    # ------------------------ public entrypoint -----------------------------

    async def handle(self, user_text: str) -> AgentContext:
      """Main entrypoint: route to the correct step based on pending_action."""

      answer_raw = (user_text or "").strip()
      answer_lower = answer_raw.lower()

      # Global cancel handler
      if self._is_cancel(answer_lower):
          return self._handle_cancel(answer_raw, answer_lower)

      # Step routing
      if self.pending_action == "confirm_table":
          return self._handle_confirm_table(answer_raw, answer_lower)

      if self.pending_action == "collect_details":
          return self._handle_collect_details(answer_raw)

      # Unknown step → graceful cancel
      return self._handle_unknown()

    # ------------------------ internal helpers -----------------------------

    @staticmethod
    def _is_cancel(answer_lower: str) -> bool:
      cancel_tokens = {
          "cancel",
          "stop",
          "never mind",
          "nevermind",
          "abort",
          "exit",
          "quit",
      }
      return answer_lower in cancel_tokens

    def _get_wizard_state(self, context: AgentContext) -> Dict[str, Any]:
      exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}
      return exec_state.get("wizard") or {}

    def _set_wizard_state(self, context: AgentContext, state: Optional[Dict[str, Any]]) -> None:
      exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}
      if state:
          exec_state["wizard"] = state
      else:
          exec_state.pop("wizard", None)
      context.execution_state = exec_state

    def _wizard_channel_key(self, collection: Optional[str] = None) -> str:
      # Single logical channel for wizard UX, optionally namespaced by collection
      if collection:
          return f"{self.agent_name}:wizard:{collection}"
      return f"{self.agent_name}:wizard"


    # ---------------------------------------------------------------------
    # CANCEL HANDLER (applies to all steps)
    # ---------------------------------------------------------------------

    def _handle_cancel(self, answer_raw: str, answer_lower: str) -> AgentContext:
      logger.info(
          "[wizard] user cancelled wizard",
          extra={
              "event": "wizard_user_cancel",
              "collection": self.collection,
              "operation": self.operation,
              "pending_action": self.pending_action,
          },
      )

      # Mark cancellation in execution_state for orchestration_api/UI
      exec_state: Dict[str, Any] = getattr(self.context, "execution_state", {}) or {}
      exec_state["wizard_cancelled"] = True

      final_meta = exec_state.setdefault("final_meta", {})
      if isinstance(final_meta, dict):
          final_meta.setdefault("source", "wizard")
          final_meta["status"] = "cancelled"
          final_meta["reason"] = "user_cancelled_wizard"

      cancel_message = (
          "Okay, I’ve cancelled this CRUD wizard. No changes were made — "
          "you’re back at a blank prompt."
      )
      exec_state["final_answer"] = cancel_message
      self.context.execution_state = exec_state

      # Clear wizard state so future messages are fresh.
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
              "pending_action": self.pending_action,
          },
          action="wizard_cancelled",
          intent="action",
      )
      return self.context

    # ---------------------------------------------------------------------
    # TABLE NAME CONFIRMATION STEP (Turn 2)
    # ---------------------------------------------------------------------

    def _handle_confirm_table(self, answer_raw: str, answer_lower: str) -> AgentContext:
      logger.info("Is confirm_table action")
      base_url = self.state.get("base_url")
      entity_meta: Dict[str, Any] = self.state.get("entity_meta") or {}

      table_name = (
          self.state.get("table_name")
          or entity_meta.get("table")
          or self.collection
          or entity_meta.get("topic_key")
          or "unknown_table"
      )

      yes_tokens = {
          "yes",
          "y",
          "yeah",
          "yep",
          "correct",
          "ok",
          "okay",
          "sure",
          "that's right",
          "that is right",
      }

      # If the user just says "yes"/"ok" (or nothing), keep the proposed table.
      if not answer_raw or answer_lower in yes_tokens:
          final_table = table_name
      else:
          # Otherwise, treat their answer as a specific table name.
          final_table = answer_raw





      # Update entity metadata with the final table name.
      entity_meta["table"] = final_table
      self.state["table_name"] = final_table
      self.state["entity_meta"] = entity_meta

      thank_you_msg = (
          f"Thanks — I’ll use the `{final_table}` table for this **{self.operation.upper()}** operation."
          f"{CANCEL_HINT}"
      )

      self.context.add_agent_output(
          agent_name=self.channel_key,
          logical_name=self.agent_name,
          content=thank_you_msg,
          role="assistant",
          meta={
              "action": "wizard",
              "step": "table_confirmed",
              "collection": self.collection,
              "operation": self.operation,
              "table_name": final_table,
          },
          action="wizard_table_confirmed",
          intent="action",
      )

      # --- Turn 2: ask operation-specific follow-up and move to collect_details ---
      # Initialize a simple payload shell (for stubbing).
      payload = {
          "source": "ai_data_query_wizard_stub",
          "base_url": base_url,
          "collection": self.collection,
          "table_name": final_table,
          "operation": self.operation,
          "entity": entity_meta,
      }
      self.state["payload"] = payload
      self.state["pending_action"] = "collect_details"

      logger.info("operation is: " + str(self.operation))

      # Operation-specific follow-up prompt (Turn 3)
      if self.operation == "read":

          details_prompt = (
              f"`{self.context}` What filters or conditions should I use when querying this table?\n\n"
              "For example, you can mention columns, statuses, or date ranges. "
              "_(This is a stub: I’ll just summarize your answer instead of actually running the query.)_"
          )
      elif self.operation == "create":
          details_prompt = (
              "What fields and values should the new record have?\n\n"
              "For example: `student_id`, `consent_type`, `granted = yes`, etc.\n"
              "_(This is a stub: I’ll just summarize the record instead of creating it.)_"
          )
      elif self.operation == "update":
          details_prompt = (
              "Which record(s) should I update, and what fields or values should change?\n\n"
              "You can describe an ID, a filter, and the fields to modify.\n"
              "_(This is a stub: I’ll summarize the update but won’t change any data.)_"
          )
      elif self.operation == "delete":
          details_prompt = (
              "Which record(s) should I delete from this table?\n\n"
              "You can describe specific IDs or a filter that selects the records.\n"
              "_(This is a stub: I’ll describe the deletion but won’t actually delete anything.)_"
          )
      else:
          details_prompt = (
              "Please describe what you want to do with this table.\n\n"
              "_(This is a stub: I’ll only summarize your intent.)_"
          )

      # Append cancel hint to the details prompt.
      details_prompt = details_prompt + CANCEL_HINT

      meta_block = {
          "action": "wizard",
          "step": "collect_details",
          "collection": self.collection,
          "operation": self.operation,
          "table_name": final_table,
      }

      set_wizard_state(self.context, self.state)

      self.context.add_agent_output(
          agent_name=self.channel_key,
          logical_name=self.agent_name,
          content=details_prompt,
          role="assistant",
          meta=meta_block,
          action="wizard_step",
          intent="action",
      )
      return self.context

    # ---------------------------------------------------------------------
    # DETAILS COLLECTION STEP (Turn 3)
    # ---------------------------------------------------------------------

    def _handle_collect_details(self, answer_raw: str) -> AgentContext:
      details_text = answer_raw

      exec_state: Dict[str, Any] = getattr(self.context, "execution_state", {}) or {}
      table_name = (
          self.state.get("table_name")
          or (self.state.get("entity_meta") or {}).get("table")
          or self.collection
          or "unknown_table"
      )
      entity_meta: Dict[str, Any] = self.state.get("entity_meta") or {}

      # Build a stub payload that other components can inspect.
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

      # Operation-specific stub summary message.
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

      # Append cancel hint to the stub summary (even though the wizard ends,
      # this keeps the UX consistent with the other messages).
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

      # End the wizard after 3rd turn.
      set_wizard_state(self.context, None)
      return self.context

    # ---------------------------------------------------------------------
    # Fallback: unknown pending_action → cancel with error
    # ---------------------------------------------------------------------

    def _handle_unknown(self) -> AgentContext:
      logger.warning(
          "[wizard] unknown pending_action; cancelling wizard",
          extra={
              "event": "wizard_unknown_pending_action",
              "pending_action": self.pending_action,
              "collection": self.collection,
              "operation": self.operation,
          },
      )

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
              "pending_action": self.pending_action,
          },
          action="wizard_error",
          intent="action",
      )
      return self.context


