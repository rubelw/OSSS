# OSSS/ai/agents/query_data/query_data_registry.py
from __future__ import annotations

from typing import Any, Dict, List, Protocol
import json
import logging

from OSSS.ai.agents.base import AgentContext

FetchResult = Dict[str, Any]  # rows + extras

logger = logging.getLogger("OSSS.ai.agents.query_data.registry")


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

    logger.info(
        "QueryData: registered handler mode=%s keywords=%s",
        handler.mode,
        handler.keywords,
    )


def get_handler(mode: str) -> QueryHandler | None:
    return _HANDLERS.get(mode)


def iter_handlers():
    return _HANDLERS.items()


def _mode_from_intent_raw_model_output(raw: str | None) -> str | None:
    """
    Extract a mode from the intent_raw_model_output JSON payload.

    Handles both:
      - heuristic_rule.metadata.mode
      - llm.action (e.g. 'show_materials_list')
    """
    if not isinstance(raw, str):
        return None

    try:
        obj = json.loads(raw)
    except Exception:
        logger.exception("Failed to parse intent_raw_model_output JSON", exc_info=True)
        return None

    logger.debug("QueryData: intent_raw_model_output obj=%s", obj)

    # 1) heuristic_rule.metadata.mode (if a heuristic fired)
    heuristic_rule = obj.get("heuristic_rule") or {}
    metadata = heuristic_rule.get("metadata") or {}
    meta_mode = metadata.get("mode")

    if meta_mode:
        logger.info("QueryData: mode from heuristic metadata: %s", meta_mode)
        return meta_mode

    # 2) llm.action (your LLM classifier payload)
    llm = obj.get("llm") or {}
    action = (llm.get("action") or "").lower()

    logger.info("QueryData: llm.action=%r from intent_raw_model_output", action)

    # Map specific actions to modes
    if action == "show_materials_list":
        return "materials"
    if action in {"scorecards", "show_scorecards", "list_scorecards"}:
        return "scorecards"
    if action in {"live_scoring_query", "show_live_scores", "show_live_scoring"}:
        return "live_scorings"

    return None


def detect_mode_from_context(ctx: AgentContext, fallback_mode: str = "students") -> str:
    """
    Use classifier metadata + keyword index + simple lexical heuristics
    to pick a handler.

    Priority:
      1) intent_raw_model_output → heuristic metadata.mode or llm.action
      2) direct lexical heuristics on ctx.query (e.g. "materials list")
      3) keyword index (_KEYWORD_INDEX)
      4) fallback_mode (if registered)
      5) first registered handler
      6) literal "students" as last-resort default
    """
    q = (ctx.query or "")
    q_lower = q.lower()

    logger.info(
        "QueryData: detect_mode_from_context query=%r metadata_keys=%s handlers=%s",
        q,
        list((ctx.metadata or {}).keys()),
        list(_HANDLERS.keys()),
    )

    # ------------------------------------------------------------------
    # 1) From intent_raw_model_output (heuristics + llm.action)
    # ------------------------------------------------------------------
    raw = ctx.metadata.get("intent_raw_model_output") if ctx.metadata else None
    meta_mode = _mode_from_intent_raw_model_output(raw)

    if meta_mode:
        if meta_mode in _HANDLERS:
            logger.info(
                "QueryData: using mode_from_metadata=%s (handler exists)",
                meta_mode,
            )
            return meta_mode
        else:
            logger.warning(
                "QueryData: mode_from_metadata=%s but no handler registered; "
                "will fall through to other heuristics",
                meta_mode,
            )

    # ------------------------------------------------------------------
    # 2) Direct text heuristics on the raw query
    # ------------------------------------------------------------------
    # Materials (your failing case)
    if ("materials list" in q_lower or "material list" in q_lower or "materials" in q_lower):
        if "materials" in _HANDLERS:
            logger.info("QueryData: direct heuristic matched 'materials*' -> mode=materials")
            return "materials"

    # Scorecards
    if "scorecard" in q_lower or "scorecards" in q_lower:
        if "scorecards" in _HANDLERS:
            logger.info("QueryData: direct heuristic matched 'scorecard*' -> mode=scorecards")
            return "scorecards"

    # Live scoring
    if (
        "live scoring" in q_lower
        or "live score" in q_lower
        or "live scores" in q_lower
        or "live game" in q_lower
    ):
        if "live_scorings" in _HANDLERS:
            logger.info("QueryData: direct heuristic matched 'live scoring*' -> mode=live_scorings")
            return "live_scorings"

    # ------------------------------------------------------------------
    # 3) Keyword index fallback
    # ------------------------------------------------------------------
    for kw, mode in _KEYWORD_INDEX.items():
        if kw in q_lower and mode in _HANDLERS:
            logger.info("QueryData: keyword '%s' matched mode=%s", kw, mode)
            return mode

    # ------------------------------------------------------------------
    # 4) fallback_mode if registered
    # ------------------------------------------------------------------
    if fallback_mode in _HANDLERS:
        logger.info("QueryData: using fallback_mode=%s", fallback_mode)
        return fallback_mode

    # ------------------------------------------------------------------
    # 5) Any registered handler as a last reasonable fallback
    # ------------------------------------------------------------------
    if _HANDLERS:
        first_mode = next(iter(_HANDLERS.keys()))
        logger.warning(
            "QueryData: fallback_mode=%s not registered; using first registered mode=%s",
            fallback_mode,
            first_mode,
        )
        return first_mode

    # ------------------------------------------------------------------
    # 6) Absolute last resort
    # ------------------------------------------------------------------
    logger.error("QueryData: no handlers registered; defaulting to 'students'")
    return "students"
