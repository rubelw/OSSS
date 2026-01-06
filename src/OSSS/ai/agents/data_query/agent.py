# OSSS/ai/agents/data_query/agent.py
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncEngine

from OSSS.ai.context import AgentContext
from OSSS.ai.agents.base_agent import BaseAgent
from OSSS.ai.agents.data_query.config import DataQueryRoute
from OSSS.ai.agents.data_query.query_metadata import DEFAULT_QUERY_SPECS
from OSSS.ai.agents.data_query.utils import (
    _looks_like_database_query,
    _get_classifier_and_text_from_context,
)
from OSSS.ai.services.nl_to_sql_service import NLToSQLService
from OSSS.ai.observability import get_logger

# ✅ new best-practice wizard
from OSSS.ai.agents.data_query.wizard.crud_wizard import CrudWizard, WizardResult

logger = get_logger(__name__)

DEFAULT_BASE_URL = os.getenv("OSSS_BACKEND_BASE_URL", "http://app:8000")


def _safe_text(x: Any) -> str:
    if isinstance(x, str):
        return x.strip()
    return str(x or "").strip()


def _truthy(x: Any) -> bool:
    if isinstance(x, bool):
        return x
    if isinstance(x, (int, float)):
        return x != 0
    if isinstance(x, str):
        return x.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(x)


def _get_wizard(exec_state: Dict[str, Any]) -> Dict[str, Any]:
    w = exec_state.get("wizard")
    return w if isinstance(w, dict) else {}


def _set_wizard(exec_state: Dict[str, Any], wiz: Dict[str, Any]) -> None:
    exec_state["wizard"] = dict(wiz or {})
    exec_state["wizard_in_progress"] = bool(wiz)


def _consume_detail_reply(exec_state: Dict[str, Any]) -> str:
    """
    TurnNormalizer should stash the user's freeform wizard reply in one of these keys.
    We consume once (one-turn semantics).
    """
    for k in ("wizard_user_reply_text", "wizard_user_reply", "wizard_reply"):
        v = exec_state.get(k)
        if isinstance(v, str) and v.strip():
            # clear all related keys after consuming
            exec_state.pop("wizard_user_reply_text", None)
            exec_state.pop("wizard_user_reply", None)
            exec_state.pop("wizard_reply", None)
            exec_state["wizard_user_reply_consumed"] = True
            return v.strip()
    return ""


def _guess_table_name(*, topic: str | None, raw_text_lower: str) -> str:
    """
    Best-effort table guess:
    - try DataQueryRoute registry/list (if exposed)
    - fall back to DEFAULT_QUERY_SPECS scan
    """
    topic_l = (topic or "").strip().lower()

    # If DataQueryRoute exposes collections/topics, exact match wins
    try:
        for attr in ("collections", "topics", "available_collections", "available_topics"):
            vals = getattr(DataQueryRoute, attr, None)
            if isinstance(vals, (list, tuple, set)) and topic_l:
                lowered = {str(v).strip().lower() for v in vals}
                if topic_l in lowered:
                    return topic_l
    except Exception:
        pass

    # Reflective lookups if your DataQueryRoute supports them
    try:
        for attr in ("get", "lookup", "for_topic", "resolve", "from_topic"):
            fn = getattr(DataQueryRoute, attr, None)
            if callable(fn) and topic_l:
                route = fn(topic_l)
                if route:
                    for key in ("collection", "view_name", "store_key", "table_name", "name", "topic"):
                        val = getattr(route, key, None) if not isinstance(route, dict) else route.get(key)
                        if isinstance(val, str) and val.strip():
                            return val.strip().lower()
    except Exception:
        pass

    # DEFAULT_QUERY_SPECS scan
    for spec in (DEFAULT_QUERY_SPECS or []):
        try:
            name = str(getattr(spec, "name", "") or spec.get("name") or "").strip()
            store_key = str(getattr(spec, "store_key", "") or spec.get("store_key") or "").strip()
        except Exception:
            continue

        if topic_l and (topic_l == name.lower() or topic_l == store_key.lower()):
            return (store_key or name).strip().lower()

        if name and name.lower() in raw_text_lower:
            return (store_key or name).strip().lower()

        if store_key and store_key.lower() in raw_text_lower:
            return store_key.strip().lower()

    return (topic_l or "unknown_table").strip().lower()


