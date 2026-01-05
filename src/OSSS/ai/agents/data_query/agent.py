# OSSS/ai/agents/data_query/agent.py
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncEngine

from OSSS.ai.context import AgentContext
from OSSS.ai.agents.base_agent import BaseAgent
from OSSS.ai.agents.data_query.config import DataQueryRoute
from OSSS.ai.agents.data_query.queryspec import QuerySpec, FilterCondition
from OSSS.ai.agents.data_query.query_metadata import DEFAULT_QUERY_SPECS
from OSSS.ai.agents.data_query.text_filters import parse_text_filters
from OSSS.ai.services.nl_to_sql_service import NLToSQLService

from OSSS.ai.observability import get_logger

from OSSS.ai.agents.data_query.utils import (
    ExtractedTextFilters,
    _extract_text_filters_from_query,
    _looks_like_database_query,
    # ✅ NOTE: we still import the utils version for other callers, but we will
    # prefer the PR5 contract directly from execution_state in this agent.
    _extract_refined_text_from_refiner_output as _extract_refined_text_from_refiner_output_legacy,
    _get_classifier_and_text_from_context,
    _normalize_like_filter_condition,
    _extract_text_sort_from_query,
    _apply_filters_to_params,
    choose_route_for_query,
)

from OSSS.ai.agents.data_query.wizard.crud_wizard import (
    get_wizard_state,
    set_wizard_state,
    wizard_channel_key,
    CrudWizard,
)

# ✅ NEW: central protocol/turn service
from OSSS.ai.orchestration.protocol.turn_controller import TurnController

logger = get_logger(__name__)

# Single shared controller instance (stateless)
_turns = TurnController()

DEFAULT_BASE_URL = os.getenv("OSSS_BACKEND_BASE_URL", "http://app:8000")
MIN_TOPIC_CONFIDENCE = float(os.getenv("OSSS_DATAQUERY_MIN_TOPIC_CONFIDENCE", "0.15"))


# ------------------------------------------------------------------------------
# ✅ Local helper: truthy coercion (fixes "is True" round-trip issues)
# ------------------------------------------------------------------------------
def _truthy(x: Any) -> bool:
    if isinstance(x, bool):
        return x
    if isinstance(x, (int, float)):
        return x != 0
    if isinstance(x, str):
        return x.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(x)


