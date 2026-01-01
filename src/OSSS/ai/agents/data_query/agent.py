from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncEngine

from OSSS.ai.context import AgentContext
from OSSS.ai.agents.base_agent import BaseAgent, LangGraphNodeDefinition
from OSSS.ai.agents.classifier_agent import ClassifierResult  # kept for type hints
from OSSS.ai.agents.data_query.config import DataQueryRoute
from OSSS.ai.agents.data_query.queryspec import QuerySpec, FilterCondition
from OSSS.ai.agents.data_query.query_metadata import DEFAULT_QUERY_SPECS
from OSSS.ai.agents.data_query.text_filters import parse_text_filters
from OSSS.ai.services.nl_to_sql_service import NLToSQLService

from OSSS.ai.services.backend_api_client import BackendAPIClient, BackendAPIConfig
from OSSS.ai.observability import get_logger

from OSSS.ai.agents.data_query.utils import (
    ExtractedTextFilters,
    _extract_text_filters_from_query,
    _looks_like_database_query,
    _extract_refined_text_from_refiner_output,
    _get_classifier_and_text_from_context,
    _normalize_like_filter_condition,
    _extract_text_sort_from_query,
    _apply_filters_to_params,
    _rows_to_markdown_table,
    _shrink_to_ui_defaults,
    choose_route_for_query,
)


# 🔁 UPDATED IMPORT: now pulling from wizard.crud_wizard and using the class
from OSSS.ai.agents.data_query.wizard.crud_wizard import (
    get_wizard_state,
    set_wizard_state,
    wizard_channel_key,
    CrudWizard,
)

logger = get_logger(__name__)

DEFAULT_BASE_URL = os.getenv("OSSS_BACKEND_BASE_URL", "http://app:8000")
MIN_TOPIC_CONFIDENCE = float(os.getenv("OSSS_DATAQUERY_MIN_TOPIC_CONFIDENCE", "0.15"))

# Simple confirmation phrases for wizard-style follow-ups
CONFIRMATION_TOKENS = {
    "yes",
    "yep",
    "yeah",
    "y",
    "ok",
    "okay",
    "sure",
    "do it",
    "go ahead",
    "confirm",
    "please proceed",
}


@dataclass(frozen=True)
class DataQuerySpec:
    name: str
    store_key: str
    source: str = "http"


