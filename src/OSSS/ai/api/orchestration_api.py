"""
LangGraph Orchestration API implementation.

Production implementation of OrchestrationAPI that wraps the existing
LangGraphOrchestrator to provide a stable external interface.

Design goals of this module:
- Provide a *stable* API surface (OrchestrationAPI) to external callers
  even if the internal orchestration engine changes over time.
- Centralize lifecycle operations (initialize/shutdown).
- Track active workflows for status endpoints and basic observability.
- Emit workflow lifecycle events (started/completed) for telemetry.
- Persist workflow metadata/results to the database without making DB failures
  break the user-facing API response.
- Support optional markdown export and optional persistence of that export.
"""

# ---------------------------------------------------------------------------
# Standard library imports
# ---------------------------------------------------------------------------

import uuid                 # Unique workflow IDs (UUID4)
import asyncio              # Async primitives (sleep, cancellation patterns)
import time                 # Wall-clock timing for execution durations
from typing import Dict, Any, Optional, List, Awaitable, Callable
from datetime import datetime, timezone  # UTC timestamps for telemetry/metadata
from pathlib import Path     # Filesystem paths (markdown export)
import json
import re

from OSSS.ai.analysis.pipeline import analyze_query
from OSSS.ai.analysis.policy import build_execution_plan
from OSSS.ai.analysis.models import QueryProfile
from OSSS.ai.analysis.rules.types import RuleHit


from OSSS.ai.config.openai_config import OpenAIConfig
from OSSS.ai.llm.openai import OpenAIChatLLM

# ---------------------------------------------------------------------------
# OSSS / OSSS API contracts and models
# ---------------------------------------------------------------------------

from OSSS.ai.api.external import OrchestrationAPI
from OSSS.ai.api.models import (
    WorkflowRequest,        # Input request model for workflow execution
    WorkflowResponse,       # Output response model for workflow execution
    StatusResponse,         # Response model for status polling
)
from OSSS.ai.api.base import APIHealthStatus          # API-level health response model
from OSSS.ai.diagnostics.health import HealthStatus   # Health enum: HEALTHY/DEGRADED/UNHEALTHY

# Decorator that ensures initialize() has been called before API methods run
from OSSS.ai.api.decorators import ensure_initialized

# The production orchestrator that actually runs the LangGraph pipeline
from OSSS.ai.orchestration.orchestrator import LangGraphOrchestrator

# Observability helpers (structured logger)
from OSSS.ai.observability import get_logger

# Workflow lifecycle events (for metrics/traces/audit logs)
from OSSS.ai.events import emit_workflow_started, emit_workflow_completed

# Database / persistence infrastructure
from OSSS.ai.database.connection import get_session_factory
from OSSS.ai.database.repositories.question_repository import QuestionRepository
from OSSS.ai.database.session_factory import DatabaseSessionFactory
from OSSS.ai.llm.utils import call_llm_text

from OSSS.ai.analysis.models import build_routing_decision
from OSSS.ai.orchestration.graph_registry import GRAPH_REGISTRY


# Module-level logger (structured)
logger = get_logger(__name__)

_ALLOWED_ACTIONS = {"read", "troubleshoot", "create", "review", "explain", "route"}

_ACTION_ALIASES = {
    "inform": "explain",
    "information": "explain",
    "answer": "explain",
    "respond": "explain",
    "debug": "troubleshoot",
    "diagnose": "troubleshoot",
    "fix": "troubleshoot",
    "research": "read",
    "lookup": "read",
    "search": "read",
    "plan": "route",
}

_TOP_LEVEL_ALIASES = {
    # common camelCase / variants -> your schema keys
    "intentConfidence": "intent_confidence",
    "subIntent": "sub_intent",
    "subIntentConfidence": "sub_intent_confidence",
    "sub_intentConfidence": "sub_intent_confidence",
    "toneConfidence": "tone_confidence",
    "matchedRules": "matched_rules",
}

_ALLOWED_TOP_KEYS = {
    "intent",
    "intent_confidence",
    "tone",
    "tone_confidence",
    "sub_intent",
    "sub_intent_confidence",
    "signals",
    "matched_rules",
}

AsyncRunner = Callable[[str, Dict[str, Any]], Awaitable[Any]]

def coerce_rule_hits(raw: Any) -> List[RuleHit]:
    hits: List[RuleHit] = []
    if not raw:
        return hits

    items = raw if isinstance(raw, list) else [raw]

    # allowed keys only (respects RuleHit schema)
    allowed_keys = set(RuleHit.model_fields.keys())

    for item in items:
        if isinstance(item, RuleHit):
            hits.append(item)
            continue

        if isinstance(item, dict):
            d: Dict[str, Any] = {k: v for k, v in item.items() if k in allowed_keys}

            # common fallbacks / aliases
            if "rule" not in d:
                if "rule_id" in item and isinstance(item["rule_id"], str):
                    d["rule"] = item["rule_id"]
                elif "id" in item and isinstance(item["id"], str):
                    d["rule"] = item["id"]

            if "score" not in d:
                # your logs used "confidence"; map it -> score if present
                if "confidence" in item and isinstance(item["confidence"], (int, float)):
                    d["score"] = float(item["confidence"])

            hits.append(RuleHit.model_validate(d))
            continue

        # ignore unknown types
    return hits

def _fire_and_forget(maybe_awaitable: Any) -> None:
    """
    Safely handle both sync and async event emitters.
    - If emitter returns a coroutine/awaitable, schedule it.
    - If emitter is sync (returns None), do nothing extra.
    Never raises.
    """
    try:
        if asyncio.iscoroutine(maybe_awaitable) or isinstance(maybe_awaitable, Awaitable):
            asyncio.create_task(maybe_awaitable)
    except Exception:
        pass


def _sanitize_query_profile_dict(data: dict) -> dict:
    """
    Make LLM JSON safe for QueryProfile(extra=forbid):
    - rename common alias keys
    - drop unknown top-level keys
    - coerce required strings / floats
    - normalize matched_rules into strict RuleHit shape + action enum
    """
    if not isinstance(data, dict):
        return {}

    # 1) rename aliases
    for src, dst in _TOP_LEVEL_ALIASES.items():
        if src in data and dst not in data:
            data[dst] = data.pop(src)

    # 2) drop unknown top-level keys (extra=forbid)
    cleaned = {k: data[k] for k in list(data.keys()) if k in _ALLOWED_TOP_KEYS}

    # 3) required-ish fields with safe coercion
    def _as_str(v, default: str) -> str:
        if isinstance(v, str) and v.strip():
            return v.strip()
        return default

    def _as_float(v, default: float) -> float:
        try:
            if v is None:
                return default
            return float(v)
        except Exception:
            return default

    cleaned["intent"] = _as_str(cleaned.get("intent"), "general")
    cleaned["tone"] = _as_str(cleaned.get("tone"), "neutral")
    cleaned["sub_intent"] = _as_str(cleaned.get("sub_intent"), "general")

    cleaned["intent_confidence"] = _as_float(cleaned.get("intent_confidence"), 0.50)
    cleaned["tone_confidence"] = _as_float(cleaned.get("tone_confidence"), 0.50)
    cleaned["sub_intent_confidence"] = _as_float(cleaned.get("sub_intent_confidence"), 0.50)

    if not isinstance(cleaned.get("signals"), dict):
        cleaned["signals"] = {}

    # 4) normalize matched_rules and action values
    mr = _normalize_rule_hits(cleaned.get("matched_rules"))
    hits = coerce_rule_hits(mr)
    cleaned["matched_rules"] = [h.model_dump() for h in hits]

    return cleaned


def _normalize_rule_hits(value: Any) -> list[dict]:
    """
    Normalize various rule-hit shapes into:
      {"rule": str, "action": str, "category"?: str, "score"?: number, "meta"?: object}
    Drops unknown keys to satisfy Pydantic "extra=forbid".
    """
    if not value:
        return []

    out: list[dict] = []

    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                out.append({"rule": item, "action": "read"})
                continue

            if not isinstance(item, dict):
                continue

            # Map possible identifiers -> "rule"
            rule = (
                item.get("rule")
                or item.get("rule_id")
                or item.get("id")
                or item.get("name")
                or item.get("label")  # last resort
            )
            if not isinstance(rule, str) or not rule.strip():
                continue

            hit: dict = {
                "rule": rule.strip(),
                "action": item.get("action") if isinstance(item.get("action"), str) else "read",
            }

            if isinstance(item.get("category"), str):
                hit["category"] = item["category"]

            # score/confidence normalization
            if isinstance(item.get("score"), (int, float)):
                hit["score"] = float(item["score"])
            elif isinstance(item.get("confidence"), (int, float)):
                hit["score"] = float(item["confidence"])

            # meta: preserve anything else useful but keep it under "meta"
            meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
            # stash common extras into meta so we don't violate schema
            for k in ("label", "tone", "sub_intent", "parent_intent"):
                if k in item and k not in meta:
                    meta[k] = item[k]
            if meta:
                hit["meta"] = meta

            out.append(hit)

    return out


