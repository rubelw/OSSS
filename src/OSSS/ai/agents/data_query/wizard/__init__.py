
from __future__ import annotations

from typing import Any, Dict, List, Optional

from OSSS.ai.context import AgentContext
from OSSS.ai.observability import get_logger
from OSSS.ai.agents.data_query.wizard_config import (
    WizardConfig,
    get_wizard_config_for_collection,
)

logger = get_logger(__name__)


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
    """Human‑readable summary used in confirmation messages."""
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
# Main flow
# ---------------------------------------------------------------------------


async def continue_wizard(
    agent_name: str,
    context: AgentContext,
    wizard_state: Dict[str, Any],
    user_text: str,
) -> AgentContext:
    """Port of the previous DataQueryAgent._continue_wizard method.

    This function is intentionally generic so it can be reused by any agent
    that wants a simple multi‑turn "CRUD wizard" UX.
    """
    collection = wizard_state.get("collection")
    channel_key = wizard_channel_key(agent_name, collection)
    pending_action = wizard_state.get("pending_action")
    payload: Dict[str, Any] = wizard_state.get("payload") or {}

    # ---------------------------------------------------------------------
    # TABLE NAME CONFIRMATION STEP (first turn of CRUD wizards)
    # ---------------------------------------------------------------------
    if pending_action == "confirm_table":
        operation = (wizard_state.get("operation") or "create").lower()
        base_url = wizard_state.get("base_url")
        entity_meta: Dict[str, Any] = wizard_state.get("entity_meta") or {}

        table_name = (
            wizard_state.get("table_name")
            or entity_meta.get("table")
            or collection
            or entity_meta.get("topic_key")
            or "unknown_table"
        )

        answer_raw = (user_text or "").strip()
        answer_lower = answer_raw.lower()

        cancel_tokens = {"cancel", "stop", "never mind", "nevermind", "abort", "exit", "quit"}
        if answer_lower in cancel_tokens:
            set_wizard_state(context, None)
            context.add_agent_output(
                agent_name=channel_key,
                logical_name=agent_name,
                content="Okay, I won’t start this wizard right now.",
                role="assistant",
                meta={
                    "action": "wizard",
                    "step": "cancelled",
                    "collection": collection,
                    "operation": operation,
                    "reason": "user_cancelled_at_table_confirm",
                },
                action="wizard_cancelled",
                intent="action",
            )
            return context

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

        if not answer_raw or answer_lower in yes_tokens:
            final_table = table_name
        else:
            final_table = answer_raw

        entity_meta["table"] = final_table
        wizard_state["table_name"] = final_table
        wizard_state["entity_meta"] = entity_meta

        thank_you_msg = (
            f"Thank you — I’ll use the `{final_table}` table for this {operation} operation."
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

        # CREATE → proceed into field‑collection wizard
        if operation == "create":
            cfg = get_wizard_config_for_collection(collection)
            if not cfg:
                set_wizard_state(context, None)
                context.add_agent_output(
                    agent_name=channel_key,
                    logical_name=agent_name,
                    content=(
                        "However, I don’t have a wizard configuration for this collection yet, "
                        "so I can’t collect the fields automatically."
                    ),
                    role="assistant",
                    meta={
                        "action": "wizard",
                        "step": "error",
                        "collection": collection,
                        "operation": operation,
                    },
                    action="wizard_error",
                    intent="action",
                )
                return context

            payload = {
                "source": "ai_data_query",
                "base_url": base_url,
                "entity_id": entity_meta.get("id"),
                "collection": collection,
            }

            missing = _wizard_missing_fields(payload, cfg)
            next_field_name = missing[0] if missing else None

            new_state: Dict[str, Any] = {
                "pending_action": "collect",
                "payload": payload,
                "collection": collection,
                "current_field": next_field_name,
                "route_info": wizard_state.get("route_info") or {},
            }
            set_wizard_state(context, new_state)

            if next_field_name:
                field_cfg = cfg.field_by_name(next_field_name)
                if field_cfg and field_cfg.prompt:
                    prompt = field_cfg.prompt
                else:
                    prompt = f"Please provide {field_cfg.label if field_cfg else next_field_name}."

                meta_block = {
                    "action": "wizard",
                    "step": "collect_field",
                    "collection": collection,
                    "current_field": next_field_name,
                    "missing_fields": missing,
                }

                context.add_agent_output(
                    agent_name=channel_key,
                    logical_name=agent_name,
                    content="To get started, I just need a few details.\n\n" + prompt,
                    role="assistant",
                    meta=meta_block,
                    action="wizard_step",
                    intent="action",
                )
                return context

            # Everything pre‑filled → go straight to confirm
            summary = _summarize_wizard_payload(payload, cfg)
            new_state["pending_action"] = "confirm"
            set_wizard_state(context, new_state)

            meta_block = {
                "action": "wizard",
                "step": "confirm",
                "collection": collection,
            }

            context.add_agent_output(
                agent_name=channel_key,
                logical_name=agent_name,
                content=(
                    "Here’s the record I’m ready to create:\n\n"
                    f"{summary}\n\n"
                    "Type 'confirm' to save this record or 'cancel' to abort."
                ),
                role="assistant",
                meta=meta_block,
                action="wizard_step",
                intent="action",
            )
            return context

        # UPDATE / DELETE → stub message then end
        set_wizard_state(context, None)

        if operation == "update":
            stub_message = (
                f"[STUB] I would now start an **UPDATE** wizard for table `{final_table}`.\n\n"
                "In a full implementation, the next steps would be:\n"
                "1. Ask which record(s) to update.\n"
                "2. Ask which fields to change and their new values.\n\n"
                "This is currently a stub, so no data has been changed."
            )
        else:
            stub_message = (
                f"[STUB] I would now start a **DELETE** wizard for table `{final_table}`.\n\n"
                "In a full implementation, the next steps would be:\n"
                "1. Ask which record(s) to delete.\n"
                "2. Ask you to confirm the deletion.\n\n"
                "This is currently a stub, so no data has been changed."
            )

        exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}
        payload_stub: Dict[str, Any] = {
            "ok": True,
            "source": "wizard_stub",
            "operation": operation,
            "collection": collection,
            "entity": entity_meta,
            "base_url": wizard_state.get("base_url"),
            "route": wizard_state.get("route_info") or {},
            "message": stub_message,
        }

        key_collection = collection or "unknown_collection"
        exec_state[f"{key_collection}_{operation}_wizard_stub"] = payload_stub
        context.execution_state = exec_state

        structured = exec_state.setdefault("structured_outputs", {})
        structured[channel_key] = payload_stub
        if not isinstance(structured.get(agent_name), dict):
            structured[agent_name] = payload_stub

        context.add_agent_output(
            agent_name=channel_key,
            logical_name=agent_name,
            content=stub_message,
            role="assistant",
            meta=payload_stub,
            action=operation,
            intent="action",
        )
        return context

    # ---------------------------------------------------------------------
    # Traditional create‑wizard flow (collect / confirm)
    # ---------------------------------------------------------------------
    cfg = get_wizard_config_for_collection(collection)
    if not cfg:
        set_wizard_state(context, None)
        context.add_agent_output(
            agent_name=channel_key,
            logical_name=agent_name,
            content="Sorry, I’m missing the configuration for this wizard.",
            role="assistant",
            meta={
                "action": "wizard",
                "step": "error",
                "collection": collection,
            },
            action="wizard_error",
            intent="action",
        )
        return context

    # CONFIRMATION
    if pending_action == "confirm":
        answer = (user_text or "").strip().lower()
        logger.info(
            "[wizard] confirmation step",
            extra={
                "event": "wizard_confirm",
                "collection": collection,
                "answer": answer,
            },
        )

        if answer in {"yes", "y", "confirm", "ok", "okay"}:
            exec_state = getattr(context, "execution_state", {}) or {}
            if collection:
                exec_state[f"{collection}_create_ready"] = payload
            context.execution_state = exec_state

            set_wizard_state(context, None)
            summary = _summarize_wizard_payload(payload, cfg)

            meta_block = {
                "action": "wizard",
                "step": "confirmed",
                "collection": collection,
            }

            context.add_agent_output(
                agent_name=channel_key,
                logical_name=agent_name,
                content=(
                    "Great, I’ve collected everything needed:\n\n"
                    f"{summary}\n\n"
                    "The payload is ready for creation in the backend."
                ),
                role="assistant",
                meta=meta_block,
                action="wizard_confirmed",
                intent="action",
            )
            return context

        # User cancelled
        set_wizard_state(context, None)
        context.add_agent_output(
            agent_name=channel_key,
            logical_name=agent_name,
            content="Okay, I won’t create this record.",
            role="assistant",
            meta={
                "action": "wizard",
                "step": "cancelled",
                "collection": collection,
            },
            action="wizard_cancelled",
            intent="action",
        )
        return context

    # FIELD COLLECTION
    current_field_name = wizard_state.get("current_field")
    if not current_field_name:
        missing = _wizard_missing_fields(payload, cfg)
        current_field_name = missing[0] if missing else None
        wizard_state["current_field"] = current_field_name
        set_wizard_state(context, wizard_state)

    field_cfg = cfg.field_by_name(current_field_name) if current_field_name else None

    logger.info(
        "[wizard] collecting field",
        extra={
            "event": "wizard_collect_field",
            "collection": collection,
            "current_field": current_field_name,
            "user_text": user_text,
        },
    )

    answer = (user_text or "").strip()

    if field_cfg:
        if field_cfg.normalizer:
            value = field_cfg.normalizer(answer)
        else:
            if (
                not field_cfg.required
                and field_cfg.name in {"notes", "comment", "comments"}
                and answer.lower() in {"no", "none"}
            ):
                value = ""
            elif not answer and field_cfg.default_value is not None:
                value = field_cfg.default_value
            else:
                value = answer
        payload[field_cfg.name] = value
    else:
        if current_field_name:
            payload[current_field_name] = answer

    wizard_state["payload"] = payload

    # Recompute missing required fields
    missing = _wizard_missing_fields(payload, cfg)

    if missing:
        next_field_name = missing[0]
        next_field_cfg = cfg.field_by_name(next_field_name)
        wizard_state["current_field"] = next_field_name
        wizard_state["pending_action"] = "collect"
        set_wizard_state(context, wizard_state)

        if next_field_cfg and next_field_cfg.prompt:
            prompt = next_field_cfg.prompt
        else:
            prompt = f"Please provide {next_field_cfg.label if next_field_cfg else next_field_name}."

        meta_block = {
            "action": "wizard",
            "step": "collect_field",
            "collection": collection,
            "current_field": next_field_name,
            "missing_fields": missing,
        }

        context.add_agent_output(
            agent_name=channel_key,
            logical_name=agent_name,
            content=prompt,
            role="assistant",
            meta=meta_block,
            action="wizard_step",
            intent="action",
        )
        return context

    # All required fields present → move to confirmation
    wizard_state["pending_action"] = "confirm"
    wizard_state["current_field"] = None
    set_wizard_state(context, wizard_state)

    summary = _summarize_wizard_payload(payload, cfg)
    meta_block = {
        "action": "wizard",
        "step": "confirm",
        "collection": collection,
    }

    context.add_agent_output(
        agent_name=channel_key,
        logical_name=agent_name,
        content=(
            "Here’s the record I’m ready to create:\n\n"
            f"{summary}\n\n"
            "Type 'confirm' to save this record, or 'cancel' to abort."
        ),
        role="assistant",
        meta=meta_block,
        action="wizard_confirm",
        intent="action",
    )
    return context