class DataQueryAgent(BaseAgent):
    """Refactored data_query agent.

    - Wizard orchestration lives in OSSS.ai.agents.data_query.wizard
    - Common helpers live in OSSS.ai.agents.data_query.utils
    - This class focuses on:
        * lexical gating / intent resolution
        * wiring QuerySpec + HTTP calls
        * emitting structured + markdown outputs
    """

    name = "data_query"
    BASE_URL = DEFAULT_BASE_URL

    def __init__(
        self,
        *,
        data_query: Optional[Dict[str, Any]] = None,
        pg_engine: Optional[AsyncEngine] = None,
    ):
        super().__init__(name=self.name, timeout_seconds=20.0)
        self.data_query = data_query or {}
        self.pg_engine = pg_engine
        # Dependency-injected service; default to a shared instance.
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

        result = {
            "effective_text": effective_text,
            "intent": intent,
        }

        logger.info(
            "[data_query] lexical gate (local)",
            extra={
                "event": "data_query_lexical_gate_local",
                "effective_text_preview": effective_text[:80],
                "intent": intent,
            },
        )
        return result

    def _is_confirmation(self, text: str) -> bool:
        """Return True if the user text looks like a simple confirmation (e.g. 'yes')."""
        if not text:
            return False
        normalized = text.strip().lower()
        return normalized in CONFIRMATION_TOKENS

    async def _maybe_execute_wizard_plan(
        self,
        context: AgentContext,
        wizard_state: Optional[Dict[str, Any]],
        raw_text: str,
        effective_text: str,
    ) -> Optional[Dict[str, Any]]:
        """
        If there's an in-flight wizard and the user message is a simple confirmation,
        delegate handling to the wizard instead of treating it as a fresh query.
        """
        if wizard_state is None:
            logger.debug(
                "[data_query:wizard_confirm] _maybe_execute_wizard_plan called with no wizard_state",
                extra={"event": "data_query_wizard_confirm_no_state"},
            )
            return None

        # Support both 'status' and older 'pending_action'-style markers.
        status = wizard_state.get("status") or wizard_state.get("pending_action")
        if status not in {"pending_confirmation", "confirm_table"}:
            logger.debug(
                "[data_query:wizard_confirm] wizard_state present but status not confirm-related",
                extra={
                    "event": "data_query_wizard_confirm_status_mismatch",
                    "status": status,
                    "wizard_keys": list(wizard_state.keys()),
                },
            )
            return None

        confirmation_text = effective_text or raw_text
        if not self._is_confirmation(confirmation_text):
            logger.debug(
                "[data_query:wizard_confirm] message not treated as confirmation",
                extra={
                    "event": "data_query_wizard_confirm_not_confirmation",
                    "confirmation_text": confirmation_text,
                },
            )
            return None

        logger.info(
            "[data_query:wizard_confirm] confirmation detected, delegating to CrudWizard",
            extra={
                "event": "data_query_wizard_confirm",
                "status": status,
                "wizard_keys": list(wizard_state.keys()),
            },
        )

        await CrudWizard.continue_wizard(
            agent_name=self.name,
            context=context,
            wizard_state=wizard_state,
            user_text=confirmation_text,
        )

        return {"ok": True, "handled_by": "wizard_confirm", "status": status}


    # ------------------------------------------------------------------
    # MAIN EXECUTION
    # ------------------------------------------------------------------
    async def run(self, context: AgentContext) -> AgentContext:
        """Main data_query entrypoint."""
        exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}
        exec_cfg: Dict[str, Any] = exec_state.setdefault("execution_config", {})
        dq_cfg: Dict[str, Any] = exec_cfg.setdefault("data_query", {})

        # Classifier output + original text (typically pre-refiner)
        # Classifier output + original text (typically pre-refiner)
        classifier, initial_effective_text = _get_classifier_and_text_from_context(context)
        if not isinstance(classifier, dict):
            classifier = {}
        classifier.setdefault("topic_confidence", 0.0)
        classifier.setdefault("topics", [])
        classifier.setdefault("intent", None)

        # ✅ Actual user text (what we really want to route on)
        raw_user_input = (exec_state.get("user_question") or "").strip()

        # Try to get refined_query from refiner
        refined_text: Optional[str] = None
        try:
            refiner_output = context.get_last_output("refiner")
            refined_text = _extract_refined_text_from_refiner_output(refiner_output)
        except Exception as e:  # pragma: no cover - best effort only
            logger.warning(
                "[data_query:refiner] failed to extract refined_query; falling back to original text",
                extra={
                    "event": "data_query_refined_query_extract_error",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
            )
            refined_text = None

        # ✅ Prefer user query for routing; refiner/classifier text is only a fallback
        effective_text = (raw_user_input or refined_text or initial_effective_text or "").strip()
        raw_text_norm = effective_text

        exec_state["data_query_texts"] = {
            "raw_user_input": raw_user_input,
            "raw_text": raw_text_norm,
            "refined_text": refined_text,
            "effective_text": effective_text,
        }
        context.execution_state = exec_state

        raw_text_lower = effective_text.lower()

        exec_state["data_query_texts"] = {
            "raw_user_input": raw_user_input,
            "raw_text": raw_text_norm,
            "refined_text": refined_text,
            "effective_text": effective_text,
        }
        context.execution_state = exec_state

        structured_filters_cfg: List[Dict[str, Any]] = dq_cfg.get("filters") or []

        # Load wizard state (if any)
        wizard_state: Optional[Dict[str, Any]] = get_wizard_state(context)

        logger.info(
            "[data_query:wizard_state] loaded wizard state in run()",
            extra={
                "event": "data_query_wizard_state_loaded",
                "has_wizard_state": wizard_state is not None and bool(wizard_state),
                "wizard_keys": list(wizard_state.keys()) if wizard_state else [],
                "wizard_pending_action": (
                    wizard_state.get("pending_action") if wizard_state else None
                ),
                "wizard_status": (wizard_state.get("status") if wizard_state else None),
            },
        )

        # --------------------------
        # Wizard flow classification
        # --------------------------
        crud_verbs = {"read", "create", "update", "delete", "patch"}
        crud_pending_actions = {
            "confirm_table",
            "confirm_entity",
            "collect_filters",
            "collect_updates",
        }

        wizard_operation = (
            str((wizard_state or {}).get("operation") or "").strip().lower()
            if wizard_state
            else ""
        )
        wizard_pending_action = (
            str((wizard_state or {}).get("pending_action") or "").strip().lower()
            if wizard_state
            else ""
        )

        is_crud_wizard_flow = bool(wizard_state) and (
            wizard_operation in crud_verbs
            or wizard_pending_action in crud_pending_actions
        )

        # Lexical gate (use the cleaned effective_text, not the long refiner narrative)
        lexical = self._lexical_gate(
            raw_text=(effective_text or raw_user_input or raw_text_norm or ""),
            refined_text=None,  # ✅ ignore refiner text here; it can be verbose/meta
        )

        lexical_intent = lexical.get("intent")
        if isinstance(lexical_intent, str):
            lexical_intent = lexical_intent.strip().lower() or None

        is_crud_lexical_intent = lexical_intent in crud_verbs
        force_data_query = bool(dq_cfg.get("force")) or _looks_like_database_query(
            effective_text
        )

        logger.info(
            "[data_query] lexical gate",
            extra={
                "event": "data_query_lexical_gate",
                "raw_text_preview": raw_text_norm[:200],
                "effective_text_preview": effective_text[:200],
                "raw_user_preview": raw_user_input[:200],
                "force_data_query": force_data_query,
                "has_wizard_state": wizard_state is not None and bool(wizard_state),
                "lexical_intent": lexical_intent,
                "is_crud_lexical_intent": is_crud_lexical_intent,
                "is_crud_wizard_flow": is_crud_wizard_flow,
                "wizard_operation": wizard_operation,
                "wizard_pending_action": wizard_pending_action,
            },
        )

        # ---- Intent resolution (moved earlier so CRUD flows are never skipped) ----
        state_intent = getattr(context, "intent", None) or exec_state.get("intent")
        classifier_intent = classifier.get("intent") if isinstance(classifier, dict) else None

        if isinstance(state_intent, str):
            state_intent = state_intent.strip().lower() or None
        if isinstance(classifier_intent, str):
            classifier_intent = classifier_intent.strip().lower() or None

        if lexical_intent in crud_verbs:
            if state_intent in crud_verbs:
                intent_raw = state_intent
            else:
                intent_raw = lexical_intent
        else:
            intent_raw = state_intent or classifier_intent or lexical_intent

        intent = (intent_raw or "").strip().lower() or None
        topic_override = dq_cfg.get("topic")

        logger.info(
            "[data_query] run() begin",
            extra={
                "event": "data_query_run_begin",
                "intent": intent,
                "topic_override": topic_override,
                "raw_text_preview": raw_text_norm[:200],
                "refined_text_preview": (refined_text[:200] if refined_text else None),
                "effective_text_preview": effective_text[:200],
                "raw_user_preview": raw_user_input[:200],
            },
        )

        # If there's an active wizard, first check if this is a simple confirmation
        wizard_result: Optional[Dict[str, Any]] = None
        if wizard_state is not None and wizard_state:
            logger.debug(
                "[data_query:wizard] attempting wizard confirmation path",
                extra={
                    "event": "data_query_wizard_confirm_attempt",
                    "wizard_keys": list(wizard_state.keys()),
                    "wizard_pending_action": wizard_pending_action,
                    "wizard_status": wizard_state.get("status"),
                },
            )
            try:
                wizard_result = await self._maybe_execute_wizard_plan(
                    context=context,
                    wizard_state=wizard_state,
                    raw_text=raw_user_input or raw_text_norm or "",
                    effective_text=effective_text,
                )
            except Exception as e:  # pragma: no cover - defensive
                logger.error(
                    "[data_query:wizard_confirm] error while handling confirmation",
                    extra={
                        "event": "data_query_wizard_confirm_error",
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                )
                wizard_result = None

            # If the wizard handled this turn (e.g. "yes" / "ok"), we don't treat it as a new query
            if wizard_result is not None:
                logger.info(
                    "[data_query:wizard_confirm] wizard handled this turn; skipping fresh query",
                    extra={
                        "event": "data_query_wizard_handled_turn",
                        "wizard_result": wizard_result,
                    },
                )
                return context

        # Skip non-query chatter, but emit a structured "skipped" output
        if (
            intent not in crud_verbs
            and not force_data_query
            and not is_crud_wizard_flow
        ):
            logger.info(
                "[data_query:routing] skipping: no structured query, no force, "
                "no CRUD wizard flow, non-CRUD intent",
                extra={
                    "event": "data_query_skip_non_structured",
                    "effective_text_preview": effective_text[:200],
                    "intent": intent,
                },
            )

            channel_key = self.name

            meta_block = {
                "status": "skipped",
                "reason": "skip_non_structured",
                "event": "data_query_skip_non_structured",
                "projection_mode": "none",
            }

            canonical_output = {
                "status": "skipped",
                "reason": "skip_non_structured",
                "table_markdown": "",
                "table_markdown_compact": "",
                "table_markdown_full": "",
                "markdown": "",
                "content": "",
                "meta": meta_block,
                "action": "noop",
                "intent": "none",
            }

            human_message = (
                "Data query skipped: your message didn't look like a structured "
                "database/query or CRUD request, so no data was fetched."
            )

            context.add_agent_output(
                agent_name=channel_key,
                logical_name=self.name,
                content=human_message,
                role="assistant",
                meta=meta_block,
                action="noop",
                intent="none",
            )

            structured_outputs = context.execution_state.setdefault(
                "structured_outputs", {}
            )
            structured_outputs[channel_key] = canonical_output
            if not isinstance(structured_outputs.get(self.name), dict):
                structured_outputs[self.name] = canonical_output

            return context

        # Continue wizard, if one is active and this wasn't a simple confirmation case
        if wizard_state is not None and wizard_state:
            logger.info(
                "[data_query:wizard] continuing existing wizard (non-confirmation path)",
                extra={
                    "event": "data_query_wizard_continue",
                    "wizard_keys": list(wizard_state.keys()),
                    "wizard_pending_action": wizard_pending_action,
                    "wizard_status": wizard_state.get("status"),
                },
            )

            return await CrudWizard.continue_wizard(
                agent_name=self.name,
                context=context,
                wizard_state=wizard_state,
                user_text=effective_text or raw_user_input or raw_text_norm,
            )

        # -----------------
        # Route selection
        # -----------------
        routing_text = effective_text or raw_text_norm or raw_user_input

        if topic_override:
            route = DataQueryRoute.from_topic(topic_override, intent=intent)  # type: ignore[attr-defined]
            route_source = "explicit_override"
        else:
            route = choose_route_for_query(
                routing_text,
                classifier,
                min_topic_confidence=MIN_TOPIC_CONFIDENCE,
            )
            route_source = "classifier_or_text"

        logger.info(
            "[data_query:routing] route selected",
            extra={
                "event": "data_query_route_selected",
                "route_source": route_source,
                "routing_text_preview": routing_text[:200],
                "route_topic": getattr(route, "topic", None),
                "route_collection": getattr(route, "collection", None),
                "route_view": getattr(route, "view_name", None),
            },
        )

        # Metadata from route
        if hasattr(route, "to_entity") and callable(getattr(route, "to_entity")):
            entity_meta: Dict[str, Any] = route.to_entity()
        else:
            entity_meta = {
                "id": getattr(route, "id", None) or route.topic or route.collection,
                "topic_key": getattr(
                    route,
                    "topic_key",
                    getattr(route, "topic", getattr(route, "collection", None)),
                ),
                "table": getattr(route, "table", getattr(route, "collection", None)),
                "api_route": getattr(route, "api_route", route.resolved_path),
                "display_name": getattr(
                    route,
                    "display_name",
                    (
                        route.topic.replace("_", " ")
                        if isinstance(route.topic, str)
                        else getattr(route, "collection", None)
                    ),
                ),
                "synonyms": getattr(route, "synonyms", []) or [],
                "description": getattr(route, "description", None),
                "collection": route.collection,
                "view_name": route.view_name,
                "path": getattr(route, "path", None),
                "detail_path": getattr(route, "detail_path", None),
                "base_url": getattr(route, "base_url", None),
                "default_params": getattr(route, "default_params", None),
            }

        raw_base_url_from_cfg = dq_cfg.get("base_url")
        raw_base_url_from_route = getattr(route, "base_url", None)

        if raw_base_url_from_cfg:
            raw_base_url = raw_base_url_from_cfg
        elif raw_base_url_from_route:
            raw_base_url = raw_base_url_from_route
        else:
            raw_base_url = self.BASE_URL

        base_url = (raw_base_url or "").rstrip("/")
        if not base_url or not base_url.startswith(("http://", "https://")):
            raise RuntimeError(
                f"Invalid base_url for route "
                f"{getattr(route, 'id', getattr(route, 'topic', None))!r}: "
                f"{raw_base_url!r} (expected something like 'http://localhost:8000')"
            )

        params: Dict[str, Any] = {}
        params.update(getattr(route, "default_params", None) or {})
        params.update(dq_cfg.get("default_params") or {})
        params.update(exec_cfg.get("http_query_params") or {})

        # QuerySpec setup
        collection = getattr(route, "collection", None) or entity_meta.get("collection")
        base_spec = DEFAULT_QUERY_SPECS.get(collection) if collection else None
        if base_spec:
            query_spec = QuerySpec(
                base_collection=base_spec.base_collection,
                projections=list(base_spec.projections),
                joins=list(base_spec.joins),
                filters=list(base_spec.filters),
                synonyms=dict(base_spec.synonyms),
                search_fields=list(base_spec.search_fields),
                default_limit=base_spec.default_limit,
                **(
                    {"sort": list(getattr(base_spec, "sort", []))}
                    if hasattr(base_spec, "sort")
                    else {}
                ),
            )
        else:
            query_spec = QuerySpec(base_collection=collection or "")

        # Attach structured filters from config
        for f in structured_filters_cfg:
            try:
                field = (f.get("field") or "").strip()
                op = (f.get("op") or "eq").strip().lower()
                value = f.get("value", None)
                if field and value is not None:
                    query_spec.filters.append(
                        FilterCondition(field=field, op=op, value=value)
                    )
            except Exception:
                logger.exception(
                    "[data_query:filters] failed to attach cfg filter",
                    extra={"event": "data_query_cfg_filter_attach_error", "filter": f},
                )

        # Text-derived filters
        filter_text = raw_user_input or raw_text_norm or effective_text
        if filter_text:
            before_count = len(query_spec.filters)
            query_spec = parse_text_filters(filter_text, query_spec)
            after_count = len(query_spec.filters)

            if after_count > before_count:
                logger.info(
                    "[data_query:filters] parsed filters from text",
                    extra={
                        "event": "data_query_filters_from_text",
                        "raw_text_preview": filter_text[:200],
                        "new_filter_count": after_count - before_count,
                        "total_filter_count": after_count,
                    },
                )

            normalized_filters: List[FilterCondition] = []
            for fc in query_spec.filters:
                try:
                    normalized_filters.append(_normalize_like_filter_condition(fc))
                except Exception as e:
                    logger.warning(
                        "[data_query:filters] like-normalization failed; keeping original condition",
                        extra={
                            "event": "data_query_like_normalization_failed",
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                            "field": getattr(fc, "field", None),
                            "op": getattr(fc, "op", None),
                            "value": getattr(fc, "value", None),
                        },
                    )
                    normalized_filters.append(fc)

            query_spec.filters = normalized_filters

            # Fallback 'startswith' filters for simple phrases
            try:
                extracted = _extract_text_filters_from_query(filter_text, route)
            except Exception as e:
                logger.warning(
                    "[data_query:filters] fallback text filter parsing failed; ignoring",
                    extra={
                        "event": "data_query_fallback_text_filter_parse_error",
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "raw_text_preview": filter_text[:200],
                    },
                )
                extracted = ExtractedTextFilters(filters=[], sort=None)

            if extracted.filters:
                logger.info(
                    "[data_query:filters] applying fallback text filters to HTTP params",
                    extra={
                        "event": "data_query_apply_fallback_filters",
                        "raw_text_preview": filter_text[:200],
                        "fallback_filter_count": len(extracted.filters),
                        "filters": extracted.filters,
                    },
                )
                params = _apply_filters_to_params(params, extracted.filters)

        dq_meta = exec_state.setdefault("data_query_step_metadata", {})
        dq_meta["query_spec_summary"] = {
            "base_collection": query_spec.base_collection,
            "projection_count": len(query_spec.projections),
            "join_count": len(query_spec.joins),
            "filter_count": len(query_spec.filters),
            "search_fields": list(query_spec.search_fields),
            "sort": list(getattr(query_spec, "sort", [])),
        }

        compiled_filters: List[Dict[str, Any]] = [
            {"field": fc.field, "op": fc.op, "value": fc.value}
            for fc in query_spec.filters
        ]
        if compiled_filters:
            params = _apply_filters_to_params(params, compiled_filters)

        # Sort handling
        sort_list: List[Tuple[str, str]] = list(getattr(query_spec, "sort", []))
        if not sort_list and filter_text:
            sort_hint = _extract_text_sort_from_query(filter_text)
            if sort_hint:
                sort_list = [sort_hint]

        if sort_list:
            sort_field, sort_dir = sort_list[0]
            sort_dir = (sort_dir or "asc").lower()
            if sort_dir not in {"asc", "desc"}:
                sort_dir = "asc"
            ordering_value = f"-{sort_field}" if sort_dir == "desc" else sort_field
            params["ordering"] = ordering_value

        entity_meta["base_url"] = base_url
        entity_meta["default_params"] = params

        # CRUD wizards (table-confirm handshake) – only when this turn itself is CRUD intent
        if intent in {"read", "create", "update", "delete", "patch"}:
            collection_for_wizard = getattr(route, "collection", None)
            table_name = (
                entity_meta.get("table")
                or collection_for_wizard
                or entity_meta.get("topic_key")
                or getattr(route, "topic", None)
                or "unknown_table"
            )


            wizard_state_init: Dict[str, Any] = {
                "pending_action": "confirm_table",
                "operation": intent,
                "collection": collection_for_wizard,
                "table_name": table_name,
                "base_url": base_url,
                "route_info": {
                    "topic": getattr(route, "topic", None),
                    "collection": collection_for_wizard,
                    "view_name": getattr(route, "view_name", None),
                    "resolved_path": getattr(route, "resolved_path", None),
                },
                "entity_meta": dict(entity_meta),
            }

            logger.info(
                "[data_query:wizard_state] initializing CRUD wizard_state",
                extra={
                    "event": "data_query_wizard_state_init",
                    "operation": intent,
                    "collection": collection_for_wizard,
                    "table_name": table_name,
                    "wizard_state_keys": list(wizard_state_init.keys()),
                    "route_info": wizard_state_init.get("route_info"),
                },
            )

            set_wizard_state(context, wizard_state_init)

            exec_state_after = getattr(context, "execution_state", {}) or {}
            logger.info(
                "[data_query:wizard_state] wizard_state stored in execution_state",
                extra={
                    "event": "data_query_wizard_state_post_set",
                    "has_wizard": "wizard" in exec_state_after,
                    "wizard_keys": list(
                        (exec_state_after.get("wizard") or {}).keys()
                    ),
                    "wizard_pending_action": (
                        (exec_state_after.get("wizard") or {}).get("pending_action")
                    ),
                },
            )

            channel_key = wizard_channel_key(self.name, collection_for_wizard)

            content_str = (
                f"I’m about to **{intent}** records in the `{table_name}` table.\n"
                "Is that the correct table? You can reply 'yes', 'no', provide a different table name, "
                "or type 'cancel' to end this workflow."
            )
            meta_block = {
                "action": "wizard",
                "step": "confirm_table",
                "collection": collection_for_wizard,
                "operation": intent,
                "table_name": table_name,
            }

            context.add_agent_output(
                agent_name=channel_key,
                logical_name=self.name,
                content=content_str,
                role="assistant",
                meta=meta_block,
                action="wizard_table_confirm",
                intent="action",
            )
            return context



        logger.info(
            "[data_query] run() completed",
            extra={
                "event": "data_query_run_completed",
                "view": payload.get("view"),
                "row_count": payload.get("row_count"),
                "ok": payload.get("ok"),
            },
        )
        return context