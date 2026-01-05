# OSSS/ai/orchestration/routers/helpers.py
from __future__ import annotations

from typing import Any, Dict


def get_exec_state(state: Any) -> Dict[str, Any]:
    """
    Normalize whatever the graph/router receives into the execution_state dict.

    Supported inputs:
      - plain dict state (langgraph state)
      - dict containing {"execution_state": {...}}
      - AgentContext-like objects with .execution_state or .get("execution_state")
    """
    if state is None:
        return {}

    # If we already got an execution_state-like dict
    if isinstance(state, dict):
        es = state.get("execution_state")
        if isinstance(es, dict):
            return es
        # Sometimes the state dict itself is the exec_state
        return state

    # AgentContext-like: attribute
    es = getattr(state, "execution_state", None)
    if isinstance(es, dict):
        return es

    # AgentContext-like: mapping interface
    try:
        es2 = state.get("execution_state")  # type: ignore[attr-defined]
        if isinstance(es2, dict):
            return es2
    except Exception:
        pass

    return {}


def truthy(value: Any) -> bool:
    """
    Interpret common "truthy" encodings robustly.

    This exists because router modules often import `truthy` from here.

    Examples treated as True:
      - True, 1, "1", "true", "yes", "y", "on", "t"
    Examples treated as False:
      - False, 0, "0", "false", "no", "n", "off", "f", "", None
    """
    if value is None:
        return False

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value != 0

    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"1", "true", "yes", "y", "on", "t"}:
            return True
        if v in {"0", "false", "no", "n", "off", "f", ""}:
            return False
        # Non-empty, unknown string -> treat as True (conservative)
        return True

    # Fallback: python truthiness
    try:
        return bool(value)
    except Exception:
        return False


def get_query_profile(state: Any) -> Dict[str, Any]:
    """
    Compatibility shim: some routers import get_query_profile() from this module.

    Returns a small, stable "query profile" derived from execution_state that
    routers can use for branching decisions without hard-coupling to other services.
    """
    es = get_exec_state(state)

    raw = (
        es.get("query")
        or es.get("question")
        or es.get("user_question")
        or es.get("raw_user_text")
        or ""
    )
    text = str(raw or "").strip()
    lowered = text.lower()

    is_query_prefix = lowered.startswith("query ")
    is_sqlish = lowered.startswith(("select ", "show ", "describe "))

    classifier = es.get("classifier") or es.get("classifier_profile") or {}
    intent = ""
    try:
        intent = str((classifier or {}).get("intent") or "").lower()
    except Exception:
        intent = ""

    return {
        "text": text,
        "intent": intent,
        "is_query_prefix": is_query_prefix,
        "is_sqlish": is_sqlish,
        "looks_like_db_query": bool(is_query_prefix or is_sqlish or intent == "action"),
    }
