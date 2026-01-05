"""
State mutation helpers (single source of truth for entry_* + legacy route_*).
"""

from __future__ import annotations

from typing import Any, Dict

from .heuristics import should_route_to_data_query


def apply_db_query_routing(execution_state: Dict[str, Any], user_text: str) -> None:
    """
    Apply DB-query routing decision to execution_state.

    Safe behavior:
    - If already route_locked, do nothing (honor existing lock).
    - If should_route_to_data_query(...) is false, do nothing.
    """
    if execution_state.get("route_locked"):
        return

    decision = should_route_to_data_query(user_text, execution_state)
    if not decision:
        return

    execution_state["entry_target"] = "data_query"
    execution_state["entry_locked"] = True
    execution_state["entry_reason"] = "db_query_heuristic"

    execution_state["route"] = "data_query"
    execution_state["route_locked"] = True
    execution_state["route_reason"] = "db_query_heuristic"
