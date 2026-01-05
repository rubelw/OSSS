from __future__ import annotations

"""
LangGraphOrchestrationAPI (clean pipeline refactor) — Contract Superset Mode

Fixes applied (from review):
1) ✅ Restore conversation execution_state (by conversation_id) BEFORE normalization.
2) ✅ Persist pending_action after each run so turn 2 can consume it.
3) ✅ Plan application always overwrites config agents with plan.agents when present.
4) ✅ Normalize orchestrator output (AgentContext or dict) -> plain execution_state dict.
5) ✅ Merge upstream exec_state back in after orchestrator.run() (prevents dropped keys).
6) ✅ Unwrap/Wrap conversation store payloads:
   - load() may return {"execution_state": {...}, ...} or raw dict; we unwrap.
   - save() writes {"execution_state": {...}} wrapper payload.
7) ✅ Route semantics hardening:
   - "route" is the contract route/pattern (e.g. "data_query"), NOT the next node.
   - "entry_point" is the graph entry (often "refiner").
   - If orchestrator overwrites route with entry/next-node, we preserve that as "next_node"
     and re-assert the contract route before persistence.
8) ✅ Skip classifier (and any route recomputation side-effects) on pending-action resume turns.

Fixes applied (pending_action “awaiting-only” truth):
9) ✅ Treat “pending action exists” as pending ONLY when awaiting=True.
   - conversation.save / conversation.restore metadata
   - pipeline.normalize_query logging flags
   - workflow.completed metadata
   NOTE: we intentionally DO NOT delete pending_action when cleared (awaiting=False).

Additional hardening applied (from latest review):
10) ✅ Always persist the contract route at save boundary (not only when route_locked=True).
    - Preserve any node-ish returned route as "next_node".
11) ✅ Pending-action resume detection safety fallback:
    - If normalizer couldn't surface "handled" but wrote pending_action_result, treat as resume turn.
"""

import asyncio
import inspect
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol, Tuple

from OSSS.ai.observability import get_logger

# These imports represent your existing architecture; keep your actual paths.
from OSSS.ai.orchestration.orchestrator import LangGraphOrchestrator
from OSSS.ai.orchestration.planning.planner import Planner
from OSSS.ai.orchestration.planning.plan import ExecutionPlan
from OSSS.ai.services.classification_service import ClassificationService
from OSSS.ai.orchestration.pipeline.turn_normalizer import TurnNormalizer  # adjust to your actual module

# ✅ awaiting-only pending_action predicates
from OSSS.ai.orchestration.protocol.pending_action import (
    has_awaiting_pending_action,
    get_pending_action_type,
)

logger = get_logger(__name__)


# -----------------------------
# Conversation State Persistence
# -----------------------------

