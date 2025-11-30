# OSSS/ai/agents/query_data/query_data_registry.py
from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List, Protocol

from OSSS.ai.agents.base import AgentContext

FetchResult = Dict[str, Any]  # same idea as before: rows + extras


class QueryHandler(Protocol):
    mode: str
    keywords: List[str]  # text patterns for fallback (optional)
    source_label: str

    async def fetch(self, ctx: AgentContext, skip: int, limit: int) -> FetchResult: ...
    def to_markdown(self, rows: List[Dict[str, Any]]) -> str: ...
    def to_csv(self, rows: List[Dict[str, Any]]) -> str: ...


_HANDLERS: Dict[str, QueryHandler] = {}
_KEYWORD_INDEX: Dict[str, str] = {}  # "live scoring" -> "live_scorings"


def register_handler(handler: QueryHandler) -> None:
    """Register a dataset handler under its mode."""
    _HANDLERS[handler.mode] = handler
    for kw in handler.keywords:
        _KEYWORD_INDEX[kw.lower()] = handler.mode


def get_handler(mode: str) -> QueryHandler | None:
    return _HANDLERS.get(mode)


def iter_handlers() -> Dict[str, QueryHandler].items:
    return _HANDLERS.items()


def detect_mode_from_context(ctx: AgentContext, fallback_mode: str = "students") -> str:
    """Use classifier metadata + keyword index to pick a handler."""
    q = (ctx.query or "").lower()

    # 1) classifier metadata
    raw = ctx.metadata.get("intent_raw_model_output") if ctx.metadata else None
    meta_mode: str | None = None
    if isinstance(raw, str):
        import json, logging

        logger = logging.getLogger("OSSS.ai.agents.query_data.registry")
        try:
            obj = json.loads(raw)
            heuristic_rule = obj.get("heuristic_rule") or {}
            metadata = heuristic_rule.get("metadata") or {}
            meta_mode = metadata.get("mode")
        except Exception:
            logger.exception("Failed to parse intent_raw_model_output", exc_info=True)

    if meta_mode and meta_mode in _HANDLERS:
        return meta_mode

    # 2) keywords
    for kw, mode in _KEYWORD_INDEX.items():
        if kw in q:
            return mode

    # 3) fallback
    return fallback_mode
