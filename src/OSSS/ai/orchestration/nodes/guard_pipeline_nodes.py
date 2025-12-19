# OSSS/ai/orchestration/advanced_nodes/guard_pipeline_nodes.py

from __future__ import annotations

from typing import Any, Dict, Optional
from datetime import datetime, timezone

from OSSS.ai.observability import get_logger
from OSSS.ai.agents.metadata import AgentMetadata
from OSSS.ai.orchestration.advanced_nodes.base import BaseAdvancedNode, NodeExecutionContext


logger = get_logger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(x: Any) -> str:
    return "" if x is None else str(x)


class AnswerSearchNode(BaseAdvancedNode):
    """
    Executes the "real work": answer and/or search. In your system this would call
    your DCG personnel lookup / web search / internal DB retrieval, etc.
    """

    async def execute(self, context: NodeExecutionContext) -> Dict[str, Any]:
        # Inputs: original query typically stored in execution_metadata or available_inputs
        query = _safe_str(context.execution_metadata.get("query") or context.available_inputs.get("query"))
        if not query:
            # fallback: let it run but return a safe diagnostic payload
            return {
                "ok": False,
                "type": "answer_search",
                "error": "missing_query",
                "answer_text": "",
                "sources": [],
                "ts": _now_iso(),
            }

        # TODO: replace this stub with your actual “answer/search” logic.
        # Example shape:
        answer_text = f"(stub) I would answer/search for: {query}"
        sources = []  # e.g. [{"title": "...", "url": "..."}]

        return {
            "ok": True,
            "type": "answer_search",
            "answer_text": answer_text,
            "sources": sources,
            "ts": _now_iso(),
        }

    def can_handle(self, context: NodeExecutionContext) -> bool:
        # If guard allowed, we can handle. You can tighten this.
        return True


class FormatResponseNode(BaseAdvancedNode):
    """
    Formats an allowed response for the UI.
    """

    async def execute(self, context: NodeExecutionContext) -> Dict[str, Any]:
        # Expect AnswerSearch output in available_inputs
        answer_payload = context.available_inputs.get("answer_search") or {}
        answer_text = _safe_str(answer_payload.get("answer_text"))
        sources = answer_payload.get("sources") or []

        # A simple UI payload shape; adapt to your front-end contract
        ui = {
            "status": "ok",
            "message": answer_text,
            "sources": sources,
            "ts": _now_iso(),
        }

        return {"ok": True, "type": "format_response", "ui": ui}

    def can_handle(self, context: NodeExecutionContext) -> bool:
        return True


class FormatBlockNode(BaseAdvancedNode):
    """
    Formats a blocked response for the UI (guard denied).
    """

    async def execute(self, context: NodeExecutionContext) -> Dict[str, Any]:
        guard = context.available_inputs.get("guard") or {}
        safe_response = _safe_str(guard.get("safe_response")) or "Sorry, I can’t help with that request."

        ui = {
            "status": "blocked",
            "message": safe_response,
            "ts": _now_iso(),
        }
        return {"ok": True, "type": "format_block", "ui": ui}

    def can_handle(self, context: NodeExecutionContext) -> bool:
        return True


class FormatRequiresConfirmationNode(BaseAdvancedNode):
    """
    Formats a “requires confirmation” response for the UI.
    """

    async def execute(self, context: NodeExecutionContext) -> Dict[str, Any]:
        guard = context.available_inputs.get("guard") or {}
        reason = _safe_str(guard.get("reason")) or "This action requires confirmation."

        ui = {
            "status": "requires_confirmation",
            "message": reason,
            "ts": _now_iso(),
        }
        return {"ok": True, "type": "format_requires_confirmation", "ui": ui}

    def can_handle(self, context: NodeExecutionContext) -> bool:
        return True


# --- convenience constructors (metadata examples) ---

def _meta(node_name: str, pattern: str) -> AgentMetadata:
    """
    If your AgentMetadata requires different fields, adjust this helper.
    """
    return AgentMetadata(
        name=node_name,
        execution_pattern=pattern,
        cognitive_speed="fast",
        cognitive_depth="shallow",
        processing_pattern="deterministic",
        pipeline_role="orchestration",
        bounded_context="ai",
        capabilities=[node_name],
    )


def build_answer_search_node() -> AnswerSearchNode:
    return AnswerSearchNode(metadata=_meta("answer_search", "processor"), node_name="answer_search")


def build_format_response_node() -> FormatResponseNode:
    return FormatResponseNode(metadata=_meta("format_response", "terminator"), node_name="format_response")


def build_format_block_node() -> FormatBlockNode:
    return FormatBlockNode(metadata=_meta("format_block", "terminator"), node_name="format_block")


def build_format_requires_confirmation_node() -> FormatRequiresConfirmationNode:
    return FormatRequiresConfirmationNode(
        metadata=_meta("format_requires_confirmation", "terminator"),
        node_name="format_requires_confirmation",
    )