class ConversationStateStore(Protocol):
    """
    Minimal interface for restoring/persisting conversation execution_state.

    Implementations vary. Some store/return raw execution_state dicts, others
    store/return wrappers like:
        {"execution_state": {...}, "updated_at": "...", ...}

    This API:
      - Unwraps on load
      - Wraps on save
    """

    async def load(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        ...

    async def save(self, conversation_id: str, state: Dict[str, Any]) -> None:
        ...


# -----------------------------
# Request/Response structures
# -----------------------------

@dataclass
class QueryRequest:
    query: str
    conversation_id: Optional[str] = None
    correlation_id: Optional[str] = None
    agents: Optional[list[str]] = None
    execution_config: Optional[Dict[str, Any]] = None
    export_md: bool = False


@dataclass
class QueryResponse:
    text: str
    execution_state: Dict[str, Any]
    workflow_id: str
    conversation_id: str
    correlation_id: str


# -----------------------------
# API Implementation
# -----------------------------

class LangGraphOrchestrationAPI:
    """
    Production Orchestration API wrapper.

    Contract Superset Mode principles:
    - pattern names are canonical contracts: "standard", "data_query"
    - "superset" is compile strategy only: config["compile_variant"]="superset"
    - planning/routing happens before graph compilation
    """

    api_name: str = "langgraph"
    api_version: str = "v1"

    def __init__(
        self,
        orchestrator: LangGraphOrchestrator,
        planner: Planner,
        classifier: ClassificationService,
        turn_normalizer: TurnNormalizer,
        conversation_store: Optional[ConversationStateStore] = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._planner = planner
        self._classifier = classifier
        self._turn_normalizer = turn_normalizer
        self._conversation_store = conversation_store
        self._initialized: bool = False

    # -----------------------------
    # Lifecycle hooks (required by factory)
    # -----------------------------

    async def initialize(self) -> None:
        if self._initialized:
            return

        init_fn = getattr(self._orchestrator, "initialize", None)
        if callable(init_fn):
            res = init_fn()
            if asyncio.iscoroutine(res):
                await res

        self._initialized = True
        logger.info(
            "[orchestration_api] initialized",
            extra={"event": "api.initialize", "api": type(self).__name__},
        )

    async def shutdown(self) -> None:
        if not self._initialized:
            return

        shutdown_fn = getattr(self._orchestrator, "shutdown", None)
        if callable(shutdown_fn):
            res = shutdown_fn()
            if asyncio.iscoroutine(res):
                await res

        self._initialized = False
        logger.info(
            "[orchestration_api] shutdown",
            extra={"event": "api.shutdown", "api": type(self).__name__},
        )

    def clear_graph_cache(self) -> Dict[str, Any]:
        cleared_any = False

        for obj in (self._orchestrator, getattr(self._orchestrator, "graph_factory", None)):
            if obj is None:
                continue
            fn = (
                getattr(obj, "clear_graph_cache", None)
                or getattr(obj, "clear_cache", None)
                or getattr(obj, "reset_cache", None)
            )
            if callable(fn):
                try:
                    fn()
                    cleared_any = True
                except Exception:
                    logger.exception("[orchestration_api] clear_graph_cache delegate failed")

        try:
            if hasattr(self._orchestrator, "_compiled_graph"):
                setattr(self._orchestrator, "_compiled_graph", None)
                cleared_any = True
            if hasattr(self._orchestrator, "_compiled_graph_key"):
                setattr(self._orchestrator, "_compiled_graph_key", None)
                cleared_any = True
            if hasattr(self._orchestrator, "_graph"):
                setattr(self._orchestrator, "_graph", None)
        except Exception:
            pass

        return {"status": "ok", "cleared": bool(cleared_any)}

    # -----------------------------
    # Public entry point
    # -----------------------------

    async def execute_workflow(self, request: QueryRequest) -> QueryResponse:
        """
        Deterministic pipeline:
          1) resolve ids + base config
          2) restore conversation execution_state
          3) normalize turn (wizard / pending_action resume)
          4) classify (unless pending-action resume / lock fast-path)
          5) plan
          6) apply plan to config/state
          7) run orchestrator (compile per-run using plan)
          8) persist updated conversation state (execution_state only)
        """
        t0 = time.time()
        workflow_id = str(uuid.uuid4())

        conversation_id = (request.conversation_id or str(uuid.uuid4())).strip()
        client_corr = (request.correlation_id or conversation_id).strip()

        base_config = self._build_base_config(
            request=request,
            workflow_id=workflow_id,
            conversation_id=conversation_id,
            client_correlation_id=client_corr,
        )

        exec_state: Dict[str, Any] = {
            "workflow_id": workflow_id,
            "conversation_id": conversation_id,
            "client_correlation_id": client_corr,
            "raw_user_text": request.query,
            "original_query": request.query,
            "user_question": request.query,
            "question": request.query,
            "query": request.query,
            "effective_queries": {"user": request.query},
            "wizard_bailed": False,
            "wizard_in_progress": False,
        }

        # (2) Restore conversation execution_state BEFORE normalization/classification
        restored = await self._load_conversation_state(conversation_id)
        if restored:
            exec_state = self._merge_restored_execution_state(
                current=exec_state,
                restored=restored,
            )

        # (3) Normalize turn (pending_action yes/no consumption happens here)
        normalized_text, exec_state = self._normalize_turn(exec_state)

        # ✅ Hardening: if the normalizer/controller left a pending_action_result,
        # treat this as a resume turn even if normalize() return shape couldn't assert handled.
        if not exec_state.get("pending_action_resume_turn"):
            if isinstance(exec_state.get("pending_action_result"), dict):
                exec_state["pending_action_resume_turn"] = True

        effective_query = (normalized_text or request.query).strip()
        base_config["query"] = effective_query
        exec_state["query"] = effective_query
        exec_state["user_question"] = effective_query
        exec_state["question"] = effective_query
        exec_state["effective_queries"] = {"user": effective_query}

        # ---- pending-action resume detection (skip classifier/routers) ----
        # ✅ Resume turns are ONLY those the turn controller/normalizer actually handled
        is_pending_action_resume_turn = bool(exec_state.get("pending_action_resume_turn"))

        # ✅ awaiting-only truth for pending action presence
        has_pending_action = has_awaiting_pending_action(exec_state)

        logger.debug(
            "[orchestration_api] normalized query",
            extra={
                "event": "pipeline.normalize_query",
                "workflow_id": workflow_id,
                "conversation_id": conversation_id,
                "conversation_id_explicit": bool(request.conversation_id),
                "wizard_bailed": exec_state.get("wizard_bailed", False),
                "wizard_in_progress": exec_state.get("wizard_in_progress", False),
                "mode": base_config.get("option_mode"),
                "has_pending_action": has_pending_action,
                "pending_action_type": get_pending_action_type(exec_state) if has_pending_action else None,
                "pending_action_resume_turn": is_pending_action_resume_turn,
                "route_locked": exec_state.get("route_locked", False),
                "route": exec_state.get("route"),
            },
        )

        # (4) Classify (signature-compat) — SKIP on pending-action resume turns
        base_config["execution_state"] = exec_state

        classification = None
        if not is_pending_action_resume_turn:
            route_reason = str(exec_state.get("route_reason") or "").strip().lower()
            route_key = str(exec_state.get("route_key") or "").strip().lower()
            classification = await self._call_classifier(
                query=effective_query,
                workflow_id=workflow_id,
                correlation_id=base_config["correlation_id"],
                config=base_config,
                execution_state=exec_state,
            )

            write_fn = getattr(self._classifier, "write_to_execution_state", None)
            if callable(write_fn):
                try:
                    exec_state = write_fn(exec_state, classification)
                except Exception:
                    logger.exception("[orchestration_api] classifier.write_to_execution_state failed (continuing)")
        else:
            route_reason = str(exec_state.get("route_reason") or "").strip().lower()
            route_key = str(exec_state.get("route_key") or "").strip().lower()

            logger.info(
                "[orchestration_api] skipping classifier on pending-action resume turn",
                extra={
                    "event": "pipeline.skip_classifier",
                    "workflow_id": workflow_id,
                    "conversation_id": conversation_id,
                    "route_reason": route_reason,
                    "route_key": route_key,
                    "route_locked": bool(exec_state.get("route_locked")),
                    "route": exec_state.get("route"),
                    "has_pending_action": has_pending_action,
                    "pending_action_type": get_pending_action_type(exec_state) if has_pending_action else None,
                },
            )

        # (5) Plan (single source of truth; signature-compat)
        plan = self._call_planner(
            query=effective_query,
            config=base_config,
            execution_state=exec_state,
        )

        logger.info(
            "[orchestration_api] planning completed",
            extra={
                "event": "planning.completed",
                "workflow_id": workflow_id,
                "conversation_id": conversation_id,
                "mode": base_config.get("option_mode"),
                "signals": exec_state.get("routing_signals", {}) or {},
                "plan_type": type(plan).__name__,
                "plan_pattern": getattr(plan, "pattern", None),
                "compile_variant": getattr(plan, "compile_variant", None),
                "agents_superset": base_config.get("agents_superset", False),
                "route_locked": bool(exec_state.get("route_locked")),
                "route": exec_state.get("route"),
                "has_pending_action": has_pending_action,
                "pending_action_type": get_pending_action_type(exec_state) if has_pending_action else None,
            },
        )

        # (6) Apply plan to config/state deterministically
        self._apply_plan(base_config, exec_state, plan)

        logger.info(
            "[orchestration_api] plan applied",
            extra={
                "event": "planning.applied",
                "workflow_id": workflow_id,
                "conversation_id": conversation_id,
                "mode": base_config.get("option_mode"),
                "graph_pattern": base_config.get("graph_pattern"),
                "agents": base_config.get("agents"),
                "entry_point": base_config.get("entry_point"),
                "route": exec_state.get("route"),
                "route_locked": exec_state.get("route_locked", False),
                "compile_variant": base_config.get("compile_variant"),
                "agents_superset": base_config.get("agents_superset", False),
                "has_pending_action": has_pending_action,
                "pending_action_type": get_pending_action_type(exec_state) if has_pending_action else None,
            },
        )

        # (7) Run orchestrator (pass exec_state through config for merge into initial_state)
        base_config["execution_state"] = exec_state

        logger.info(
            "[api] Delegating to LangGraphOrchestrator",
            extra={
                "event": "orchestrator.run",
                "workflow_id": workflow_id,
                "correlation_id": base_config["correlation_id"],
                "conversation_id": conversation_id,
                "mode": base_config.get("option_mode"),
                "graph_pattern": base_config.get("graph_pattern"),
                "compile_variant": base_config.get("compile_variant"),
                "agents_superset": base_config.get("agents_superset"),
                "agents": base_config.get("agents"),
                "route": exec_state.get("route"),
                "route_locked": bool(exec_state.get("route_locked")),
                "has_pending_action": has_pending_action,
                "pending_action_type": get_pending_action_type(exec_state) if has_pending_action else None,
            },
        )

        agent_context = await self._orchestrator.run(
            query=effective_query,
            config=base_config,
        )

        result_exec_state, final_text = self._extract_execution_state_and_text(agent_context)

        # ✅ HARDEN: ensure we don't lose keys the orchestrator dropped (pending_action/wizard/locks/etc.)
        if not isinstance(result_exec_state, dict):
            result_exec_state = {}
        result_exec_state = {**exec_state, **result_exec_state}

        # Ensure core ids are present
        result_exec_state.setdefault("workflow_id", workflow_id)
        result_exec_state.setdefault("conversation_id", conversation_id)
        result_exec_state.setdefault("client_correlation_id", client_corr)

        # -----------------------------
        # ✅ ROUTE SEMANTICS FIX (critical)
        # -----------------------------
        # "route" is the contract route/pattern (e.g. "data_query"), not the next node.
        # Preserve any node-ish value as next_node, but ALWAYS persist contract route.
        contract_route = (exec_state.get("route") or base_config.get("graph_pattern") or "standard")
        contract_route = str(contract_route).strip().lower()

        returned_route = result_exec_state.get("route")
        returned_route_norm = str(returned_route).strip().lower() if isinstance(returned_route, str) else None

        # If someone wrote a node name into `route`, preserve it as next_node.
        if returned_route_norm and returned_route_norm != contract_route:
            result_exec_state.setdefault("next_node", returned_route_norm)

        # Always persist the contract route, locked or not.
        result_exec_state["route"] = contract_route

        # Always keep entry_point explicitly from plan/config (avoid accidental overwrites).
        result_exec_state["entry_point"] = str(
            base_config.get("entry_point") or getattr(plan, "entry_point", None) or "refiner"
        ).strip().lower()

        # (8) Persist updated conversation execution_state (persist wrapper payload)
        await self._save_conversation_state(conversation_id, result_exec_state)

        elapsed_ms = (time.time() - t0) * 1000.0

        # ✅ awaiting-only at completion boundary too
        result_has_pending_action = has_awaiting_pending_action(result_exec_state)
        result_pa_type = get_pending_action_type(result_exec_state) if result_has_pending_action else None

        logger.info(
            "[orchestration_api] workflow complete",
            extra={
                "event": "workflow.completed",
                "workflow_id": workflow_id,
                "conversation_id": conversation_id,
                "elapsed_ms": elapsed_ms,
                "has_pending_action": result_has_pending_action,
                "pending_action_type": result_pa_type,
                "route_locked": bool(result_exec_state.get("route_locked")),
                "route": result_exec_state.get("route"),
                "entry_point": result_exec_state.get("entry_point"),
                "next_node": result_exec_state.get("next_node"),
            },
        )

        return QueryResponse(
            text=final_text,
            execution_state=result_exec_state,
            workflow_id=workflow_id,
            conversation_id=conversation_id,
            correlation_id=client_corr,
        )

    # -----------------------------
    # Helpers
    # -----------------------------

    def _build_base_config(
        self,
        request: QueryRequest,
        workflow_id: str,
        conversation_id: str,
        client_correlation_id: str,
    ) -> Dict[str, Any]:
        execution_cfg = request.execution_config or {}
        timeout_seconds = int(execution_cfg.get("timeout_seconds", 180))
        use_rag = bool(execution_cfg.get("use_rag", True))
        top_k = int(execution_cfg.get("top_k", 6))

        config: Dict[str, Any] = {
            "workflow_id": workflow_id,
            "workflow_run_id": workflow_id,
            "conversation_id": conversation_id,
            "thread_id": conversation_id,
            "client_correlation_id": client_correlation_id,
            "correlation_id": f"wf-{uuid.uuid4()}",
            "query": request.query,
            "timeout_seconds": timeout_seconds,
            "use_rag": use_rag,
            "top_k": top_k,
            "parallel_execution": bool(execution_cfg.get("parallel_execution", True)),
            "use_llm_intent": bool(execution_cfg.get("use_llm_intent", True)),
            "option_mode": "contract_superset",
            "compile_variant": "superset",
            "agents_superset": True,
            "graph_pattern": "standard",
            "agents": (request.agents if request.agents else []),
            "export_md": bool(request.export_md),
        }
        return config

    def _unwrap_loaded_state(self, loaded: Dict[str, Any]) -> Dict[str, Any]:
        """
        A) Conversation store may return a wrapper: {"execution_state": {...}, ...}
           - Restore unwraps it.
        """
        if not isinstance(loaded, dict):
            return {}

        maybe_state = loaded.get("execution_state")
        if isinstance(maybe_state, dict):
            # Optionally keep meta if you want it later
            return dict(maybe_state)

        # Otherwise treat as raw execution_state dict
        return dict(loaded)

    def _wrap_state_for_save(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        A) Persist writes wrapper payload (store can unwrap if it wants raw).
        """
        return {"execution_state": state}

    async def _load_conversation_state(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        if not self._conversation_store:
            return None
        try:
            loaded = await self._conversation_store.load(conversation_id)
            if not isinstance(loaded, dict) or not loaded:
                return None

            restored = self._unwrap_loaded_state(loaded)
            if not restored:
                return None

            # ✅ awaiting-only metadata
            has_pa = has_awaiting_pending_action(restored)
            pa_type = get_pending_action_type(restored) if has_pa else None

            logger.debug(
                "[orchestration_api] restored conversation state",
                extra={
                    "event": "conversation.restore",
                    "conversation_id": conversation_id,
                    "restored_keys": list(restored.keys())[:50],
                    "has_pending_action": has_pa,
                    "pending_action_type": pa_type,
                    "has_wizard": bool(restored.get("wizard")),
                    "route_locked": bool(restored.get("route_locked")),
                    "route": restored.get("route"),
                },
            )
            return restored
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "[orchestration_api] conversation restore failed (continuing without it)",
                extra={"event": "conversation.restore_failed", "conversation_id": conversation_id, "error": str(exc)},
            )
            return None

    async def _save_conversation_state(self, conversation_id: str, state: Dict[str, Any]) -> None:
        if not self._conversation_store:
            return
        try:
            payload = self._wrap_state_for_save(state)
            await self._conversation_store.save(conversation_id, payload)

            # ✅ awaiting-only metadata
            has_pa = has_awaiting_pending_action(state)
            pa_type = get_pending_action_type(state) if has_pa else None

            logger.debug(
                "[orchestration_api] persisted conversation state",
                extra={
                    "event": "conversation.save",
                    "conversation_id": conversation_id,
                    "has_pending_action": has_pa,
                    "pending_action_type": pa_type,
                    "has_wizard": bool(state.get("wizard")),
                    "route_locked": bool(state.get("route_locked")),
                    "route": state.get("route"),
                    "entry_point": state.get("entry_point"),
                },
            )
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "[orchestration_api] conversation save failed (continuing)",
                extra={"event": "conversation.save_failed", "conversation_id": conversation_id, "error": str(exc)},
            )

    def _merge_restored_execution_state(self, current: Dict[str, Any], restored: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(restored)

        merged["workflow_id"] = current["workflow_id"]
        merged["conversation_id"] = current["conversation_id"]
        merged["client_correlation_id"] = current["client_correlation_id"]

        for k in ("raw_user_text", "user_question", "question", "query", "effective_queries"):
            merged[k] = current.get(k)

        restored_oq = merged.get("original_query")
        if not (isinstance(restored_oq, str) and restored_oq.strip()):
            merged["original_query"] = current.get("original_query")

        merged.setdefault("wizard_bailed", False)
        merged.setdefault("wizard_in_progress", False)

        if "pending_action" in merged and merged["pending_action"] is not None and not isinstance(merged["pending_action"], dict):
            merged["pending_action"] = None
        if "wizard" in merged and merged["wizard"] is not None and not isinstance(merged["wizard"], dict):
            merged["wizard"] = None

        return merged

    def _normalize_turn(self, exec_state: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        raw_text = (exec_state.get("raw_user_text") or "").strip()
        fn = getattr(self._turn_normalizer, "normalize", None)
        if not callable(fn):
            return raw_text, exec_state

        # ✅ default to False each turn; only the controller/normalizer can flip it.
        exec_state["pending_action_resume_turn"] = False

        try:
            sig = inspect.signature(fn)
            params = sig.parameters
            accepts_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())

            if accepts_var_kw:
                result = fn(exec_state=exec_state, raw_user_text=raw_text)
            else:
                candidates = {
                    "exec_state": exec_state,
                    "state": exec_state,
                    "execution_state": exec_state,
                    "raw_user_text": raw_text,
                    "user_text": raw_text,
                    "text": raw_text,
                    "query": raw_text,
                }
                payload = {k: v for k, v in candidates.items() if k in params}

                if payload:
                    result = fn(**payload)
                else:
                    result = fn(exec_state, raw_text)
        except TypeError:
            try:
                result = fn(exec_state, raw_text)
            except TypeError:
                result = fn(raw_text, exec_state)
        except Exception:
            logger.exception("[orchestration_api] TurnNormalizer.normalize failed (continuing)")
            return raw_text, exec_state

        # ------------------------------------------------------------------
        # ✅ resume_turn depends ONLY on whether the normalizer/controller
        # actually handled the raw user text this turn.
        #
        # - If handled: canonical_user_text is authoritative (often pending_question).
        # - If not handled: use raw_text and do NOT mark resume.
        # ------------------------------------------------------------------

        # TurnNormalizer may return dict-like results
        if isinstance(result, dict):
            handled = bool(result.get("handled")) if "handled" in result else False
            canonical = (result.get("canonical_user_text") or "").strip()

            if handled:
                exec_state["pending_action_resume_turn"] = True
                return canonical, exec_state

            exec_state["pending_action_resume_turn"] = False
            return raw_text, exec_state

        # Or it may return a NormalizeResult-like object
        handled = getattr(result, "handled", None)
        canonical = getattr(result, "canonical_user_text", None)

        if isinstance(handled, bool) and handled:
            exec_state["pending_action_resume_turn"] = True

            if isinstance(canonical, str):
                return canonical.strip(), exec_state

            # handled but no canonical -> treat as empty canonical
            return "", exec_state

        exec_state["pending_action_resume_turn"] = False

        if isinstance(result, tuple) and len(result) == 2:
            canonical_text = (result[0] or "").strip()
            st = result[1]
            if isinstance(st, dict):
                exec_state = st

            # tuple-return legacy API cannot assert handled; treat as NOT a resume turn
            exec_state.setdefault("pending_action_resume_turn", False)

            return canonical_text or raw_text, exec_state

        return raw_text, exec_state

    async def _call_classifier(
        self,
        *,
        query: str,
        workflow_id: str,
        correlation_id: str,
        config: Dict[str, Any],
        execution_state: Dict[str, Any],
    ) -> Any:
        classify_fn = getattr(self._classifier, "classify", None)
        if not callable(classify_fn):
            logger.warning("[orchestration_api] classifier has no classify(); skipping classification")
            return None

        candidates: Dict[str, Any] = {
            "query": query,
            "text": query,
            "question": query,
            "workflow_id": workflow_id,
            "workflow_run_id": workflow_id,
            "correlation_id": correlation_id,
            "config": config,
            "execution_state": execution_state,
            "exec_state": execution_state,
            "state": execution_state,
        }

        try:
            sig = inspect.signature(classify_fn)
            params = sig.parameters
            accepts_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())

            if accepts_var_kw:
                payload = {
                    "query": query,
                    "workflow_id": workflow_id,
                    "correlation_id": correlation_id,
                    "config": config,
                    "execution_state": execution_state,
                }
                result = classify_fn(**payload)
            else:
                payload = {k: v for k, v in candidates.items() if k in params}
                if payload:
                    result = classify_fn(**payload)
                else:
                    try:
                        result = classify_fn(query)
                    except TypeError:
                        result = classify_fn(query, config, execution_state)

        except TypeError:
            try:
                result = classify_fn(query)
            except TypeError:
                result = classify_fn(query, config, execution_state)
        except Exception:
            logger.exception("[orchestration_api] classifier.classify failed (continuing without classification)")
            return None

        if asyncio.iscoroutine(result):
            try:
                return await result
            except Exception:
                logger.exception("[orchestration_api] classifier.classify coroutine failed (continuing)")
                return None

        return result

    def _call_planner(
        self,
        *,
        query: str,
        config: Dict[str, Any],
        execution_state: Dict[str, Any],
    ) -> ExecutionPlan:
        plan_fn = getattr(self._planner, "plan", None)
        if not callable(plan_fn):
            raise TypeError("Planner has no callable plan()")

        sig = inspect.signature(plan_fn)
        params = sig.parameters
        accepts_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())

        pool: Dict[str, Any] = {
            "query": query,
            "text": query,
            "question": query,
            "config": config,
            "exec_state": execution_state,
            "execution_state": execution_state,
            "state": execution_state,
        }

        request_payload: Dict[str, Any] = dict(pool)
        pool["request"] = request_payload

        if accepts_var_kw:
            kwargs = dict(pool)
        else:
            kwargs = {k: v for k, v in pool.items() if k in params}

        for name, p in params.items():
            if p.kind == inspect.Parameter.KEYWORD_ONLY and p.default is inspect._empty:
                if name not in kwargs and name in pool:
                    kwargs[name] = pool[name]

        try:
            return plan_fn(**kwargs)
        except Exception:
            logger.exception(
                "[orchestration_api] planner.plan failed",
                extra={
                    "planner": type(self._planner).__name__,
                    "signature": str(sig),
                    "passed_kwargs": sorted(kwargs.keys()),
                },
            )
            raise

    def _apply_plan(self, config: Dict[str, Any], exec_state: Dict[str, Any], plan: ExecutionPlan) -> None:
        if hasattr(plan, "to_dict") and callable(getattr(plan, "to_dict")):
            try:
                exec_state["execution_plan"] = plan.to_dict()  # type: ignore[assignment]
            except Exception:
                exec_state["execution_plan"] = {
                    "pattern": getattr(plan, "pattern", None),
                    "agents": getattr(plan, "agents", None),
                    "entry_point": getattr(plan, "entry_point", None),
                    "compile_variant": getattr(plan, "compile_variant", None),
                    "route": getattr(plan, "route", None),
                    "route_locked": getattr(plan, "route_locked", None),
                }
        else:
            exec_state["execution_plan"] = {
                "pattern": getattr(plan, "pattern", None),
                "agents": getattr(plan, "agents", None),
                "entry_point": getattr(plan, "entry_point", None),
                "compile_variant": getattr(plan, "compile_variant", None),
                "route": getattr(plan, "route", None),
                "route_locked": getattr(plan, "route_locked", None),
            }

        pattern = (getattr(plan, "pattern", None) or "standard").strip().lower()
        config["graph_pattern"] = pattern

        compile_variant = (
            getattr(plan, "compile_variant", None) or config.get("compile_variant") or "default"
        ).strip().lower()
        config["compile_variant"] = compile_variant

        entry_point = (getattr(plan, "entry_point", None) or "refiner").strip().lower()
        config["entry_point"] = entry_point

        plan_agents = getattr(plan, "agents", None)
        if plan_agents:
            config["agents"] = [str(a).strip().lower() for a in plan_agents if str(a).strip()]

        # "route" should mean contract route/pattern; default to plan.pattern if plan.route absent.
        plan_route = getattr(plan, "route", None)
        plan_locked = getattr(plan, "route_locked", None)

        if plan_route:
            exec_state["route"] = str(plan_route).strip().lower()
        else:
            exec_state.setdefault("route", pattern)

        if plan_locked is True:
            exec_state["route_locked"] = True

        exec_state["planned_graph_pattern"] = config["graph_pattern"]
        exec_state["planned_agents"] = config.get("agents", [])
        exec_state["entry_point"] = config.get("entry_point", "refiner")

    def _extract_execution_state_and_text(self, agent_context: Any) -> Tuple[Dict[str, Any], str]:
        if isinstance(agent_context, dict):
            state = agent_context
            text = (state.get("final") or state.get("response") or state.get("final_answer") or "").strip()
            return state, text

        exec_state: Dict[str, Any] = {}

        try:
            raw_exec_state = getattr(agent_context, "execution_state", None)
            if isinstance(raw_exec_state, dict):
                exec_state = dict(raw_exec_state)
        except Exception:
            exec_state = {}

        final_text = ""

        try:
            outputs = getattr(agent_context, "agent_outputs", None)
            if isinstance(outputs, dict):
                for k in ("final", "response", "final_answer"):
                    v = outputs.get(k)
                    if isinstance(v, str) and v.strip():
                        final_text = v.strip()
                        break
        except Exception:
            pass

        if not final_text:
            for k in ("final", "response", "final_answer"):
                v = exec_state.get(k)
                if isinstance(v, str) and v.strip():
                    final_text = v.strip()
                    break

        return exec_state, final_text


# -----------------------------
# Minimal default constructor
# -----------------------------

def build_langgraph_api(
    orchestrator: LangGraphOrchestrator,
    planner: Planner,
    classifier: ClassificationService,
    turn_normalizer: TurnNormalizer,
    conversation_store: Optional[ConversationStateStore] = None,
) -> LangGraphOrchestrationAPI:
    return LangGraphOrchestrationAPI(
        orchestrator=orchestrator,
        planner=planner,
        classifier=classifier,
        turn_normalizer=turn_normalizer,
        conversation_store=conversation_store,
    )
