from __future__ import annotations

from typing import Any, Dict, List, Optional

from OSSS.ai.context import AgentContext
from OSSS.ai.observability import get_logger
from OSSS.ai.agents.data_query.wizard_config import (
    WizardConfig,
    get_wizard_config_for_collection,
)

logger = get_logger(__name__)

# Shared hint text used in prompts and stub summaries.
CANCEL_HINT = (
    "\n\nYou can type **cancel** at any time to end this workflow "
    "and return to a blank prompt."
)


def _wizard_missing_fields(payload: Dict[str, Any], cfg: WizardConfig) -> List[str]:
    """Compute which required fields are still missing in the wizard payload."""
    missing: List[str] = []
    for field in cfg.fields:
        if not field.required:
            continue
        value = payload.get(field.name)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field.name)
    return missing


def _summarize_wizard_payload(payload: Dict[str, Any], cfg: WizardConfig) -> str:
    """Human-readable summary used in confirmation messages."""
    lines: List[str] = []
    for field in cfg.fields:
        label = field.summary_label or field.label or field.name
        value = payload.get(field.name)

        if value is None or (isinstance(value, str) and not value.strip()):
            if field.required:
                value_str = "_not set_"
            else:
                value_str = field.default_value if field.default_value is not None else "none"
        else:
            value_str = value

        lines.append(f"- **{label}**: {value_str}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------


def get_wizard_state(context: AgentContext) -> Optional[Dict[str, Any]]:
    exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}
    return exec_state.get("wizard")  # returns dict or None


def set_wizard_state(context: AgentContext, state: Optional[Dict[str, Any]]) -> None:
    exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}
    if state:
        exec_state["wizard"] = state
    else:
        exec_state.pop("wizard", None)
    context.execution_state = exec_state


def wizard_channel_key(agent_name: str, collection: Optional[str] = None) -> str:
    if collection:
        return f"{agent_name}:wizard:{collection}"
    return f"{agent_name}:wizard"


# ---------------------------------------------------------------------------
# Main flow (3-turn CRUD wizard stub for read/create/update/delete)
# ---------------------------------------------------------------------------