def _coerce_llm_text(raw: Any) -> str:
    """
    Normalize common LLM client return shapes into plain assistant text.
    Supports:
      - plain string
      - OpenAI-style dict: {"choices":[{"message":{"content":"..."}}]}
      - {"content": "..."} or {"text": "..."}
      - objects with .content / .text
    """
    if raw is None:
        return ""

    if isinstance(raw, str):
        return raw

    if isinstance(raw, dict):
        # OpenAI / compatible
        if "choices" in raw and isinstance(raw["choices"], list) and raw["choices"]:
            ch0 = raw["choices"][0]
            if isinstance(ch0, dict):
                msg = ch0.get("message")
                if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                    return msg["content"]
                # sometimes "text" exists directly
                if isinstance(ch0.get("text"), str):
                    return ch0["text"]

        if isinstance(raw.get("content"), str):
            return raw["content"]
        if isinstance(raw.get("text"), str):
            return raw["text"]

        return str(raw)

    # pydantic / dataclasses / custom objects
    for attr in ("content", "text"):
        v = getattr(raw, attr, None)
        if isinstance(v, str):
            return v

    return str(raw)

def _extract_first_json_object(text: str) -> str:
    """
    Best-effort: pull the first {...} JSON object out of an LLM response.
    Handles cases like:
      - leading text
      - ```json fences
      - trailing commentary
    """
    if not text:
        raise ValueError("empty LLM response")

    # strip fenced blocks
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    # Try direct JSON first
    try:
        json.loads(text)
        return text
    except Exception:
        pass

    # Find the first {...} block
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        raise ValueError("no JSON object found in response")

    candidate = m.group(0)
    json.loads(candidate)  # validate
    return candidate