# ------------------------------------------------------------------------------
# ✅ Local helper: choose table using DataQueryRoute registry first, then fallbacks
# ------------------------------------------------------------------------------
def _guess_table_name(
    *,
    topic: str | None,
    raw_text_lower: str,
) -> Optional[str]:
    topic_l = (topic or "").strip().lower()

    # 0) ✅ Fix 3: if classifier topic is already a known topic/collection, trust it directly.
    # This makes "query consents" reliably choose "consents" even if registry lookup APIs differ.
    try:
        for attr in ("collections", "topics", "available_collections", "available_topics"):
            vals = getattr(DataQueryRoute, attr, None)
            if isinstance(vals, (list, tuple, set)) and topic_l:
                lowered = {str(v).strip().lower() for v in vals}
                if topic_l in lowered:
                    return topic_l
    except Exception:
        pass

    # 1) ✅ Prefer DataQueryRoute registry (routes.json) because it is authoritative for topics/collections.
    # We don't know the exact API shape, so we do a few safe reflective attempts.
    try:
        # common patterns: DataQueryRoute.get(topic), .lookup(topic), .for_topic(topic), .resolve(topic)
        for attr in ("get", "lookup", "for_topic", "resolve", "from_topic"):
            fn = getattr(DataQueryRoute, attr, None)
            if callable(fn) and topic_l:
                route = fn(topic_l)  # may return DataQueryRoute or dict or None
                if route:
                    # route may have collection/view_name/store_key/table_name fields
                    for key in ("collection", "view_name", "store_key", "table_name", "name", "topic"):
                        val = getattr(route, key, None) if not isinstance(route, dict) else route.get(key)
                        if isinstance(val, str) and val.strip():
                            return val.strip()
    except Exception:
        pass

    # 1b) Try a registry/map attribute if present
    try:
        for reg_attr in ("registry", "routes", "ROUTES", "_registry", "_routes"):
            reg = getattr(DataQueryRoute, reg_attr, None)
            if isinstance(reg, dict) and topic_l:
                route = reg.get(topic_l)
                if route:
                    for key in ("collection", "view_name", "store_key", "table_name", "name"):
                        val = getattr(route, key, None) if not isinstance(route, dict) else route.get(key)
                        if isinstance(val, str) and val.strip():
                            return val.strip()
    except Exception:
        pass

    # 2) ✅ Fallback: substring scan using DataQueryRoute “topics list” if available
    try:
        # If DataQueryRoute exposes available topics/collections, scan those first.
        for attr in ("topics", "collections", "available_topics", "available_collections"):
            vals = getattr(DataQueryRoute, attr, None)
            if isinstance(vals, (list, tuple, set)):
                for t in vals:
                    t_s = str(t).strip().lower()
                    if t_s and (t_s in raw_text_lower):
                        return str(t).strip()
    except Exception:
        pass

    # 3) Legacy fallback: DEFAULT_QUERY_SPECS scan (what you already had)
    guessed_table = None
    for spec in (DEFAULT_QUERY_SPECS or []):
        try:
            name = str(getattr(spec, "name", "") or spec.get("name") or "").strip()
            store_key = str(getattr(spec, "store_key", "") or spec.get("store_key") or "").strip()
        except Exception:
            continue

        name_l = name.lower()
        store_l = store_key.lower()

        if topic_l and (topic_l == name_l or topic_l == store_l):
            guessed_table = store_key or name
            break
        if name_l and name_l in raw_text_lower:
            guessed_table = store_key or name
            break
        if store_l and store_l in raw_text_lower:
            guessed_table = store_key or name
            break

    return guessed_table


def _extract_refined_text_from_refiner_output(refiner_output: Any) -> Optional[str]:
    # New PR5 contract dict
    if isinstance(refiner_output, dict):
        rq = refiner_output.get("refined_query")
        if isinstance(rq, str) and rq.strip():
            return rq.strip()

        # if someone accidentally passed analysis_signals wrapper
        inner = refiner_output.get("analysis_signals")
        if isinstance(inner, dict):
            rq2 = inner.get("refined_query")
            if isinstance(rq2, str) and rq2.strip():
                return rq2.strip()

    # Legacy envelope / context output variants
    try:
        content = getattr(refiner_output, "content", None)
        if isinstance(content, str) and content.strip():
            return content.strip()
    except Exception:
        pass

    try:
        if isinstance(refiner_output, dict):
            # common envelope form
            content = refiner_output.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
    except Exception:
        pass

    # final fallback: attempt legacy util extractor (if it can parse the shape)
    try:
        return _extract_refined_text_from_refiner_output_legacy(refiner_output)
    except Exception:
        return None


@dataclass(frozen=True)
class DataQuerySpec:
    name: str
    store_key: str
    source: str = "http"


