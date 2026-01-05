"""
Pure heuristics for DB-query detection and historian enablement.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from OSSS.ai.observability import get_logger

from .constants import (
    _WORD_RE,
    ACTION_HINTS,
    DB_TABLES,
    DISTRICT_ALIASES,
    HISTORY_TRIGGERS,
    SCHOOL_ENTITIES,
)

logger = get_logger(__name__)


def should_route_to_data_query(
    user_text: str,
    execution_state: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Heuristic to decide if a user request should bypass refiner/critic/synthesis
    and go directly to data_query.

    Can optionally use classifier output from execution_state (if provided)
    to strengthen DB-query detection.
    """
    try:
        t = (user_text or "").lower()
        tokens = set(_WORD_RE.findall(t))

        classifier_profile: Dict[str, Any] = {}
        intent = ""
        domain = ""
        query_terms: List[str] = []

        if execution_state:
            classifier_profile = execution_state.get("classifier_profile") or {}
            intent = (classifier_profile.get("intent") or "").lower()
            domain = (classifier_profile.get("domain") or "").lower()
            query_terms = classifier_profile.get("query_terms") or []

        if not query_terms:
            query_terms = list(tokens)

        has_db_table = bool(
            DB_TABLES.intersection({term.lower() for term in query_terms}) or DB_TABLES.intersection(tokens)
        )
        has_district = bool(tokens.intersection(DISTRICT_ALIASES))
        has_school_entity = bool(tokens.intersection(SCHOOL_ENTITIES))

        has_query_prefix = t.startswith("query ")
        has_database_keyword = " database" in t or " db " in t

        crud_intents = {"create", "read", "update", "delete", "list", "action"}
        data_domains = {"data_systems", "data_query", "wizard", "crud"}

        has_action_intent = bool(intent in crud_intents and domain in data_domains)

        has_action_hint = bool(
            ACTION_HINTS.search(t) or has_action_intent or has_query_prefix or has_database_keyword
        )

        if has_db_table:
            decision = True
            reason = "has_db_table"
        elif has_district and has_school_entity:
            decision = True
            reason = "district_plus_entity"
        elif has_action_hint and has_school_entity:
            decision = True
            reason = "action_hint_plus_entity"
        elif has_query_prefix or has_database_keyword or has_action_intent:
            decision = True
            reason = "query_or_database_or_action_intent"
        else:
            decision = False
            reason = "no_db_query_signals"

        logger.debug(
            "Evaluated should_route_to_data_query",
            extra={
                "event": "routing_decision",
                "router": "should_route_to_data_query",
                "decision": decision,
                "reason": reason,
                "has_db_table": has_db_table,
                "has_district_alias": has_district,
                "has_school_entity": has_school_entity,
                "has_action_hint": has_action_hint,
                "has_query_prefix": has_query_prefix,
                "has_database_keyword": has_database_keyword,
                "has_action_intent": has_action_intent,
                "classifier_intent": intent or None,
                "classifier_domain": domain or None,
                "sample_query": t[:256],
            },
        )
        return decision

    except Exception as exc:
        logger.error(
            "Error while evaluating should_route_to_data_query",
            exc_info=True,
            extra={
                "event": "routing_decision_error",
                "router": "should_route_to_data_query",
                "error_type": type(exc).__name__,
            },
        )
        return False


def should_run_historian(query: str) -> bool:
    q = (query or "").strip()
    try:
        if should_route_to_data_query(q):
            logger.debug(
                "Historian disabled due to DB query heuristic",
                extra={
                    "event": "routing_historian_decision",
                    "decision": False,
                    "reason": "db_query_short_circuit",
                    "query_len": len(q),
                },
            )
            return False

        if len(q) < 40:
            logger.debug(
                "Historian disabled for short query",
                extra={
                    "event": "routing_historian_decision",
                    "decision": False,
                    "reason": "short_query",
                    "query_len": len(q),
                },
            )
            return False

        if HISTORY_TRIGGERS.search(q):
            logger.debug(
                "Historian enabled due to explicit historical trigger",
                extra={
                    "event": "routing_historian_decision",
                    "decision": True,
                    "reason": "history_trigger",
                    "query_len": len(q),
                },
            )
            return True

        ql = q.lower()
        if "notes" in ql or "docs" in ql:
            logger.debug(
                "Historian enabled due to notes/docs mention",
                extra={
                    "event": "routing_historian_decision",
                    "decision": True,
                    "reason": "notes_or_docs",
                    "query_len": len(q),
                },
            )
            return True

        logger.debug(
            "Historian disabled (no triggers matched)",
            extra={
                "event": "routing_historian_decision",
                "decision": False,
                "reason": "no_triggers",
                "query_len": len(q),
            },
        )
        return False

    except Exception as exc:
        logger.error(
            "Error while evaluating should_run_historian",
            exc_info=True,
            extra={"event": "routing_historian_error", "error_type": type(exc).__name__},
        )
        return False