class LangGraphOrchestrationAPI(OrchestrationAPI):
    """
    Production orchestration API wrapping LangGraphOrchestrator.

    This class is the "public" façade:
    - It owns the orchestrator instance and its lifecycle.
    - It exposes stable API methods (execute_workflow, status, cancel, metrics).
    - It adapts internal AgentContext results into API response models.
    - It integrates observability: health checks, metrics, event emission.
    - It integrates persistence: store workflow results and optional markdown.
    """

    def __init__(self) -> None:
        # -------------------------------------------------------------------
        # Internal orchestration engine
        # -------------------------------------------------------------------
        # Created lazily during initialize(). Keep None until then to avoid
        # importing/constructing complex dependencies during module import.
        self._orchestrator: Optional[LangGraphOrchestrator] = None

        # Tracks whether initialize() has been run.
        # The ensure_initialized decorator uses this as part of its checks.
        self._initialized = False

        # -------------------------------------------------------------------
        # In-memory workflow tracking
        # -------------------------------------------------------------------
        # This is used for:
        # - status polling (/status)
        # - simple metrics (active workflow counts)
        # - debugging in development
        #
        # NOTE: This is process-local memory; it will not survive restarts.
        self._active_workflows: Dict[str, Dict[str, Any]] = {}

        # A simple counter of how many workflows this API instance has processed.
        self._total_workflows = 0

        # -------------------------------------------------------------------
        # Database session factories
        # -------------------------------------------------------------------
        # Primary session factory used for persisting Question records.
        self._session_factory = get_session_factory()

        # Optional "repository factory" session manager used for historian
        # document persistence (markdown export).
        self._db_session_factory: Optional[DatabaseSessionFactory] = None

        # -------------------------------------------------------------------
        # Query profile idempotency (prevents double LLM calls)
        # -------------------------------------------------------------------
        self._query_profile_cache: Dict[str, Dict[str, Any]] = {}   # workflow_id -> query_profile dict
        self._query_profile_locks: Dict[str, asyncio.Lock] = {}     # workflow_id -> lock

    def _get_query_profile_lock(self, workflow_id: str) -> asyncio.Lock:
        lock = self._query_profile_locks.get(workflow_id)
        if lock is None:
            lock = asyncio.Lock()
            self._query_profile_locks[workflow_id] = lock
        return lock

    async def _ensure_query_profile(
        self,
        *,
        workflow_id: str,
        query: str,
        use_llm_intent: bool,
        llm: Optional[Any],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Ensure query_profile exists for this workflow_id exactly once.
        Caches result in:
          - self._query_profile_cache[workflow_id]
          - self._active_workflows[workflow_id]["query_profile"]
          - config["query_profile"]
        """
        # 1) Fast paths (already computed somewhere)
        cached = self._query_profile_cache.get(workflow_id)
        if isinstance(cached, dict) and cached:
            config["query_profile"] = cached
            if workflow_id in self._active_workflows:
                self._active_workflows[workflow_id]["query_profile"] = cached
            return cached

        existing = config.get("query_profile")
        if isinstance(existing, dict) and existing:
            self._query_profile_cache[workflow_id] = existing
            if workflow_id in self._active_workflows:
                self._active_workflows[workflow_id]["query_profile"] = existing
            return existing

        wf_existing = None
        if workflow_id in self._active_workflows:
            wf_existing = self._active_workflows[workflow_id].get("query_profile")
        if isinstance(wf_existing, dict) and wf_existing:
            self._query_profile_cache[workflow_id] = wf_existing
            config["query_profile"] = wf_existing
            return wf_existing

        # 2) Compute exactly once (lock protects concurrency + multi-callers)
        lock = self._get_query_profile_lock(workflow_id)
        async with lock:
            # Re-check after acquiring lock
            cached2 = self._query_profile_cache.get(workflow_id)
            if isinstance(cached2, dict) and cached2:
                config["query_profile"] = cached2
                if workflow_id in self._active_workflows:
                    self._active_workflows[workflow_id]["query_profile"] = cached2
                return cached2

            # Compute (LLM best-effort or rules)
            if use_llm_intent:
                if llm is None:
                    from OSSS.ai.llm.openai import OpenAIChatLLM
                    from OSSS.ai.config.openai_config import OpenAIConfig
                    cfg = OpenAIConfig.load()
                    llm = OpenAIChatLLM(api_key=cfg.api_key, model=cfg.model, base_url=cfg.base_url)

                prof = await self._llm_analyze_query_profile_best_effort(query, llm=llm)
                prof.signals = dict(prof.signals or {})
                prof.signals["use_llm_intent"] = True
                qp = prof.model_dump(mode="json")
            else:
                prof = analyze_query(query)
                prof.signals = dict(prof.signals or {})
                prof.signals.setdefault("analysis_source", "rules")
                qp = prof.model_dump(mode="json")

            # Store everywhere
            self._query_profile_cache[workflow_id] = qp
            config["query_profile"] = qp
            if workflow_id in self._active_workflows:
                self._active_workflows[workflow_id]["query_profile"] = qp

            return qp

    def _extract_effective_queries(
            self,
            *,
            base_query: str,
            executed_agents: List[str],
            exec_state: Dict[str, Any],
    ) -> Dict[str, str]:
        """
        Build per-agent query text for analysis.

        Preferred:
          exec_state["effective_queries"][agent]
        Fallback:
          base_query
        """
        effective_queries: Dict[str, str] = {}

        eq = exec_state.get("effective_queries")
        if isinstance(eq, dict):
            for agent in executed_agents:
                v = eq.get(agent)
                if isinstance(v, str) and v.strip():
                    effective_queries[agent] = v.strip()

        for agent in executed_agents:
            effective_queries.setdefault(agent, (base_query or "").strip())

        return effective_queries



    async def _llm_analyze_query_profile_best_effort(
            self,
            query: str,
            *,
            llm: Any,
    ) -> QueryProfile:
        """
        Ask the LLM to produce a QueryProfile for a single query.

        Best-effort:
          - returns QueryProfile
          - falls back to deterministic analyze_query on any error
        """
        q = (query or "").strip()
        if not q:
            prof = QueryProfile()
            prof.signals = dict(prof.signals or {})
            prof.signals["analysis_source"] = "rules_fallback"
            prof.signals["empty_query"] = True
            return prof

        raw: Any = None
        text: str = ""  # ✅ always defined (prevents "text referenced before assignment")
        try:
            prompt = f"""
You are a classifier. Return ONLY valid JSON that matches this schema EXACTLY.
Do not add any extra keys.

Schema:
{{
  "intent": "string",
  "intent_confidence": 0.0,
  "tone": "string",
  "tone_confidence": 0.0,
  "sub_intent": "string",
  "sub_intent_confidence": 0.0,
  "signals": {{}},
  "matched_rules": [
    {{
      "rule": "string",
      "action": "read|write|update|delete",
      "category": "intent|tone|sub_intent|policy",
      "score": 0.0,
      "meta": {{}}
    }}
  ]
}}

Query:
{q}
""".strip()

            # ✅ log marker so we can prove we reached the LLM path
            logger.info(
                "Calling LLM for query_profile",
                extra={
                    "query_preview": q[:200],
                    "llm_type": type(llm).__name__,
                },
            )



            raw = await call_llm_text(llm, prompt)

            text = _coerce_llm_text(raw).strip()
            if not text:
                raise ValueError("LLM returned empty content")

            # ---- Attempt structured JSON path ----
            try:
                json_text = _extract_first_json_object(text)
                data = json.loads(json_text)

                # ✅ sanitize/alias/drop extras + normalize rule hits/action enum
                data = _sanitize_query_profile_dict(data)

                # ✅ Fix B: coerce matched_rules into strict RuleHit shape
                try:
                    hits = coerce_rule_hits(data.get("matched_rules"))
                    data["matched_rules"] = [h.model_dump() for h in hits]
                except Exception:
                    data["matched_rules"] = []

                prof = QueryProfile.model_validate(data)
                prof.signals = dict(prof.signals or {})
                prof.signals["analysis_source"] = "llm"
                prof.signals["llm_parse_mode"] = "json"
                return prof

            except Exception as parse_error:
                # ---- Token fallback path (keeps system useful even if JSON is messy) ----
                # NOTE: we only try to salvage intent here; other fields stay neutral.
                ALLOWED_INTENTS = {
                    "general", "analyze", "explain", "howto", "summarize",
                    "troubleshoot", "create", "review", "route",
                }

                token_prompt = f"""Return ONLY ONE WORD: one of {sorted(ALLOWED_INTENTS)}.
Query: {q}
Intent:"""

                logger.info(
                    "LLM query_profile JSON parse failed; attempting token fallback",
                    extra={"error": str(parse_error)},
                )

                raw2 = None
                text2 = ""
                try:
                    raw2 = await call_llm_text(llm, token_prompt)
                    text2 = _coerce_llm_text(raw2).strip().lower()

                except Exception:
                    text2 = ""

                intent = (text2.split()[0] if text2 else "").strip()
                if intent not in ALLOWED_INTENTS:
                    # final fallback: deterministic rules
                    raise parse_error

                data = {
                    "intent": intent,
                    "intent_confidence": 0.70,  # conservative but "usable"
                    "tone": "neutral",
                    "tone_confidence": 0.50,
                    "sub_intent": "general",
                    "sub_intent_confidence": 0.50,
                    "signals": {
                        "analysis_source": "llm",
                        "llm_parse_mode": "token_fallback",
                        "llm_json_parse_error": str(parse_error),
                    },
                    "matched_rules": [],
                }

                # ✅ Fix B: coerce matched_rules into strict RuleHit shape
                try:
                    hits = coerce_rule_hits(data.get("matched_rules"))
                    data["matched_rules"] = [h.model_dump() for h in hits]
                except Exception:
                    data["matched_rules"] = []

                prof = QueryProfile.model_validate(data)
                return prof

        except Exception as e:
            logger.warning(
                "LLM query_profile failed; falling back to rules",
                extra={
                    "error": str(e),
                    "raw_type": (type(raw).__name__ if raw is not None else None),
                    "text_preview": (text[:500] if text else None),
                },
            )
            prof = analyze_query(q)
            prof.signals = dict(prof.signals or {})
            prof.signals["analysis_source"] = "rules_fallback"
            prof.signals["llm_query_profile_error"] = str(e)
            prof.signals["llm_query_profile_fallback"] = True
            return prof

    async def _llm_analyze_agent_queries(
            self,
            agent_queries: Dict[str, str],
            *,
            llm: Optional[Any] = None,
    ) -> Dict[str, QueryProfile]:
        """
        Run LLM query analysis for each agent query.

        If an LLM instance is provided, reuse it to avoid provider/base_url drift.
        """
        if llm is None:
            from OSSS.ai.llm.openai import OpenAIChatLLM
            from OSSS.ai.config.openai_config import OpenAIConfig

            cfg = OpenAIConfig.load()
            llm = OpenAIChatLLM(api_key=cfg.api_key, model=cfg.model, base_url=cfg.base_url)

        results: Dict[str, QueryProfile] = {}
        for agent, q in agent_queries.items():
            results[agent] = await self._llm_analyze_query_profile_best_effort(q, llm=llm)
        return results

    def _convert_agent_outputs_to_serializable(
        self,
        agent_outputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Convert agent outputs into JSON-serializable structures.

        Why this exists:
        - Historically agent outputs were strings.
        - Newer agents may return Pydantic models (structured outputs).
        - API responses must be serializable (dict/str/list/primitive),
          so we normalize any Pydantic objects via model_dump().

        Parameters
        ----------
        agent_outputs : Dict[str, Any]
            Raw agent outputs which may contain:
            - Pydantic models
            - plain strings
            - dicts/lists/primitive values

        Returns
        -------
        Dict[str, Any]
            Outputs with any Pydantic models converted to dicts.
        """
        serialized_outputs: Dict[str, Any] = {}

        for agent_name, output in agent_outputs.items():
            # Pydantic model detection: model_dump exists on Pydantic v2 models
            if hasattr(output, "model_dump"):
                serialized_outputs[agent_name] = output.model_dump()
            else:
                # Leave already-serializable outputs unchanged
                serialized_outputs[agent_name] = output

        return serialized_outputs

    # -----------------------------------------------------------------------
    # API identity metadata
    # -----------------------------------------------------------------------

    @property
    def api_name(self) -> str:
        """Human-friendly name for diagnostics / health endpoints."""
        return "LangGraph Orchestration API"

    @property
    def api_version(self) -> str:
        """Version string for API clients and telemetry correlation."""
        return "1.0.0"

    # -----------------------------------------------------------------------
    # Lifecycle management
    # -----------------------------------------------------------------------

    async def initialize(self) -> None:
        """
        Initialize the API and its underlying resources.

        Responsibilities:
        - Instantiate the orchestrator (LangGraphOrchestrator)
        - Mark API as initialized so ensure_initialized allows execution
        """
        if self._initialized:
            # Idempotent initialization: safe to call multiple times
            return

        logger.info("Initializing LangGraphOrchestrationAPI")

        # Create orchestrator instance (production pipeline runner)
        self._orchestrator = LangGraphOrchestrator()

        # Mark initialization complete
        self._initialized = True

        logger.info("LangGraphOrchestrationAPI initialized successfully")

    async def shutdown(self) -> None:
        """
        Clean shutdown of orchestrator and resources.

        Responsibilities:
        - Attempt to cancel active workflows (best-effort)
        - Cleanup orchestrator caches if supported
        - Reset initialized flag

        NOTE:
        The underlying orchestrator currently does not expose a formal shutdown(),
        so cleanup is limited to what we can do safely (e.g., cache clearing).
        """
        if not self._initialized:
            return

        logger.info("Shutting down LangGraphOrchestrationAPI")

        # Cancel any active workflows (best-effort)
        for workflow_id in list(self._active_workflows.keys()):
            await self.cancel_workflow(workflow_id)

        # Orchestrator cleanup hook (if implemented)
        if self._orchestrator:
            if hasattr(self._orchestrator, "clear_graph_cache"):
                self._orchestrator.clear_graph_cache()

        self._initialized = False
        logger.info("LangGraphOrchestrationAPI shutdown complete")

    # -----------------------------------------------------------------------
    # Health and metrics endpoints
    # -----------------------------------------------------------------------

    async def health_check(self) -> APIHealthStatus:
        """
        Comprehensive health check including orchestrator status.

        Health strategy:
        - If API isn't initialized -> UNHEALTHY
        - If orchestrator missing -> UNHEALTHY
        - If orchestrator stats indicate high failure rate -> DEGRADED
        - Otherwise -> HEALTHY

        Returns:
            APIHealthStatus with:
            - overall status
            - human-readable details
            - structured "checks" map for dashboards
        """
        checks = {
            "initialized": self._initialized,
            "orchestrator_available": self._orchestrator is not None,
            "active_workflows": len(self._active_workflows),
            "total_workflows_processed": self._total_workflows,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        status = HealthStatus.HEALTHY
        details = (
            f"LangGraph Orchestration API - {len(self._active_workflows)} active workflows"
        )

        # If orchestrator exists and API is initialized, we can perform deeper checks
        if self._orchestrator and self._initialized:
            try:
                # Orchestrator statistics provide a health signal (failures vs total)
                if hasattr(self._orchestrator, "get_execution_statistics"):
                    orchestrator_stats = self._orchestrator.get_execution_statistics()
                    checks["orchestrator_stats"] = orchestrator_stats

                    total_executions = orchestrator_stats.get("total_executions", 0)
                    failed_executions = orchestrator_stats.get("failed_executions", 0)

                    # Only compute failure rate when we have nonzero executions
                    if total_executions > 0:
                        failure_rate = failed_executions / total_executions
                        checks["failure_rate"] = failure_rate

                        # Arbitrary threshold: degrade health if more than 50% failing
                        if failure_rate > 0.5:
                            status = HealthStatus.DEGRADED
                            details += f" (High failure rate: {failure_rate:.1%})"

            except Exception as e:
                # Any exception in deeper checks degrades health but doesn't crash endpoint
                checks["orchestrator_error"] = str(e)
                status = HealthStatus.DEGRADED
                details += f" (Orchestrator check failed: {e})"

        else:
            # If not initialized or orchestrator missing, API is unhealthy
            if not self._initialized:
                status = HealthStatus.UNHEALTHY
                details = "API not initialized"
            else:
                status = HealthStatus.UNHEALTHY
                details = "Orchestrator not available"

        return APIHealthStatus(status=status, details=details, checks=checks)

    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get API performance and usage metrics.

        This endpoint provides:
        - API-level counters (active workflows, total processed)
        - Orchestrator statistics (if available)
        - Graph cache statistics (if available)
        """
        base_metrics = {
            "active_workflows": len(self._active_workflows),
            "total_workflows_processed": self._total_workflows,
            "api_initialized": self._initialized,
            "api_version": self.api_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # If orchestrator is present and initialized, enrich metrics
        if self._orchestrator and self._initialized:
            try:
                if hasattr(self._orchestrator, "get_execution_statistics"):
                    orchestrator_stats = self._orchestrator.get_execution_statistics()
                    base_metrics.update(
                        {f"orchestrator_{k}": v for k, v in orchestrator_stats.items()}
                    )

                if hasattr(self._orchestrator, "get_graph_cache_stats"):
                    cache_stats = self._orchestrator.get_graph_cache_stats()
                    base_metrics.update(
                        {f"cache_{k}": v for k, v in cache_stats.items()}
                    )

            except Exception as e:
                # Metrics failures should never break API
                base_metrics["metrics_error"] = str(e)

        return base_metrics

    # -----------------------------------------------------------------------
    # Workflow execution
    # -----------------------------------------------------------------------


    async def _run_selected_graph(self, query: str, config: Dict[str, Any]) -> Any:
        """
        Indirection layer: selected_graph -> actual runner.
        Keeps execute_workflow clean.
        """
        if self._orchestrator is None:
            raise RuntimeError("Orchestrator not initialized")

        # Local import to avoid heavy import cost at module import time
        from OSSS.ai.orchestration.advanced_adapter import AdvancedOrchestratorAdapter

        async def run_default(q: str, c: Dict[str, Any]) -> Any:
            return await self._orchestrator.run(q, c)

        async def run_diagnostics(q: str, c: Dict[str, Any]) -> Any:
            return await AdvancedOrchestratorAdapter(graph="diagnostics").run(q, c)

        async def run_builder(q: str, c: Dict[str, Any]) -> Any:
            return await AdvancedOrchestratorAdapter(graph="builder").run(q, c)

        async def run_data_read(q: str, c: Dict[str, Any]) -> Any:
            return await AdvancedOrchestratorAdapter(graph="data_read").run(q, c)

        async def run_explain_calm(q: str, c: Dict[str, Any]) -> Any:
            return await AdvancedOrchestratorAdapter(graph="explain_calm").run(q, c)

        async def run_clarify(q: str, c: Dict[str, Any]) -> Any:
            return await AdvancedOrchestratorAdapter(graph="clarify").run(q, c)

        GRAPH_RUNNERS: Dict[str, AsyncRunner] = {
            "graph_default": run_default,
            "graph_diagnostics": run_diagnostics,
            "graph_builder": run_builder,
            "graph_data_read": run_data_read,
            "graph_explain_deescalate": run_explain_calm,
            "graph_clarify": run_clarify,
        }

        graph_id = config.get("selected_graph", "graph_default")
        runner = GRAPH_RUNNERS.get(graph_id) or GRAPH_RUNNERS["graph_default"]
        return await runner(query, config)

    def _apply_tone_policy(self, config: Dict[str, Any], qp: Dict[str, Any]) -> None:
        TONE_POLICY = {
            "angry": {"style": "calm", "verbosity": "concise"},
            "anxious": {"style": "reassuring", "verbosity": "medium"},
            "neutral": {"style": "neutral", "verbosity": "medium"},
        }

        tone = (qp.get("tone") or "neutral").strip().lower()
        config["response_policy"] = TONE_POLICY.get(tone, TONE_POLICY["neutral"])

    def _apply_confidence_gates(self, config: Dict[str, Any]) -> None:
        decision = config.get("routing_decision") or {}
        intent_conf = float(decision.get("intent_conf") or decision.get("intent_confidence") or 0.0)

        min_conf = float(config.get("min_intent_confidence", 0.70))

        # If confidence is low, override routing to a clarify graph
        if intent_conf < min_conf:
            config["routing_gates"] = {
                "intent_confidence_below_threshold": True,
                "min_intent_confidence": min_conf,
                "intent_conf": intent_conf,
            }
            config["selected_graph"] = "graph_clarify"
            config["routing_source"] = "gate:intent_confidence"

    def _cleanup_query_profile_state(self, workflow_id: str) -> None:
        self._query_profile_cache.pop(workflow_id, None)
        self._query_profile_locks.pop(workflow_id, None)

    def _agents_requested_for_persistence(self, request: WorkflowRequest) -> list[str]:
        # None means "use default orchestrator agents"
        if request.agents is None:
            return ["refiner", "critic", "historian", "synthesis"]

        # [] means "direct LLM bypass"
        if isinstance(request.agents, list) and len(request.agents) == 0:
            return []  # or ["llm"] if you prefer

        # explicit list
        return list(request.agents)

    def _get_or_default_query_profile(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Return a non-empty query_profile dict from config, with a safe default shape.
        NEVER calls the LLM (analysis is done earlier).
        """
        qp = config.get("query_profile")
        if isinstance(qp, dict) and qp:
            return qp

        return {
            "intent": "general",
            "intent_confidence": 0.50,
            "sub_intent": "general",
            "sub_intent_confidence": 0.50,
            "tone": "neutral",
            "tone_confidence": 0.50,
            "signals": {"analysis_source": "rules_fallback", "fallback": True},
            "matched_rules": [{"rule": "intent:general:fallback", "action": "read"}],
        }

    @ensure_initialized
    async def execute_workflow(self, request: WorkflowRequest) -> WorkflowResponse:
        """
        Execute a workflow using the production orchestrator.

        High-level steps:
        1. Create workflow_id + start timer
        2. Emit workflow_started event
        3. Track workflow in memory
        4. Build orchestrator config (correlation_id, workflow_id, agents)
        5. Run orchestrator to obtain result context
        6. Prefer structured outputs from execution_state if present
        7. Build WorkflowResponse (and optional markdown export)
        8. Persist workflow metadata to database (best-effort)
        9. Emit workflow_completed event (success or failure)
        """

        # ------------------------------------------------------------
        # ALWAYS establish workflow identity + config, then ANALYZE ONCE
        # ------------------------------------------------------------
        workflow_id = str(uuid.uuid4())
        start_time = time.time()
        original_execution_config = request.execution_config or {}
        config: Dict[str, Any] = dict(original_execution_config)  # or {} then merge


        # Ensure canonical flag exists
        config["use_llm_intent"] = bool(original_execution_config.get("use_llm_intent", False))

        # Preserve correlation_id for tracing
        correlation_id = request.correlation_id or f"req-{uuid.uuid4()}"
        config["correlation_id"] = correlation_id
        config["workflow_id"] = workflow_id

        response: Optional[WorkflowResponse] = None

        # ✅ ANALYSIS MUST ALWAYS RUN (exactly once per workflow_id)
        llm: Optional[Any] = None
        query_profile: Optional[QueryProfile] = None
        qp: Dict[str, Any] = {}

        try:
            qp = await self._ensure_query_profile(
                workflow_id=workflow_id,
                query=request.query,
                use_llm_intent=bool(config.get("use_llm_intent", False)),
                llm=llm,
                config=config,
            )

            # attach response policy BEFORE any graph runs
            self._apply_tone_policy(config, qp)

            query_profile = QueryProfile.model_validate(qp)

            decision = build_routing_decision(query_profile)
            config["routing_decision"] = decision.model_dump()


            # gate may override selected_graph
            self._apply_confidence_gates(config)

            # only resolve via registry if gate didn't choose a graph
            # Gate may have already chosen a graph. If so, do NOT override it.
            # If a gate forced a graph, it should have set routing_source already.
            if config.get("selected_graph"):
                config.setdefault("routing_source", config.get("routing_source", "caller_or_gate"))
            else:
                routing_decision = config.get("routing_decision") or {}
                graph_id = GRAPH_REGISTRY.resolve(routing_decision)

                logger.info("Routing decision input", extra={"decision": routing_decision})
                logger.info("Routing decision output", extra={"selected_graph": graph_id})


                config["selected_graph"] = graph_id
                config["routing_source"] = "registry"


        except Exception as analysis_error:
            logger.warning(
                "Global preflight analysis failed; using safe fallback",
                extra = {"workflow_id": workflow_id, "error": str(analysis_error)},
            )
            qp = {
                "intent": "general",
                "intent_confidence": 0.50,
                "sub_intent": "general",
                "sub_intent_confidence": 0.50,
                "tone": "neutral",
                "tone_confidence": 0.50,
                "signals": {"analysis_source": "rules_fallback"},
                "matched_rules": [{"rule": "intent:general:fallback", "action": "read"}],
            }
            config["query_profile"] = qp

            # Always produce a decision dict (never None)
            try:
                query_profile = QueryProfile.model_validate(qp)
                decision = build_routing_decision(query_profile).model_dump()
            except Exception:
                decision = {"action": "read", "intent": "general", "tone": "neutral", "sub_intent": "general"}

            config["routing_decision"] = decision

            # Apply gates (optional)
            self._apply_confidence_gates(config)

            # Choose graph if not set by gate
            if not config.get("selected_graph"):
                config["selected_graph"] = GRAPH_REGISTRY.resolve(decision)
                config["routing_source"] = "registry:fallback"
            else:
                config.setdefault("routing_source", "gate:fallback")

            # ✅ Fix B: always coerce fallback matched_rules before validating QueryProfile
            try:
                hits = coerce_rule_hits(qp.get("matched_rules"))
                qp["matched_rules"] = [h.model_dump() for h in hits]
            except Exception:
                qp["matched_rules"] = []

            try:
                query_profile = QueryProfile.model_validate(qp)
            except Exception:
                query_profile = None


        logger.info(
            "Routing selected",
            extra={
                "workflow_id": workflow_id,
                "selected_graph": config.get("selected_graph"),
                "routing_source": config.get("routing_source"),
                "routing_gates": config.get("routing_gates"),
            },
        )

        # ✅ DIRECT LLM BYPASS (agents explicitly empty or None)
        bypass_llm = isinstance(request.agents, list) and len(request.agents) == 0
        if bypass_llm:

            # Always make agents a list for telemetry / pydantic models
            safe_agents: list[str] = []

            # qp already exists; keep local alias for readability
            qp = config.get("query_profile") or qp

            # --- telemetry: started (never None agents) ---
            try:
                _fire_and_forget(emit_workflow_started(
                    workflow_id=workflow_id,
                    query=request.query,
                    agents=safe_agents,  # ✅ never None
                    execution_config=request.execution_config or {},
                    correlation_id=correlation_id,
                    metadata={
                        "api_version": self.api_version,
                        "start_time": start_time,
                        "routing_source": "direct_llm_bypass",
                        "query_profile": qp,  # optional: makes “analysis ran” provable in telemetry

                    },

                ))
            except Exception:
                # telemetry must never break responses
                pass

            # --- call LLM ---
            from OSSS.ai.config.openai_config import OpenAIConfig
            from OSSS.ai.llm.openai import OpenAIChatLLM

            llm_config = OpenAIConfig.load()
            llm2 = OpenAIChatLLM(
                api_key=llm_config.api_key,
                model=llm_config.model,
                base_url=llm_config.base_url,
            )

            system_prompt = (
                "You are OSSS. Answer the user's request directly and concretely.\n"
                "If the user asks for a list, return a list.\n"
                "Do not rewrite the request into meta-analysis."
            )

            resp = await llm2.ainvoke(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": request.query},
                ],
            )

            llm_answer = _coerce_llm_text(resp).strip()

            elapsed = time.time() - start_time

            agent_output_meta: Dict[str, Any] = {
                "_query_profile": qp,  # already computed in preflight
                "_routing": {
                    "source": "direct_llm_bypass",
                    "graph": "llm",
                    "final_agents": [],  # explicit: no orchestrator agents ran
                },
                "llm": {
                    "agent": "llm",
                    "action": "read",
                    "intent": qp.get("intent", "general"),
                    "intent_confidence": qp.get("intent_confidence", 0.5),
                    "sub_intent": qp.get("sub_intent", "general"),
                    "sub_intent_confidence": qp.get("sub_intent_confidence", 0.5),
                    "tone": qp.get("tone", "neutral"),
                    "tone_confidence": qp.get("tone_confidence", 0.5),
                    "signals": qp.get("signals", {}),
                    "matched_rules": qp.get("matched_rules", []),
                    "analysis_source": (qp.get("signals") or {}).get("analysis_source", "rules"),
                },
            }


            response = WorkflowResponse(
                workflow_id=workflow_id,
                status="completed",
                agent_output_meta=agent_output_meta,
                agent_outputs={"llm": llm_answer},
                execution_time_seconds=elapsed,
                correlation_id=correlation_id,
                error_message=None,
                markdown_export=None,
            )

            # --- telemetry: completed ---
            try:
                await emit_workflow_completed(
                    workflow_id=workflow_id,
                    status="completed",
                    execution_time_seconds=elapsed,
                    agent_outputs={"llm": llm_answer},
                    correlation_id=correlation_id,
                    metadata={
                        "api_version": self.api_version,
                        "agent_output_meta": agent_output_meta,
                    },
                )
            except Exception:
                pass

            self._cleanup_query_profile_state(workflow_id)

            try:
                await self._persist_workflow_to_database(
                    request,
                    response,
                    execution_context=None,
                    workflow_id=workflow_id,
                    original_execution_config=original_execution_config,
                )
            except Exception as persist_error:
                logger.error(f"Failed to persist bypass workflow {workflow_id}: {persist_error}")

            return response

        try:
            logger.info(
                f"Starting workflow {workflow_id} with query: {request.query[:100]}..."
            )

            # Emit workflow started event for telemetry systems
            safe_agents = list(request.agents or [])
            _fire_and_forget(
                emit_workflow_started(
                    workflow_id=workflow_id,
                    query=request.query,
                    agents=safe_agents,  # ✅ never None
                    execution_config=request.execution_config or {},
                    correlation_id=correlation_id,
                    metadata={
                        "api_version": self.api_version,
                        "start_time": start_time,
                        "query_profile": qp,
                    },
                )
            )

            # Track workflow execution in memory (used by get_status(), debugging)
            self._active_workflows[workflow_id] = {
                "status": "running",
                "request": request,
                "start_time": start_time,
                "workflow_id": workflow_id,
                "query_profile": config.get("query_profile"),  # keep it here
            }
            self._total_workflows += 1

            # Build orchestrator execution config from request data
            # IMPORTANT: copy dict to avoid mutating request.execution_config
            # config already built above; just add agents restriction if requested

            # Optionally restrict which agents run in this workflow
            if request.agents:
                config["agents"] = request.agents

            use_llm_intent = bool(config.get("use_llm_intent", False))

            execution_config = request.execution_config or {}

            logger.info(
                "Execution config received",
                extra={
                    "workflow_id": workflow_id,  # if you already created it
                    "use_llm_intent": execution_config.get("use_llm_intent"),
                    "raw_execution_config": execution_config,
                },
            )

            # Run the orchestrator and obtain an execution context (AgentContext-like)
            if self._orchestrator is None:
                raise RuntimeError("Orchestrator not initialized")

            # ✅ IMPORTANT: remove/reduce duplicated “preflight analysis” block below.
            # qp/query_profile already exist and are in config["query_profile"].

            result_context = await self._run_selected_graph(request.query, config)



            # Compute end-to-end duration
            execution_time = time.time() - start_time

            # ------------------------------------------------------------
            # ALWAYS initialize final status variables (prevents UnboundLocalError)
            # ------------------------------------------------------------
            final_status: str = "completed"
            final_error_message: Optional[str] = None

            # ----------------------------------------------------------------
            # Normalize execution_state access (may not exist on some contexts)
            # ----------------------------------------------------------------
            exec_state: Dict[str, Any] = {}
            try:
                maybe_state = getattr(result_context, "execution_state", None)
                if isinstance(maybe_state, dict):
                    exec_state = maybe_state
            except Exception:
                exec_state = {}

            # ----------------------------------------------------------------
            # Output extraction: structured outputs are preferred
            # ----------------------------------------------------------------
            structured_outputs: Dict[str, Any] = {}
            try:
                so = exec_state.get("structured_outputs", {})
                if isinstance(so, dict):
                    structured_outputs = so
            except Exception:
                structured_outputs = {}

            # Determine executed agents (prefer actual agent_outputs keys)
            executed_agents: List[str] = []
            try:
                ao = getattr(result_context, "agent_outputs", {}) or {}
                if isinstance(ao, dict):
                    executed_agents = list(ao.keys())
            except Exception:
                executed_agents = []

            # Fallback: if agent_outputs is missing, use structured outputs keys
            if not executed_agents and structured_outputs:
                executed_agents = list(structured_outputs.keys())

            # Merge strategy:
            # - If structured output exists for agent -> use it
            # - Else fall back to legacy output in result_context.agent_outputs
            agent_outputs_to_serialize: Dict[str, Any] = {}
            raw_agent_outputs: Dict[str, Any] = {}
            try:
                raw_agent_outputs = getattr(result_context, "agent_outputs", {}) or {}
                if not isinstance(raw_agent_outputs, dict):
                    raw_agent_outputs = {}
            except Exception:
                raw_agent_outputs = {}

            for agent_name in executed_agents:
                if agent_name in structured_outputs:
                    agent_outputs_to_serialize[agent_name] = structured_outputs[agent_name]
                else:
                    agent_outputs_to_serialize[agent_name] = raw_agent_outputs.get(agent_name, "")

            # Convert any remaining Pydantic objects to plain dicts
            serialized_agent_outputs = self._convert_agent_outputs_to_serializable(
                agent_outputs_to_serialize
            )

            # ----------------------------------------------------------------
            # Output meta extraction (intent/tone/etc.) + ensure `action`
            # ----------------------------------------------------------------
            agent_output_meta: Dict[str, Any] = {}

            # 1) Preferred: per-agent envelopes from execution_state if present
            try:
                aom = exec_state.get("agent_output_meta", {})
                if isinstance(aom, dict):
                    agent_output_meta = aom
            except Exception:
                agent_output_meta = {}

            # ----------------------------------------------------------------
            # Ensure we ALWAYS have a query_profile dict (never None / never empty)
            # ----------------------------------------------------------------

            # ----------------------------------------------------------------
            # Canonical query profile dict (analysis already ran once above)
            # ----------------------------------------------------------------
            qp = self._get_or_default_query_profile(config)

            # Safety only: never call LLM here (preflight already did that)
            if not isinstance(qp, dict) or not qp:
                qp = self._get_or_default_query_profile(config)
                config["query_profile"] = qp

            logger.info(
                "Query profile (single-pass) finalized",
                extra={
                    "workflow_id": workflow_id,
                    "intent": qp.get("intent"),
                    "sub_intent": qp.get("sub_intent"),
                    "tone": qp.get("tone"),
                    "analysis_source": (qp.get("signals") or {}).get("analysis_source"),
                    "use_llm_intent": bool(config.get("use_llm_intent", False)),
                },
            )

            # ✅ CRITICAL: persist finalized qp so later "ensure" calls cannot re-run LLM
            config["query_profile"] = qp

            # Keep a copy at a stable location for debugging/clients
            use_llm_intent = bool(config.get("use_llm_intent", False))

            agent_output_meta["_query_profile"] = qp
            agent_output_meta["_query_profile"].setdefault("signals", {})
            agent_output_meta["_query_profile"]["signals"].setdefault(
                "analysis_source",
                "llm" if use_llm_intent else "rules",
            )

            # preserve more specific source if it exists (e.g., rules_fallback)
            agent_output_meta["_query_profile"]["signals"].setdefault(
                "analysis_source",
                "llm" if use_llm_intent else "rules",
            )

            agent_output_meta["_routing"] = {
                "source": config.get("routing_source", "unknown"),
                "decision": config.get("routing_decision"),  # ✅ add this line
                "gates": config.get("routing_gates", {}),
                "graph": config.get("selected_graph"),
                "selected_workflow_id": config.get("selected_workflow_id"),
                "final_agents": config.get("agents"),
            }

            # ----------------------------------------------------------------
            # Robust extraction helpers (handles alternate shapes)
            # ----------------------------------------------------------------
            def _pick(d: dict, *keys: str):
                for k in keys:
                    if k in d and d[k] is not None:
                        return d[k]
                return None

            def _unwrap_name(v: Any):
                # supports {"name": "..."} or {"value": "..."} shapes
                if isinstance(v, dict):
                    return v.get("name") or v.get("value") or v.get("label")
                return v

            # Canonical values (with safe defaults)
            qp_intent = _unwrap_name(_pick(qp, "intent", "intent_name")) or "general"
            qp_sub_intent = _unwrap_name(_pick(qp, "sub_intent", "sub_intent_name")) or "general"
            qp_tone = _unwrap_name(_pick(qp, "tone", "tone_name")) or "neutral"

            qp_intent_conf = _pick(qp, "intent_confidence") or 0.50
            qp_sub_intent_conf = _pick(qp, "sub_intent_confidence") or 0.50
            qp_tone_conf = _pick(qp, "tone_confidence") or 0.50

            qp_signals = _pick(qp, "signals") or {}
            qp_matched = _pick(qp, "matched_rules", "matched_patterns") or []

            # ✅ Best-practice: matched_rules is already structured (RuleHit dicts).
            # Only do a minimal compatibility shim if an older pipeline still returns List[str].
            normalized_matched: List[Dict[str, Any]] = []

            if isinstance(qp_matched, list):
                # Legacy: List[str] -> RuleHit contract
                if qp_matched and isinstance(qp_matched[0], str):
                    normalized_matched = [
                        {
                            "rule": r,
                            "action": "read",
                            "category": "analysis",
                            "score": 0.50,
                        }
                        for r in qp_matched
                        if isinstance(r, str) and r.strip()
                    ]

                # Preferred: already List[dict] -> normalize keys to RuleHit contract
                elif qp_matched and isinstance(qp_matched[0], dict):
                    for item in qp_matched:
                        if not isinstance(item, dict):
                            continue

                        rule = (
                                item.get("rule")
                                or item.get("rule_id")
                                or item.get("id")
                                or item.get("name")
                                or item.get("label")
                        )
                        if not isinstance(rule, str) or not rule.strip():
                            continue

                        hit: Dict[str, Any] = {
                            "rule": rule.strip(),
                            "action": (item.get("action") if isinstance(item.get("action"), str) else "read"),
                        }

                        if isinstance(item.get("category"), str):
                            hit["category"] = item["category"]

                        if isinstance(item.get("score"), (int, float)):
                            hit["score"] = float(item["score"])
                        elif isinstance(item.get("confidence"), (int, float)):
                            hit["score"] = float(item["confidence"])

                        meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
                        for k in ("label", "tone", "sub_intent", "parent_intent"):
                            if k in item and k not in meta:
                                meta[k] = item[k]
                        if meta:
                            hit["meta"] = meta

                        normalized_matched.append(hit)

            qp_matched = normalized_matched

            # ----------------------------------------------------------------
            # Optional: Per-agent LLM analysis (intent/tone/sub-intent)
            # Option A: decouple from use_llm_intent. Per-agent analysis is opt-in only.
            # ----------------------------------------------------------------
            enable_llm_agent_analysis = False
            try:
                enable_llm_agent_analysis = bool(config.get("enable_llm_query_analysis", False))

                logger.info(
                    "Per-agent LLM query analysis toggle evaluated",
                    extra={
                        "workflow_id": workflow_id,
                        "enable_llm_query_analysis": bool(config.get("enable_llm_query_analysis", False)),
                        "use_llm_intent": bool(config.get("use_llm_intent", False)),
                        "enable_llm_agent_analysis": enable_llm_agent_analysis,
                    },
                )
            except Exception:
                enable_llm_agent_analysis = False

            agent_profiles: Dict[str, Any] = {}  # agent -> QueryProfile (or dict)

            if enable_llm_agent_analysis:
                try:
                    # If your orchestrator/agents populate exec_state["effective_queries"],
                    # we will prefer that; otherwise we fall back to request.query.
                    agent_queries = self._extract_effective_queries(
                        base_query=request.query,
                        executed_agents=list(serialized_agent_outputs.keys()),
                        exec_state=exec_state,
                    )

                    agent_profiles = await self._llm_analyze_agent_queries(agent_queries, llm=llm)

                    # Helpful for debugging
                    agent_output_meta.setdefault("_agent_effective_queries", agent_queries)

                except Exception as e:
                    logger.warning(
                        f"Per-agent LLM query analysis failed; using base query_profile. error={e}"
                    )
                    agent_profiles = {}

            # ----------------------------------------------------------------
            # Fan-out profile into EVERY agent envelope
            # - prefer per-agent LLM profile when available
            # - otherwise fall back to base deterministic profile (qp_*)
            # ----------------------------------------------------------------
            # Fan-out profile into EVERY agent envelope
            for agent_name in serialized_agent_outputs.keys():
                envelope = agent_output_meta.get(agent_name)
                if not isinstance(envelope, dict):
                    envelope = {}
                    agent_output_meta[agent_name] = envelope

                envelope.setdefault("agent", agent_name)
                envelope.setdefault("action", "read")

                prof = agent_profiles.get(agent_name)

                if prof is not None:
                    if hasattr(prof, "model_dump"):
                        prof_dict = prof.model_dump()
                    elif isinstance(prof, dict):
                        prof_dict = prof
                    else:
                        prof_dict = {}

                    envelope["intent"] = prof_dict.get("intent") or "general"
                    envelope["sub_intent"] = prof_dict.get("sub_intent") or "general"
                    envelope["tone"] = prof_dict.get("tone") or "neutral"

                    envelope["intent_confidence"] = float(prof_dict.get("intent_confidence") or 0.50)
                    envelope["sub_intent_confidence"] = float(prof_dict.get("sub_intent_confidence") or 0.50)
                    envelope["tone_confidence"] = float(prof_dict.get("tone_confidence") or 0.50)

                    envelope["signals"] = prof_dict.get("signals") or {}
                    envelope["matched_rules"] = _normalize_rule_hits(prof_dict.get("matched_rules"))
                    envelope["analysis_source"] = "llm"
                else:
                    # Existing behavior (base query_profile)
                    envelope.setdefault("intent", qp_intent)
                    envelope.setdefault("sub_intent", qp_sub_intent)
                    envelope.setdefault("tone", qp_tone)

                    envelope.setdefault("intent_confidence", float(qp_intent_conf))
                    envelope.setdefault("sub_intent_confidence", float(qp_sub_intent_conf))
                    envelope.setdefault("tone_confidence", float(qp_tone_conf))

                    envelope.setdefault("signals", qp_signals)
                    envelope.setdefault("matched_rules", qp_matched)
                    envelope["analysis_source"] = (qp_signals.get("analysis_source") or "rules")

            # ------------------------------------------------------------
            # Option A: decide final status ONCE, after outputs are built
            # ------------------------------------------------------------
            if not isinstance(serialized_agent_outputs, dict) or len(serialized_agent_outputs) == 0:
                final_status = "failed"
                final_error_message = "No agent outputs produced."

                # ✅ _errors must be a dict (per pydantic), but we can keep a list inside it
                err_bucket = agent_output_meta.setdefault("_errors", {})
                items = err_bucket.setdefault("items", [])
                if isinstance(items, list):
                    items.append(
                        {
                            "type": "empty_agent_outputs",
                            "message": final_error_message,
                            "agents_requested": list(config.get("agents") or []),
                            "selected_graph": config.get("selected_graph"),
                        }
                    )
                else:
                    # ultra-defensive fallback
                    err_bucket["items"] = [
                        {
                            "type": "empty_agent_outputs",
                            "message": final_error_message,
                            "agents_requested": list(config.get("agents") or []),
                            "selected_graph": config.get("selected_graph"),
                        }
                    ]
            else:
                final_status = "completed"
                final_error_message = None

            # ✅ Build response HERE (always before export_md)
            response = WorkflowResponse(
                workflow_id=workflow_id,
                status=final_status,
                agent_outputs=(serialized_agent_outputs if final_status == "completed" else {}),
                execution_time_seconds=execution_time,
                correlation_id=correlation_id,
                agent_output_meta=agent_output_meta,
                error_message=final_error_message,
                markdown_export=None,
            )

            # ----------------------------------------------------------------
            # Optional markdown export
            # ----------------------------------------------------------------
            # If request.export_md is True, we:
            # - Export agent outputs to markdown file
            # - Attempt topic analysis to tag the document
            # - Attach metadata into response.markdown_export
            # - Attempt to persist the markdown to DB (best-effort)
            if request.export_md:
                # ✅ If workflow failed (including empty outputs), don't export markdown
                if response.status != "completed":
                    response.markdown_export = {
                        "error": "Export skipped",
                        "message": "Workflow did not complete successfully; no outputs to export.",
                        "export_timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                else:
                    try:
                        from OSSS.ai.store.wiki_adapter import MarkdownExporter
                        from OSSS.ai.store.topic_manager import TopicManager
                        from OSSS.ai.llm.openai import OpenAIChatLLM
                        from OSSS.ai.config.openai_config import OpenAIConfig

                        logger.info(f"Exporting markdown for workflow {workflow_id}")

                        # Create LLM instance used by TopicManager for analysis
                        llm_config = OpenAIConfig.load()
                        llm = OpenAIChatLLM(
                            api_key=llm_config.api_key,
                            model=llm_config.model,
                            base_url=llm_config.base_url,
                        )

                        topic_manager = TopicManager(llm=llm)

                        # Topic analysis is best-effort (do not fail export if analysis fails)
                        try:
                            topic_analysis = await topic_manager.analyze_and_suggest_topics(
                                query=request.query,
                                agent_outputs=serialized_agent_outputs,
                            )
                            suggested_topics = [s.topic for s in topic_analysis.suggested_topics]
                            suggested_domain = topic_analysis.suggested_domain
                            logger.info(
                                f"Topic analysis completed: {len(suggested_topics)} topics, domain: {suggested_domain}"
                            )
                        except Exception as topic_error:
                            logger.warning(f"Topic analysis failed: {topic_error}")
                            suggested_topics = []
                            suggested_domain = None

                        # Export markdown using enhanced metadata
                        exporter = MarkdownExporter()
                        md_path = exporter.export(
                            agent_outputs=serialized_agent_outputs,
                            question=request.query,
                            topics=suggested_topics,
                            domain=suggested_domain,
                        )

                        md_path_obj = Path(md_path)

                        # Attach export metadata to API response
                        response.markdown_export = {
                            "file_path": str(md_path_obj.absolute()),
                            "filename": md_path_obj.name,
                            "export_timestamp": datetime.now(timezone.utc).isoformat(),
                            "suggested_topics": (suggested_topics[:5] if suggested_topics else []),
                            "suggested_domain": suggested_domain,
                        }

                        logger.info(f"Markdown export successful: {md_path_obj.name}")

                        # Persist exported markdown to DB (best-effort; never fail workflow)
                        try:
                            db_session_factory = await self._get_or_create_db_session_factory()

                            if db_session_factory:
                                async with db_session_factory.get_repository_factory() as repo_factory:
                                    doc_repo = repo_factory.historian_documents

                                    with open(md_path_obj, "r", encoding="utf-8") as md_file:
                                        markdown_content = md_file.read()

                                    topics_list = suggested_topics[:5] if suggested_topics else []

                                    await doc_repo.get_or_create_document(
                                        title=request.query[:200],
                                        content=markdown_content,
                                        source_path=str(md_path_obj.absolute()),
                                        document_metadata={
                                            "workflow_id": workflow_id,
                                            "correlation_id": request.correlation_id,
                                            "topics": topics_list,
                                            "domain": suggested_domain,
                                            "export_timestamp": datetime.now(timezone.utc).isoformat(),
                                            "agents_executed": list(result_context.agent_outputs.keys()),
                                        },
                                    )

                                    logger.info(
                                        f"Workflow {workflow_id} markdown persisted to database: {md_path_obj.name}"
                                    )
                            else:
                                logger.warning(
                                    f"Database not available, skipping markdown persistence for workflow {workflow_id}"
                                )

                        except Exception as db_persist_error:
                            logger.error(
                                f"Failed to persist markdown to database for workflow {workflow_id}: {db_persist_error}"
                            )

                    except Exception as md_error:
                        error_msg = str(md_error)
                        logger.warning(
                            f"Markdown export failed for workflow {workflow_id}: {error_msg}"
                        )
                        response.markdown_export = {
                            "error": "Export failed",
                            "message": error_msg,
                            "export_timestamp": datetime.now(timezone.utc).isoformat(),
                        }

            # ----------------------------------------------------------------
            # Persist workflow results to database (best-effort)
            # ----------------------------------------------------------------
            try:
                await self._persist_workflow_to_database(
                    request,
                    response,
                    result_context,
                    workflow_id,
                    original_execution_config,
                )
            except Exception as persist_error:
                # Database persistence failures should never break API success response
                logger.error(f"Failed to persist workflow {workflow_id}: {persist_error}")

            # Update in-memory workflow tracking
            self._active_workflows[workflow_id].update(
                {"status": final_status, "response": response, "end_time": time.time()}
            )

            try:
                # Emit completion event for telemetry
                await emit_workflow_completed(
                    workflow_id=workflow_id,
                    status=final_status,
                    execution_time_seconds=execution_time,
                    agent_outputs=(result_context.agent_outputs if final_status == "completed" else {}),
                    error_message=(final_error_message if final_status != "completed" else None),
                    correlation_id=correlation_id,
                    metadata={
                        "api_version": self.api_version,
                        "end_time": time.time(),
                        "agent_output_meta": agent_output_meta,
                    },
                )
            except Exception:
                pass

            if final_status == "completed":
                logger.info(f"Workflow {workflow_id} completed successfully in {execution_time:.2f}s")
            else:
                logger.warning(
                    f"Workflow {workflow_id} completed with empty outputs; reporting failed in {execution_time:.2f}s"
                )

            self._cleanup_query_profile_state(workflow_id)


            return response

        except Exception as e:
            # Any exception in execution path becomes a failed workflow response
            execution_time = time.time() - start_time
            logger.error(
                f"Workflow {workflow_id} failed after {execution_time:.2f}s: {e}"
            )


            error_response = WorkflowResponse(
                workflow_id=workflow_id,
                status="failed",
                agent_outputs={},
                execution_time_seconds=execution_time,
                correlation_id=correlation_id,
                error_message=str(e),
            )

            # Persist failure metadata (best-effort)
            await self._persist_failed_workflow_to_database(
                request, error_response, workflow_id, str(e), original_execution_config
            )

            # Update workflow tracking if present
            if workflow_id in self._active_workflows:
                self._active_workflows[workflow_id].update(
                    {
                        "status": "failed",
                        "response": error_response,
                        "error": str(e),
                        "end_time": time.time(),
                    }
                )

            # Emit workflow completion event with failed status
            _fire_and_forget(emit_workflow_completed(
                workflow_id=workflow_id,
                status="failed",
                execution_time_seconds=execution_time,
                error_message=str(e),
                error_type=type(e).__name__,
                correlation_id=correlation_id,
                metadata={"api_version": self.api_version, "end_time": time.time()},
            ))

            self._cleanup_query_profile_state(workflow_id)

            return error_response

    # -----------------------------------------------------------------------
    # Status and cancellation endpoints
    # -----------------------------------------------------------------------

    @ensure_initialized
    async def get_status(self, workflow_id: str) -> StatusResponse:
        """
        Get workflow execution status.

        This implementation uses the in-memory _active_workflows store.
        It provides approximate progress for running workflows using
        a simplistic elapsed-time heuristic.

        Raises:
            KeyError if workflow_id is unknown
        """
        if workflow_id not in self._active_workflows:
            raise KeyError(f"Workflow {workflow_id} not found")

        workflow = self._active_workflows[workflow_id]
        status = workflow["status"]

        # Default status values
        progress = 0.0
        current_agent = None
        estimated_completion = None

        if status in ("completed", "failed", "cancelled"):
            progress = 100.0
            current_agent = None
            estimated_completion = None


        elif status == "running":
            # Crude progress estimate based on elapsed runtime
            elapsed = time.time() - workflow["start_time"]

            # Heuristic: assume typical workflow ≈ 10s; cap at 90% until completion
            progress = min(90.0, (elapsed / 10.0) * 100.0)

            # We do not currently track per-agent execution state here
            # so we provide a conservative default
            current_agent = "synthesis"
            estimated_completion = max(1.0, 10.0 - elapsed)

        return StatusResponse(
            workflow_id=workflow_id,
            status=status,
            progress_percentage=progress,
            current_agent=current_agent,
            estimated_completion_seconds=estimated_completion,
        )

    @ensure_initialized
    async def cancel_workflow(self, workflow_id: str) -> bool:
        """
        Cancel a running workflow.

        IMPORTANT LIMITATION:
        The underlying orchestrator does not currently support mid-flight cancellation.
        This method is therefore "soft-cancel":
        - mark status cancelled
        - remove from in-memory tracking shortly after
        """
        if workflow_id not in self._active_workflows:
            return False

        workflow = self._active_workflows[workflow_id]

        # Cannot cancel completed/failed workflows
        if workflow["status"] in ["completed", "failed"]:
            return False

        # Mark cancelled
        workflow["status"] = "cancelled"
        workflow["end_time"] = time.time()

        logger.info(f"Workflow {workflow_id} marked as cancelled")

        # Small delay before cleanup to let callers observe the cancelled status
        await asyncio.sleep(1)

        # Remove from active store to avoid memory growth
        if workflow_id in self._active_workflows:
            del self._active_workflows[workflow_id]
            self._cleanup_query_profile_state(workflow_id)

        return True

    # -----------------------------------------------------------------------
    # Database session factory for markdown persistence
    # -----------------------------------------------------------------------

    async def _get_or_create_db_session_factory(
        self,
    ) -> Optional[DatabaseSessionFactory]:
        """
        Lazily initialize DatabaseSessionFactory for document persistence.

        This factory is separate from the normal session factory used for
        questions because it provides a repository_factory abstraction
        needed by historian document persistence.

        Returns:
            DatabaseSessionFactory if available, else None.
        """
        if self._db_session_factory is None:
            try:
                self._db_session_factory = DatabaseSessionFactory()
                await self._db_session_factory.initialize()
                logger.info(
                    "Database session factory initialized for markdown persistence"
                )
            except Exception as e:
                # Persistence is optional; failure here should not break workflows
                logger.warning(f"Failed to initialize database session factory: {e}")
                self._db_session_factory = None

        return self._db_session_factory

    # -----------------------------------------------------------------------
    # Database persistence helpers (best-effort)
    # -----------------------------------------------------------------------

    async def _persist_workflow_to_database(
        self,
        request: WorkflowRequest,
        response: WorkflowResponse,
        execution_context: Any,
        workflow_id: str,
        original_execution_config: Dict[str, Any],
    ) -> None:
        """
        Persist a completed workflow to the database.

        Persistence strategy:
        - Store the original query and correlation_id
        - Store which nodes were executed
        - Store execution metadata (timing, outputs, flags)
        - If persistence fails, log and continue (do not fail API response)
        """
        try:
            async with self._session_factory() as session:
                question_repo = QuestionRepository(session)

                execution_metadata = {
                    "workflow_id": workflow_id,
                    "execution_time_seconds": response.execution_time_seconds,
                    "agent_outputs": response.agent_outputs,
                    "agents_requested": self._agents_requested_for_persistence(request),
                    "export_md": (request.export_md if request.export_md is not None else False),
                    "execution_config": original_execution_config,
                    "api_version": self.api_version,
                    "orchestrator_type": "langgraph-real",
                }

                nodes_executed = list(response.agent_outputs.keys()) if response.agent_outputs else []

                await question_repo.create_question(
                    query=request.query,
                    correlation_id=request.correlation_id,
                    execution_id=workflow_id,
                    nodes_executed=nodes_executed,
                    execution_metadata=execution_metadata,
                )

                logger.info(f"Workflow {workflow_id} persisted to database")

        except Exception as e:
            logger.error(f"Failed to persist workflow {workflow_id}: {e}")

    async def _persist_failed_workflow_to_database(
        self,
        request: WorkflowRequest,
        response: WorkflowResponse,
        workflow_id: str,
        error_message: str,
        original_execution_config: Dict[str, Any],
    ) -> None:
        """
        Persist a failed workflow to the database.

        This mirrors _persist_workflow_to_database but includes:
        - status = failed
        - error_message
        """
        try:
            async with self._session_factory() as session:
                question_repo = QuestionRepository(session)

                execution_metadata = {
                    "workflow_id": workflow_id,
                    "execution_time_seconds": response.execution_time_seconds,
                    "agent_outputs": response.agent_outputs,
                    "agents_requested": self._agents_requested_for_persistence(request),
                    "export_md": (request.export_md if request.export_md is not None else False),
                    "execution_config": original_execution_config,
                    "api_version": self.api_version,
                    "orchestrator_type": "langgraph-real",
                    "status": "failed",
                    "error_message": error_message,
                }

                nodes_executed = list(response.agent_outputs.keys()) if response.agent_outputs else []

                await question_repo.create_question(
                    query=request.query,
                    correlation_id=request.correlation_id,
                    execution_id=workflow_id,
                    nodes_executed=nodes_executed,
                    execution_metadata=execution_metadata,
                )

                logger.info(f"Failed workflow {workflow_id} persisted to database")

        except Exception as e:
            logger.error(f"Failed to persist failed workflow {workflow_id}: {e}")

    # -----------------------------------------------------------------------
    # Debugging and monitoring helpers
    # -----------------------------------------------------------------------

    def get_active_workflows(self) -> Dict[str, Dict[str, Any]]:
        """
        Return a snapshot of in-memory active workflows.

        Intended for:
        - Admin endpoints
        - Debug tooling
        - Development diagnostics
        """
        return {
            wf_id: {
                "status": wf["status"],
                "start_time": wf["start_time"],
                "query": wf["request"].query[:100],  # truncate to avoid log bloat
                "agents": wf["request"].agents,
                "elapsed_seconds": time.time() - wf["start_time"],
            }
            for wf_id, wf in self._active_workflows.items()
        }

    def get_workflow_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Return recent workflow history from in-memory storage.

        NOTE:
        This is not durable history. It is limited to what is still retained
        in _active_workflows. In production, prefer database-backed history.
        """
        workflows = list(self._active_workflows.values())
        workflows.sort(key=lambda x: x["start_time"], reverse=True)

        return [
            {
                "workflow_id": wf.get("workflow_id", "unknown"),
                "status": wf["status"],
                "query": wf["request"].query[:100],
                "start_time": wf["start_time"],
                "execution_time": wf.get("end_time", time.time()) - wf["start_time"],
            }
            for wf in workflows[:limit]
        ]

    async def get_workflow_history_from_database(
        self,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve workflow history from persistent storage (database).

        This uses QuestionRepository.get_recent_questions() to fetch stored
        workflow records and then maps them into a consistent history shape.

        Returns empty list on failure (best-effort behavior).
        """
        try:
            async with self._session_factory() as session:
                question_repo = QuestionRepository(session)
                questions = await question_repo.get_recent_questions(
                    limit=limit, offset=offset
                )

                return [
                    {
                        "workflow_id": q.execution_id or str(q.id),
                        "status": "completed",  # repository method currently returns completed entries
                        "query": q.query[:100] if q.query else "",
                        "start_time": q.created_at.timestamp(),
                        "execution_time": (
                            q.execution_metadata.get("execution_time_seconds", 0.0)
                            if q.execution_metadata
                            else 0.0
                        ),
                    }
                    for q in questions
                ]

        except Exception as e:
            logger.error(f"Failed to retrieve workflow history: {e}")
            return []

    def find_workflow_by_correlation_id(self, correlation_id: str) -> Optional[str]:
        """
        Find an in-memory workflow_id by correlation_id.

        Correlation IDs are useful for:
        - tracing requests across services
        - client-side idempotency keys
        - tying API requests back to logs/events

        Returns:
            workflow_id if found, else None
        """
        for workflow_id, workflow_data in self._active_workflows.items():
            request = workflow_data.get("request")
            if request and getattr(request, "correlation_id", None) == correlation_id:
                return workflow_id
        return None

    @ensure_initialized
    async def get_status_by_correlation_id(self, correlation_id: str) -> StatusResponse:
        """
        Get workflow execution status using correlation_id.

        This is a convenience wrapper:
        - Look up workflow_id by correlation_id
        - Delegate to get_status(workflow_id)

        Raises:
            KeyError if no workflow matches the correlation_id
        """
        workflow_id = self.find_workflow_by_correlation_id(correlation_id)
        if workflow_id is None:
            raise KeyError(f"No workflow found for correlation_id: {correlation_id}")

        return await self.get_status(workflow_id)
