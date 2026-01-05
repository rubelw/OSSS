from __future__ import annotations
from typing import Any, Dict, Optional

from .types import WizardNormalizationResult

_TRUE = {"1", "true", "t", "yes", "y", "on"}

def truthy(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v.strip().lower() in _TRUE
    return bool(v)

def get_wizard_state(execution_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    ws = execution_state.get("wizard") or execution_state.get("wizard_state")
    return ws if isinstance(ws, dict) else None

def is_wizard_in_progress(
    wizard_state: Optional[Dict[str, Any]],
    *,
    conversation_id_explicit: bool,
    wizard_bailed: bool,
) -> bool:
    if not conversation_id_explicit or wizard_bailed or not isinstance(wizard_state, dict):
        return False
    op = (wizard_state.get("operation") or "").lower()
    pending = (wizard_state.get("pending_action") or "").lower()
    is_crud_op = op in {"read", "create", "update", "delete", "list"}
    is_pending = pending not in {"", "done", "complete", "completed", "end", "cancel", "cancelled"}
    return bool(is_crud_op and is_pending)

def normalize_wizard_query(
    *,
    request_query: str,
    execution_state: Dict[str, Any],
    conversation_id: str,
    conversation_id_explicit: bool,
) -> WizardNormalizationResult:
    q = (request_query or "").strip()
    wizard_state = get_wizard_state(execution_state)

    wizard_bailed = truthy(execution_state.get("wizard_bailed")) or (
        truthy(wizard_state.get("bailed")) if wizard_state else False
    )

    patch: Dict[str, Any] = {
        "conversation_id": execution_state.get("conversation_id") or conversation_id,
        "wizard_bailed": bool(wizard_bailed),
    }

    # Preserve original query for auditing/debug
    if q:
        patch.setdefault("original_query", execution_state.get("original_query") or q)
        patch.setdefault("user_question", execution_state.get("user_question") or q)

    # If no explicit conversation, we do not attempt "resume" semantics
    if not conversation_id_explicit:
        effective = q
        in_progress = False
        patch["effective_queries"] = {"user": effective} if effective else {"user": ""}
        return WizardNormalizationResult(
            effective_query=effective,
            wizard_bailed=bool(wizard_bailed),
            wizard_in_progress=in_progress,
            patch=patch,
            wizard_state=wizard_state,
        )

    # Resume query sources (keep permissive)
    resume_query = None
    if wizard_state:
        resume_query = (
            wizard_state.get("resume_query")
            or wizard_state.get("query")
            or wizard_state.get("user_query")
        )
    if not resume_query:
        resume_query = execution_state.get("resume_query")

    if isinstance(resume_query, str) and resume_query.strip() and not wizard_bailed:
        patch["resume_query"] = resume_query.strip()

    if wizard_bailed and q:
        patch.setdefault("wizard_bail_original_query", execution_state.get("wizard_bail_original_query") or q)

    # Decide effective query using your precedence order
    effective = (
        patch.get("resume_query")
        or patch.get("wizard_bail_original_query")
        or patch.get("original_query")
        or patch.get("user_question")
        or q
    )
    effective = (effective or "").strip()

    patch["question"] = effective
    patch["query"] = effective
    patch["user_question"] = effective
    patch.setdefault("raw_user_text", effective)
    patch.setdefault("effective_queries", {"user": effective})

    in_progress = is_wizard_in_progress(
        wizard_state,
        conversation_id_explicit=conversation_id_explicit,
        wizard_bailed=bool(wizard_bailed),
    )

    return WizardNormalizationResult(
        effective_query=effective,
        wizard_bailed=bool(wizard_bailed),
        wizard_in_progress=in_progress,
        patch=patch,
        wizard_state=wizard_state,
    )