class DataQueryAgent(BaseAgent):
    """
    Best-practice DataQueryAgent that delegates multi-turn control to CrudWizard.

    - Wizard state: exec_state["wizard"]
    - Protocol state: exec_state["pending_action"] (+ pending_action_result)
    - Agent: initializes wizard if needed, runs wizard, executes deterministic plan if requested
    """

    name = "data_query"

    def __init__(
        self,
        *,
        data_query: Optional[Dict[str, Any]] = None,
        pg_engine: Optional[AsyncEngine] = None,
    ):
        super().__init__(name=self.name, timeout_seconds=20.0)
        self.data_query = data_query or {}
        self.pg_engine = pg_engine
        self._nl_to_sql_service = NLToSQLService()
        self._wizard = CrudWizard()

    async def run(self, context: AgentContext) -> AgentContext:
        exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}

        # One-turn flags must not leak
        exec_state.pop("wizard_prompted_this_turn", None)

        classifier, initial_effective_text = _get_classifier_and_text_from_context(context)
        if not isinstance(classifier, dict):
            classifier = {}

        raw_user_input = _safe_text(getattr(context, "query", "")) or _safe_text(exec_state.get("user_question"))
        effective_text = _safe_text(raw_user_input or initial_effective_text)
        raw_text_lower = effective_text.lower()

        # Persist original_query once
        if not _safe_text(exec_state.get("original_query")) and raw_user_input:
            exec_state["original_query"] = raw_user_input

        # ----------------------------
        # 1) Wizard bootstrap if missing AND request looks like DB intent
        # ----------------------------
        wiz = _get_wizard(exec_state)
        if not wiz:
            force = _looks_like_database_query(effective_text) or raw_text_lower.startswith("query ")
            if not force:
                context.execution_state = exec_state
                return context

            topic = _safe_text((exec_state.get("classifier") or {}).get("topic") or classifier.get("topic")).lower()
            table = _guess_table_name(topic=topic, raw_text_lower=raw_text_lower)

            wiz = {
                "operation": "read",
                "original_query": _safe_text(exec_state.get("original_query") or raw_user_input or effective_text),
                "step": "collect_details",  # wizard will validate / advance
                "table_name": table,
                "collection": table,
                "entity_meta": {"table": table},
                "route_info": {"route": self.name},
                "base_url": _safe_text(os.getenv("OSSS_BACKEND_BASE_URL", DEFAULT_BASE_URL)),
                "confirmed": None,  # critical: confirm step depends on tri-state
            }
            _set_wizard(exec_state, wiz)

        # If TurnNormalizer stashed a detail reply, keep it in exec_state for wizard plan
        # (Wizard will read wizard_user_reply_text|wizard_user_reply in _build_execute_plan)
        # We do NOT overwrite user's effective_text here; wizard consumes stash itself.
        # But we DO want to ensure the stash exists for collect_details/execute.
        # (No-op: we just leave it in exec_state.)

        # ----------------------------
        # 2) Run wizard (mutates exec_state["wizard"] + may set pending_action)
        # ----------------------------
        result: WizardResult = self._wizard.run(exec_state)

        # Always keep context in sync after wizard mutation
        context.execution_state = exec_state

        # ----------------------------
        # 3) Interpret wizard result
        # ----------------------------
        if result.status == "prompt":
            prompt = _safe_text(result.prompt) or "Okay — what should I do next?"
            exec_state["final"] = prompt
            exec_state["wizard_prompted_this_turn"] = True
            exec_state["suppress_history"] = False  # prompt is user-visible
            context.execution_state = exec_state
            return context

        if result.status == "cancelled":
            exec_state["final"] = _safe_text(result.prompt) or "Okay — cancelled."
            exec_state["wizard_in_progress"] = False
            context.execution_state = exec_state
            return context

        if result.status == "done":
            # Wizard says complete; if you want to keep last results, you can.
            exec_state.setdefault("final", "Done.")
            context.execution_state = exec_state
            return context

        if result.status == "noop":
            # Nothing to do; keep flowing
            context.execution_state = exec_state
            return context

        if result.status != "execute":
            # Defensive fallback
            exec_state["final"] = "I’m not sure what to do next."
            context.execution_state = exec_state
            return context

        # ----------------------------
        # 4) Execute deterministic plan (no wizard/protocol logic here)
        # ----------------------------
        plan = result.plan or {}
        op = _safe_text(plan.get("operation") or "read").lower()
        table_name = _safe_text(plan.get("table_name") or plan.get("collection") or "")
        base_url = _safe_text(plan.get("base_url") or DEFAULT_BASE_URL)

        # If you use HTTP backend CRUD, do it here.
        # If you translate to SQL, do it here.
        # Below is a placeholder that you should replace with your actual execution path.

        try:
            # Example: NLToSQLService usage (placeholder)
            # sql = await self._nl_to_sql_service.to_sql(...)
            # rows = await self._nl_to_sql_service.execute(...)
            # exec_state["data_query_result"] = rows

            exec_state["data_query_plan"] = plan
            exec_state["data_query_result"] = {
                "ok": True,
                "operation": op,
                "table": table_name,
                "base_url": base_url,
                "note": "Execution placeholder: wire your actual HTTP/SQL executor here.",
            }

            exec_state["final"] = f"Executed {op.upper()} on `{table_name}`."
            context.execution_state = exec_state
            return context

        except Exception as e:
            logger.exception("data_query_execute_failed", extra={"event": "data_query_execute_failed"})
            exec_state["errors"] = (exec_state.get("errors") or []) + [str(e)]
            exec_state["final"] = f"Execution failed: {type(e).__name__}: {e}"
            context.execution_state = exec_state
            return context