class DataQueryAgent(BaseAgent):
    """
    Refactored data_query agent (best-practice separation).

    ✅ Single source of truth:
      - exec_state["pending_action"] => protocol-level confirmation awaiting reply
      - exec_state["wizard"]["step"] => real wizard step (collect_details, etc.)

    Never store confirm_table / pending_confirmation in wizard_state again.
    """

    name = "data_query"
    BASE_URL = DEFAULT_BASE_URL

    # ------------------------------------------------------------------
    # ✅ Wizard access helpers (single-source-of-truth: exec_state["wizard"])
    # ------------------------------------------------------------------
    def _get_wizard(self, exec_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        w = exec_state.get("wizard")
        return w if isinstance(w, dict) else None

    def _get_wizard_step(self, exec_state: Dict[str, Any]) -> Optional[str]:
        w = self._get_wizard(exec_state) or {}
        step = w.get("step")
        if isinstance(step, str) and step.strip():
            return step.strip()
        return None

    # ------------------------------------------------------------------
    # ✅ Local helper: keep pending_action object, only flip awaiting->False
    # ------------------------------------------------------------------
    def _mark_pending_action_not_awaiting(self, exec_state: Dict[str, Any]) -> None:
        """
        Design rule: DO NOT delete pending_action on clear/consume.
        Keep it with awaiting=False so merges cannot resurrect awaiting=True.
        """
        try:
            pa = exec_state.get("pending_action")
            if isinstance(pa, dict):
                pa["awaiting"] = False
                exec_state["pending_action"] = pa
        except Exception:
            return

    # ------------------------------------------------------------------
    # ✅ Fix 2 helper: ensure pending_action carries a user-facing prompt string
    # ------------------------------------------------------------------
    def _ensure_pending_action_user_message(self, exec_state: Dict[str, Any], prompt: str) -> None:
        """
        Some layers/UI will only display "pending_action.user_message"/"prompt"/"question".
        TurnController may store fields differently across versions, so we harden here.
        """
        try:
            pa = exec_state.get("pending_action")
            if not isinstance(pa, dict):
                return

            if not isinstance(pa.get("user_message"), str) or not pa.get("user_message", "").strip():
                pa["user_message"] = prompt
            if not isinstance(pa.get("prompt"), str) or not pa.get("prompt", "").strip():
                pa["prompt"] = prompt
            if not isinstance(pa.get("question"), str) or not pa.get("question", "").strip():
                pa["question"] = prompt

            exec_state["pending_action"] = pa
        except Exception:
            return

    # ------------------------------------------------------------------
    # ✅ Fix 1: ALWAYS set exec_state["pending_action"] when asking yes/no
    # ------------------------------------------------------------------
    def _issue_table_confirm_yes_no(
        self,
        *,
        exec_state: Dict[str, Any],
        prompt: str,
        pending_question: str,
        resume_route: str = "data_query",
        resume_pattern: str = "data_query",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Single source of truth for confirmation protocol.

        CRITICAL:
        - pending_question MUST be the original request (e.g. "query consents"),
          NOT the user's "yes"/"no" reply.
        - This writes exec_state["pending_action"] in the canonical shape.
        """
        pq = (pending_question or "").strip()

        # ✅ IMPORTANT: Use TurnController wrapper (handles required reason + UX prompt stashing).
        _turns.ask_confirm_yes_no(
            exec_state,
            owner=self.name,
            pending_question=pq,
            prompt=prompt,
            resume_route=resume_route,
            resume_pattern=resume_pattern,
            context=context or {},
            reason="data_query_table_confirm",
        )

        # ✅ Fix 2: ensure a UI-safe prompt string exists regardless of protocol version
        self._ensure_pending_action_user_message(exec_state, prompt)

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

        logger.debug(
            "[data_query:init] agent initialized",
            extra={"base_url_default": self.BASE_URL},
        )

    # ------------------------------------------------------------------
    # Small internal helpers
    # ------------------------------------------------------------------

    def _lexical_gate(self, raw_text: str, refined_text: str | None = None) -> dict:
        """Simple lexical intent detector (query / CRUD verbs)."""
        effective_text = (refined_text or raw_text or "").strip()
        text_l = effective_text.lower()

        intent: Optional[str] = None
        if text_l.startswith(("query", "read", "get ", "list ", "show ", "find ")):
            intent = "read"
        elif text_l.startswith(("create ", "insert ", "add ", "record ")):
            intent = "create"
        elif text_l.startswith(("update ", "modify ", "change ")):
            intent = "update"
        elif text_l.startswith(("delete ", "remove ")):
            intent = "delete"

        if intent is None and text_l:
            intent = "read"

        result = {"effective_text": effective_text, "intent": intent}

        logger.info(
            "[data_query] lexical gate (local)",
            extra={
                "event": "data_query_lexical_gate_local",
                "effective_text_preview": effective_text[:80],
                "intent": intent,
            },
        )
        return result

    def _set_user_facing_message(self, context: AgentContext, text: str, *, prompted: bool = False) -> None:
        """
        Hard guarantee: user sees the prompt even if the graph ends before FinalAgent runs.

        We write to:
          1) execution_state["final"]  (API-friendly surface)
          2) context.set("final", ...) (best-effort, if supported by AgentContext)
          3) agent_output              (history/UI)

        ✅ PR5.1:
          - Also sets exec_state["wizard_prompted_this_turn"]=True so routers can END.
        """
        exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}
        if prompted:
            exec_state["wizard_prompted_this_turn"] = True

        exec_state["final"] = text
        context.execution_state = exec_state

        try:
            context.set("final", text)
        except Exception:
            pass

        try:
            context.add_agent_output(
                agent_name=self.name,
                logical_name=self.name,
                content=text,
                role="assistant",
                meta={"event": "data_query_prompt"},
                action="prompt",
                intent="informational",
            )
        except Exception:
            return

    # ------------------------------------------------------------------
    # ✅ Wizard helpers (wizard_state.step only; confirmations are protocol-only)
    # ------------------------------------------------------------------

    def _advance_wizard_to_collect_details(
        self,
        context: AgentContext,
        wizard_state: Dict[str, Any],
    ) -> AgentContext:
        """
        Wizard steps begin at collect_details.
        Confirmations are protocol-level and DO NOT live in wizard_state.

        ✅ PR5.1 behavior:
        - Mark that we prompted the user for wizard input this turn, so routers can END.
        - Also set a user-facing message (exec_state["final"]) in case FinalAgent runs.
        """
        wizard_state = dict(wizard_state or {})
        wizard_state["step"] = "collect_details"
        set_wizard_state(context, wizard_state)

        exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}
        exec_state["wizard"] = dict(wizard_state)

        exec_state["wizard_in_progress"] = True
        exec_state["wizard_prompted_this_turn"] = True

        context.execution_state = exec_state

        collection = wizard_state.get("collection")
        table_name = (
            wizard_state.get("table_name")
            or (wizard_state.get("entity_meta") or {}).get("table")
            or collection
            or "unknown_table"
        )
        operation = str(wizard_state.get("operation") or "read").strip().lower()
        orig = str(wizard_state.get("original_query") or "").strip()

        prompt = (
            f"Thanks — I’ll use the `{table_name}` table for this **{operation.upper()}** operation.\n\n"
            f"Original request: **{orig or '(unknown)'}**\n\n"
            "What filters or conditions should I use?\n\n"
            "You can mention columns, statuses, IDs, or date ranges.\n\n"
            "You can type **cancel** at any time to end this workflow."
        )

        self._set_user_facing_message(context, prompt, prompted=True)

        channel_key = wizard_channel_key(self.name, collection)
        context.add_agent_output(
            agent_name=channel_key,
            logical_name=self.name,
            content=prompt,
            role="assistant",
            meta={
                "action": "wizard",
                "step": "collect_details",
                "collection": collection,
                "operation": operation,
                "table_name": table_name,
            },
            action="wizard_step",
            intent="action",
        )
        return context

    def _bail_wizard_from_confirmation(self, context: AgentContext, reason: str) -> AgentContext:
        exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}
        exec_state["wizard_bailed"] = True
        exec_state["wizard_bail_reason"] = reason
        exec_state["suppress_history"] = True

        exec_state.pop("wizard_prompted_this_turn", None)

        self._mark_pending_action_not_awaiting(exec_state)
        exec_state.pop("pending_action_result", None)

        exec_state["wizard"] = None
        exec_state["wizard_in_progress"] = False

        context.execution_state = exec_state
        set_wizard_state(context, None)
        return context

    # ------------------------------------------------------------------
    # MAIN EXECUTION
    # ------------------------------------------------------------------
    async def run(self, context: AgentContext) -> AgentContext:
        """Main data_query entrypoint."""
        exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}

        # ✅ NEW: one-turn flag (router short-circuit) must never persist across turns
        exec_state.pop("wizard_prompted_this_turn", None)

        exec_cfg: Dict[str, Any] = exec_state.setdefault("execution_config", {})
        dq_cfg: Dict[str, Any] = exec_cfg.setdefault("data_query", {})

        # ------------------------------------------------------------------
        # ✅ Load wizard state from exec_state first (persistence source of truth),
        # then fallback to legacy get_wizard_state(context).
        # ------------------------------------------------------------------
        wizard_state: Dict[str, Any] = {}
        w = exec_state.get("wizard")
        if isinstance(w, dict):
            wizard_state = w
        if not wizard_state:
            wizard_state = get_wizard_state(context) or {}

        if wizard_state and not isinstance(exec_state.get("wizard"), dict):
            exec_state["wizard"] = dict(wizard_state)
            context.execution_state = exec_state

        # ------------------------------------------------------------------
        # ✅ Step D (resume): consume protocol result for this owner and continue.
        # ------------------------------------------------------------------
        par = _turns.consume(exec_state, owner=self.name)
        if par:
            self._mark_pending_action_not_awaiting(exec_state)
            exec_state.pop("pending_action_result", None)

            exec_state.pop("pending_confirmation", None)
            exec_state.pop("confirm_table", None)

            decision = str(par.get("decision") or "").strip().lower()

            logger.info(
                "[data_query:protocol] pending_action_result consumed on entry",
                extra={
                    "event": "data_query_pending_action_result_entry",
                    "decision": decision,
                    "wizard_step": wizard_state.get("step") if wizard_state else None,
                },
            )

            if decision in {"no", "cancel"}:
                context.execution_state = exec_state
                self._set_user_facing_message(context, "Okay — cancelled.")
                return self._bail_wizard_from_confirmation(context, reason=f"pending_action_decision_{decision}")

            if decision not in {"yes"}:
                context.execution_state = exec_state
                self._set_user_facing_message(context, "Okay — cancelled.")
                return self._bail_wizard_from_confirmation(context, reason="pending_action_decision_unknown")

            exec_state["wizard_bailed"] = False
            exec_state["wizard_cancelled"] = False
            exec_state["wizard_bail_reason"] = None
            exec_state["wizard_in_progress"] = True

            if not wizard_state:
                ctx = par.get("context") if isinstance(par, dict) else None
                ctx_dict: Dict[str, Any] = ctx if isinstance(ctx, dict) else {}
                table = str(ctx_dict.get("table_name") or "unknown_table").strip() or "unknown_table"
                collection = str(ctx_dict.get("collection") or table).strip() or table
                entity_meta = ctx_dict.get("entity_meta")
                if not isinstance(entity_meta, dict):
                    entity_meta = {"table": table}

                wizard_state = {
                    "operation": "read",
                    "collection": collection,
                    "table_name": table,
                    "entity_meta": dict(entity_meta),
                    "route_info": {"route": self.name},
                    "base_url": self.BASE_URL,
                    "original_query": exec_state.get("original_query") or "",
                    "step": "collect_details",
                }
                set_wizard_state(context, wizard_state)
                exec_state["wizard"] = dict(wizard_state)
            else:
                step = str(wizard_state.get("step") or "").strip().lower()
                if not step:
                    wizard_state["step"] = "collect_details"
                    set_wizard_state(context, wizard_state)
                exec_state["wizard"] = dict(wizard_state)

            # ✅ IMPORTANT: keep pending_action_resume_turn flag (set by TurnController)
            # so the wizard delegation can detect the resume turn and hard-stop.

            context.execution_state = exec_state
            # Fall through into the normal wizard delegation below.

        context.execution_state = exec_state

        # ------------------------------------------------------------------
        # Normal run continues (unchanged)
        # ------------------------------------------------------------------
        classifier, initial_effective_text = _get_classifier_and_text_from_context(context)
        if not isinstance(classifier, dict):
            classifier = {}
        classifier.setdefault("topic_confidence", 0.0)
        classifier.setdefault("topics", [])
        classifier.setdefault("intent", None)

        raw_user_input = (getattr(context, "query", "") or "").strip()
        if not raw_user_input:
            raw_user_input = (exec_state.get("user_question") or "").strip()

        existing_original = (exec_state.get("original_query") or "").strip()
        if not existing_original and raw_user_input:
            exec_state["original_query"] = raw_user_input
            context.execution_state = exec_state

        # ------------------------------------------------------------------
        # ✅ PR5: Prefer exec_state["refiner_output"] contract; fallback to last_output("refiner")
        # ------------------------------------------------------------------
        refined_text: Optional[str] = None
        try:
            ro = exec_state.get("refiner_output") if isinstance(exec_state, dict) else None
            refined_text = _extract_refined_text_from_refiner_output(ro or {})
            if not refined_text:
                refiner_output = context.get_last_output("refiner")
                refined_text = _extract_refined_text_from_refiner_output(refiner_output)
        except Exception as e:  # pragma: no cover
            logger.warning(
                "[data_query:refiner] failed to extract refined_query; falling back to original text",
                extra={
                    "event": "data_query_refined_query_extract_error",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
            )
            refined_text = None

        effective_text = (raw_user_input or refined_text or initial_effective_text or "").strip()
        raw_text_norm = effective_text
        raw_text_lower = effective_text.lower()

        exec_state["data_query_texts"] = {
            "raw_user_input": raw_user_input,
            "raw_text": raw_text_norm,
            "refined_text": refined_text,
            "effective_text": effective_text,
        }
        context.execution_state = exec_state

        structured_filters_cfg: List[Dict[str, Any]] = dq_cfg.get("filters") or []

        logger.info(
            "[data_query:wizard_state] loaded wizard state in run()",
            extra={
                "event": "data_query_wizard_state_loaded",
                "has_wizard_state": bool(wizard_state),
                "wizard_keys": sorted(list(wizard_state.keys())) if wizard_state else [],
                "wizard_step": (wizard_state or {}).get("step"),
            },
        )

        # ------------------------------------------------------------------
        # ✅ Fix 3 (robust): absolutely-first-turn guard
        # ------------------------------------------------------------------
        if not wizard_state and raw_text_lower.startswith("query "):
            topic = ""
            try:
                topic = str((exec_state.get("classifier") or {}).get("topic") or "").strip().lower()
            except Exception:
                topic = ""

            guessed_table = _guess_table_name(topic=topic, raw_text_lower=raw_text_lower)
            table = guessed_table or (topic or "").strip().lower() or "unknown_table"
            collection = table

            wizard_state = {
                "operation": "read",
                "collection": collection,
                "table_name": table,
                "entity_meta": {"table": table},
                "route_info": {"route": self.name},
                "base_url": self.BASE_URL,
                "original_query": exec_state.get("original_query") or raw_user_input,
                "step": "collect_details",
            }
            set_wizard_state(context, wizard_state)
            exec_state["wizard"] = dict(wizard_state)
            context.execution_state = exec_state

            prompt = f"Use `{table}` for this request? (yes/no)"

            self._issue_table_confirm_yes_no(
                exec_state=exec_state,
                prompt=prompt,
                pending_question=str(wizard_state.get("original_query") or ""),
                resume_route="data_query",
                resume_pattern="data_query",
                context={
                    "table_name": table,
                    "collection": collection,
                    "entity_meta": wizard_state["entity_meta"],
                },
            )
            context.execution_state = exec_state

            logger.info(
                "[data_query:first_turn_guard] issued confirm_yes_no",
                extra={
                    "event": "data_query_first_turn_guard_confirm",
                    "table": table,
                    "collection": collection,
                    "topic": topic or None,
                    "has_pending_action": isinstance(exec_state.get("pending_action"), dict),
                },
            )

            self._set_user_facing_message(context, prompt, prompted=True)
            return context

        # ------------------------------------------------------------------
        # ✅ FIX 2: Orphan wizard-state heal
        # ------------------------------------------------------------------
        if wizard_state and not str(wizard_state.get("step") or "").strip():
            pa = exec_state.get("pending_action")
            pa_owner = ""
            pa_type = ""
            pa_awaiting = False
            if isinstance(pa, dict):
                pa_owner = str(pa.get("owner") or "").strip().lower()
                pa_type = str(pa.get("type") or "").strip().lower()
                pa_awaiting = bool(pa.get("awaiting"))

            has_awaiting_for_me = pa_awaiting and pa_type == "confirm_yes_no" and pa_owner == self.name

            if not has_awaiting_for_me:
                collection = str(wizard_state.get("collection") or "").strip()
                table_name = (
                    str(wizard_state.get("table_name") or "").strip()
                    or str((wizard_state.get("entity_meta") or {}).get("table") or "").strip()
                    or collection
                    or "unknown_table"
                )

                pending_question = str(
                    wizard_state.get("original_query")
                    or exec_state.get("original_query")
                    or raw_user_input
                    or ""
                ).strip()

                prompt = f"Use `{table_name}` for this request? (yes/no)"

                self._issue_table_confirm_yes_no(
                    exec_state=exec_state,
                    prompt=prompt,
                    pending_question=pending_question,
                    resume_route="data_query",
                    resume_pattern="data_query",
                    context={
                        "table_name": table_name,
                        "collection": collection or table_name,
                        "entity_meta": wizard_state.get("entity_meta") or {"table": table_name},
                    },
                )
                context.execution_state = exec_state

                logger.info(
                    "[data_query:wizard] orphan wizard_state healed: re-issued confirm_yes_no",
                    extra={
                        "event": "data_query_orphan_wizard_healed",
                        "table_name": table_name,
                        "collection": collection or table_name,
                        "has_pending_question": bool(pending_question),
                    },
                )

                self._set_user_facing_message(context, prompt, prompted=True)
                return context

        crud_verbs = {"read", "create", "update", "delete", "patch"}

        lexical = self._lexical_gate(
            raw_text=(effective_text or raw_user_input or raw_text_norm or ""),
            refined_text=None,
        )
        lexical_intent = lexical.get("intent")
        if isinstance(lexical_intent, str):
            lexical_intent = lexical_intent.strip().lower() or None

        force_data_query = bool(dq_cfg.get("force")) or _looks_like_database_query(effective_text)

        state_intent = getattr(context, "intent", None) or exec_state.get("intent")
        classifier_intent = classifier.get("intent") if isinstance(classifier, dict) else None

        if isinstance(state_intent, str):
            state_intent = state_intent.strip().lower() or None
        if isinstance(classifier_intent, str):
            classifier_intent = classifier_intent.strip().lower() or None

        if lexical_intent in crud_verbs:
            intent_raw = state_intent if state_intent in crud_verbs else lexical_intent
        else:
            intent_raw = state_intent or classifier_intent or lexical_intent

        intent = (intent_raw or "").strip().lower() or None

        crud_intent_for_wizard = intent
        if raw_text_lower.startswith("query "):
            crud_intent_for_wizard = "read"
        elif intent is None and raw_text_lower.startswith("query"):
            crud_intent_for_wizard = "read"
        elif intent not in crud_verbs and force_data_query:
            crud_intent_for_wizard = "read"

        # ------------------------------------------------------------------
        # ✅ MIGRATION WINDOW PATCH via TurnController
        # ------------------------------------------------------------------
        if wizard_state:
            step, healed = _turns.wizard_step_migration_heal(wizard_state)
            if healed:
                set_wizard_state(context, wizard_state)
                exec_state["wizard"] = dict(wizard_state)
                logger.info(
                    "[data_query:wizard] migrated legacy wizard step -> wizard_state.step",
                    extra={"event": "data_query_wizard_step_migrated", "step": step},
                )

            if step in {"confirm_table", "pending_confirmation"}:
                logger.warning(
                    "[data_query:wizard] invalid wizard step in legacy state (confirm_table is protocol-only); no-op",
                    extra={
                        "event": "data_query_invalid_wizard_step_legacy",
                        "step": step,
                        "wizard_keys": list(wizard_state.keys()),
                    },
                )
                return context

            if step:
                logger.info(
                    "[data_query:wizard] delegating wizard step to CrudWizard",
                    extra={"event": "data_query_wizard_delegate", "step": step},
                )

                # --------------------------------------------------------------
                # ✅ CRITICAL FIX (turns):
                # On a pending-action YES resume turn, TurnNormalizer swaps the
                # visible user text ("yes") -> pending_question ("query consents")
                # for routing. That swapped text MUST NOT be treated as wizard
                # "details" input.
                #
                # We force the collect_details prompt and END this run.
                # --------------------------------------------------------------
                if _truthy(exec_state.get("pending_action_resume_turn")) and step == "collect_details":
                    exec_state.pop("pending_action_resume_turn", None)

                    exec_state["wizard_bailed"] = False
                    exec_state["wizard_in_progress"] = True
                    exec_state["wizard"] = dict(wizard_state)
                    context.execution_state = exec_state

                    return self._advance_wizard_to_collect_details(context, wizard_state)

                # ✅ Normal wizard flow (non-resume turns)
                wizard_user_text = effective_text

                wizard = CrudWizard(agent_name=self.name, context=context, wizard_state=wizard_state)
                return await wizard.handle(wizard_user_text)

        # ------------------------------------------------------------------
        # Skip non-query chatter (only if NOT forcing data_query and no wizard flow)
        # ------------------------------------------------------------------
        if crud_intent_for_wizard not in crud_verbs and not force_data_query:
            logger.info(
                "[data_query:routing] skipping: no structured query, no force, no wizard",
                extra={"event": "data_query_skip_non_structured", "effective_text_preview": effective_text[:200]},
            )
            # ... keep your existing skip block exactly as-is ...
            return context

        # ------------------------------------------------------------------
        # ✅ Wizard init
        # ------------------------------------------------------------------
        if not wizard_state and (crud_intent_for_wizard in crud_verbs or force_data_query):
            topic = ""
            try:
                topic = str((exec_state.get("classifier") or {}).get("topic") or "").strip().lower()
            except Exception:
                topic = ""

            guessed_table = _guess_table_name(topic=topic, raw_text_lower=raw_text_lower)
            table = guessed_table or (topic or "").strip().lower() or "unknown_table"
            collection = table

            wizard_state = {
                "operation": crud_intent_for_wizard or "read",
                "collection": collection,
                "table_name": table,
                "entity_meta": {"table": table},
                "route_info": {"route": self.name},
                "base_url": self.BASE_URL,
                "original_query": exec_state.get("original_query") or raw_user_input or effective_text,
                # NOTE: do NOT set step here; only after YES
            }
            set_wizard_state(context, wizard_state)
            exec_state["wizard"] = dict(wizard_state)
            context.execution_state = exec_state

            prompt = f"Use `{table}` for this request? (yes/no)"

            self._issue_table_confirm_yes_no(
                exec_state=exec_state,
                prompt=prompt,
                pending_question=str(wizard_state.get("original_query") or ""),
                resume_route="data_query",
                resume_pattern="data_query",
                context={
                    "table_name": table,
                    "collection": collection,
                    "entity_meta": wizard_state.get("entity_meta") or {},
                },
            )
            context.execution_state = exec_state

            logger.info(
                "[data_query:wizard] wizard init: awaiting confirm_yes_no",
                extra={
                    "event": "data_query_wizard_started",
                    "table_name": table,
                    "collection": collection,
                    "operation": wizard_state.get("operation"),
                    "classifier_topic": topic or None,
                },
            )

            self._set_user_facing_message(context, prompt, prompted=True)
            return context

        logger.info(
            "[data_query] run() completed (no wizard)",
            extra={"event": "data_query_run_completed"},
        )
        return context