async def continue_wizard(
    agent_name: str,
    context: AgentContext,
    wizard_state: Dict[str, Any],
    user_text: str,
) -> AgentContext:
    """3-turn CRUD wizard stub for read, create, update, and delete.

    Turn 1 (already handled by DataQueryAgent.run):
        - Initialize wizard_state with pending_action="confirm_table".
        - Ask: "Is this the correct table?"

    Turn 2 (here, pending_action == "confirm_table"):
        - User confirms or overrides table name.
        - Wizard:
            * stores final table name
            * sends a short “thanks” message
            * asks an operation-specific question
            * sets pending_action="collect_details"

    Turn 3 (here, pending_action == "collect_details"):
        - User provides free-form details (filters, fields, ids, etc.).
        - Wizard:
            * stores a stub payload in execution_state + structured_outputs
            * emits a stub summary explaining what would happen
            * clears wizard_state

    Users can type "cancel" (or similar) at ANY step to abort and clear wizard,
    returning to a blank prompt.
    """
    collection = wizard_state.get("collection")
    channel_key = wizard_channel_key(agent_name, collection)
    pending_action = wizard_state.get("pending_action")
    payload: Dict[str, Any] = wizard_state.get("payload") or {}

    # Normalize operation; treat "read" and "query" as read-style wizards.
    operation_raw = (wizard_state.get("operation") or "read").strip().lower()
    if operation_raw == "query":
        operation = "read"
    else:
        operation = operation_raw

    # ---------------------------------------------------------------------
    # GLOBAL CANCEL HANDLER (applies to all steps)
    # ---------------------------------------------------------------------
    answer_raw = (user_text or "").strip()
    answer_lower = answer_raw.lower()

    cancel_tokens = {
        "cancel",
        "stop",
        "never mind",
        "nevermind",
        "abort",
        "exit",
        "quit",
    }

    if answer_lower in cancel_tokens:
        logger.info(
            "[wizard] user cancelled wizard",
            extra={
                "event": "wizard_user_cancel",
                "collection": collection,
                "operation": operation,
                "pending_action": pending_action,
            },
        )

        # --- NEW: mark cancellation in execution_state for orchestration_api/UI ---
        exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}
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
        context.execution_state = exec_state
        # --- END NEW ---

        # Clear wizard state so future messages are fresh.
        set_wizard_state(context, None)

        context.add_agent_output(
            agent_name=channel_key,
            logical_name=agent_name,
            content=cancel_message,
            role="assistant",
            meta={
                "action": "wizard",
                "step": "cancelled",
                "collection": collection,
                "operation": operation,
                "reason": "user_cancelled",
                "pending_action": pending_action,
            },
            action="wizard_cancelled",
            intent="action",
        )
        return context

    # ---------------------------------------------------------------------
    # TABLE NAME CONFIRMATION STEP (Turn 2)
    # ---------------------------------------------------------------------
    if pending_action == "confirm_table":
        logger.info("Is confirm_table action")
        base_url = wizard_state.get("base_url")
        entity_meta: Dict[str, Any] = wizard_state.get("entity_meta") or {}

        table_name = (
            wizard_state.get("table_name")
            or entity_meta.get("table")
            or collection
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
        wizard_state["table_name"] = final_table
        wizard_state["entity_meta"] = entity_meta

        thank_you_msg = (
            f"Thanks — I’ll use the `{final_table}` table for this **{operation.upper()}** operation."
            f"{CANCEL_HINT}"
        )

        context.add_agent_output(
            agent_name=channel_key,
            logical_name=agent_name,
            content=thank_you_msg,
            role="assistant",
            meta={
                "action": "wizard",
                "step": "table_confirmed",
                "collection": collection,
                "operation": operation,
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
            "collection": collection,
            "table_name": final_table,
            "operation": operation,
            "entity": entity_meta,
        }
        wizard_state["payload"] = payload
        wizard_state["pending_action"] = "collect_details"

        logger.info("operation is: "+str(operation))

        # Operation-specific follow-up prompt (Turn 3)
        if operation == "read":
            details_prompt = (
                "What filters or conditions should I use when querying this table?\n\n"
                "For example, you can mention columns, statuses, or date ranges. "
                "_(This is a stub: I’ll just summarize your answer instead of actually running the query.)_"
            )
        elif operation == "create":
            details_prompt = (
                "What fields and values should the new record have?\n\n"
                "For example: `student_id`, `consent_type`, `granted = yes`, etc.\n"
                "_(This is a stub: I’ll just summarize the record instead of creating it.)_"
            )
        elif operation == "update":
            details_prompt = (
                "Which record(s) should I update, and what fields or values should change?\n\n"
                "You can describe an ID, a filter, and the fields to modify.\n"
                "_(This is a stub: I’ll summarize the update but won’t change any data.)_"
            )
        elif operation == "delete":
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
            "collection": collection,
            "operation": operation,
            "table_name": final_table,
        }

        set_wizard_state(context, wizard_state)

        context.add_agent_output(
            agent_name=channel_key,
            logical_name=agent_name,
            content=details_prompt,
            role="assistant",
            meta=meta_block,
            action="wizard_step",
            intent="action",
        )
        return context

    # ---------------------------------------------------------------------
    # DETAILS COLLECTION STEP (Turn 3)
    # ---------------------------------------------------------------------
    if pending_action == "collect_details":
        details_text = answer_raw

        exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}
        table_name = (
            wizard_state.get("table_name")
            or (wizard_state.get("entity_meta") or {}).get("table")
            or collection
            or "unknown_table"
        )
        entity_meta: Dict[str, Any] = wizard_state.get("entity_meta") or {}

        # Build a stub payload that other components can inspect.
        payload_stub: Dict[str, Any] = {
            "ok": True,
            "source": "wizard_stub",
            "operation": operation,
            "collection": collection,
            "table_name": table_name,
            "entity": entity_meta,
            "base_url": wizard_state.get("base_url"),
            "route": wizard_state.get("route_info") or {},
            "details_text": details_text,
        }

        key_collection = collection or "unknown_collection"
        exec_state[f"{key_collection}_{operation}_wizard_stub"] = payload_stub
        context.execution_state = exec_state

        structured = exec_state.setdefault("structured_outputs", {})
        structured[channel_key] = payload_stub
        if not isinstance(structured.get(agent_name), dict):
            structured[agent_name] = payload_stub

        # Operation-specific stub summary message.
        if operation == "read":
            stub_message = (
                f"[STUB] I’ve captured your **READ/QUERY** request for `{table_name}`.\n\n"
                "Here’s what I understood about the filters/conditions you want:\n\n"
                f"> {details_text or '_(no additional filters specified_)'}\n\n"
                "In a full implementation, I would now translate this into query parameters, "
                "call the backend API, and show you the matching rows."
            )
        elif operation == "create":
            stub_message = (
                f"[STUB] I’ve captured your **CREATE** request for `{table_name}`.\n\n"
                "Here’s the record description you provided:\n\n"
                f"> {details_text or '_(no field details specified_)'}\n\n"
                "In a full implementation, I would now build a JSON payload and POST it to the backend."
            )
        elif operation == "update":
            stub_message = (
                f"[STUB] I’ve captured your **UPDATE** request for `{table_name}`.\n\n"
                "Here’s how you described the records and changes:\n\n"
                f"> {details_text or '_(no update details specified_)'}\n\n"
                "In a full implementation, I would now construct an update payload and "
                "send it to the backend API."
            )
        elif operation == "delete":
            stub_message = (
                f"[STUB] I’ve captured your **DELETE** request for `{table_name}`.\n\n"
                "Here’s how you described the records to delete:\n\n"
                f"> {details_text or '_(no delete criteria specified_)'}\n\n"
                "In a full implementation, I would now construct a delete request and "
                "send it to the backend API after an explicit confirmation."
            )
        else:
            stub_message = (
                f"[STUB] I’ve captured your request for `{table_name}` with operation `{operation}`.\n\n"
                "Details:\n\n"
                f"> {details_text or '_(no details specified_)'}\n\n"
                "In a full implementation, I would now translate this into a backend call."
            )

        # Append cancel hint to the stub summary (even though the wizard ends,
        # this keeps the UX consistent with the other messages).
        stub_message = stub_message + CANCEL_HINT

        context.add_agent_output(
            agent_name=channel_key,
            logical_name=agent_name,
            content=stub_message,
            role="assistant",
            meta=payload_stub,
            action=operation,
            intent="action",
        )

        # End the wizard after 3rd turn.
        set_wizard_state(context, None)
        return context

    # ---------------------------------------------------------------------
    # Fallback: unknown pending_action → cancel with error
    # ---------------------------------------------------------------------
    logger.warning(
        "[wizard] unknown pending_action; cancelling wizard",
        extra={
            "event": "wizard_unknown_pending_action",
            "pending_action": pending_action,
            "collection": collection,
            "operation": operation,
        },
    )

    set_wizard_state(context, None)
    context.add_agent_output(
        agent_name=channel_key,
        logical_name=agent_name,
        content=(
            "Sorry, I lost track of this CRUD wizard’s state, so I’ve cancelled it. "
            "You can start again with a new query if you like."
        ),
        role="assistant",
        meta={
            "action": "wizard",
            "step": "error",
            "collection": collection,
            "operation": operation,
            "pending_action": pending_action,
        },
        action="wizard_error",
        intent="action",
    )
    return context
