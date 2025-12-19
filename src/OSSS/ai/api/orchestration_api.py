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
from typing import Dict, Any, Optional, List, Callable, Tuple, Awaitable
from datetime import datetime, timezone  # UTC timestamps for telemetry/metadata
from pathlib import Path     # Filesystem paths (markdown export)
import json
import re
from dataclasses import dataclass
import inspect

from sqlalchemy.exc import IntegrityError

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


# Workflow template id (external) -> internal graph id (runner key)
WORKFLOW_TO_GRAPH: Dict[str, str] = {
    "data-views-demo": "graph_data_views",
    # add more templates here
}


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


@dataclass(frozen=True)
class WorkflowIdentity:
    workflow_run_id: str
    correlation_id: str
    start_time: float


@dataclass
class PreflightResult:
    qp: Dict[str, Any]                 # canonical query_profile dict
    decision: Dict[str, Any]           # routing decision dict
    selected_graph: str                # resolved graph id / workflow id
    routing_source: str                # caller|gate|registry|...
    config: Dict[str, Any]             # mutated config (canonicalized)


@dataclass
class ExecutionResult:
    context: Any                       # AgentContext-like or None for bypass
    agent_outputs: Dict[str, Any]      # normalized outputs (serializable later)
    agent_output_meta: Dict[str, Any]  # envelopes + _query_profile + _routing
    executed_agents: List[str]         # for telemetry/debug


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
        if asyncio.iscoroutine(maybe_awaitable):
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

    cleaned["tone"] = _as_str(cleaned.get("tone"), "neutral")

    # ✅ normalize tone like "inquiry|neutral" -> "neutral"
    tone = cleaned["tone"]
    if "|" in tone:
        cleaned["tone"] = tone.split("|")[-1].strip() or "neutral"

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

    def _apply_caller_workflow_override(self, config: Dict[str, Any]) -> None:
        requested = (config.get("selected_workflow_id") or "").strip()
        if not requested:
            return

        # If caller passed a graph id directly, accept it
        if requested.startswith("graph_"):
            config["selected_graph"] = requested
            config["routing_source"] = "caller"
            return

        # Otherwise map workflow template -> graph
        mapped = WORKFLOW_TO_GRAPH.get(requested)
        if mapped:
            config["selected_graph"] = mapped
            config["routing_source"] = "caller"

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

        async def run_data_views(q: str, c: Dict[str, Any]) -> Any:
            # If your adapter supports it:
            return await AdvancedOrchestratorAdapter(graph="data_views").run(q, c)

        GRAPH_RUNNERS: Dict[str, AsyncRunner] = {
            "graph_default": run_default,
            "graph_diagnostics": run_diagnostics,
            "graph_builder": run_builder,
            "graph_data_read": run_data_read,
            "graph_data_views": run_data_views,
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
        intent_conf = float(decision.get("intent_confidence") or 0.0)

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

        logger.info(
            "\n##################\n##################\nNew workflow\n##################\n##################\n"
        )

        ident = self._init_identity(request)
        config = self._init_config(request, ident)

        # Preflight always runs exactly once per request
        preflight = await self._preflight_analysis_and_routing(request, config)

        self._log_routing_selected(ident.workflow_run_id, preflight)

        # fast path: explicit agents=[]
        if self._should_bypass_orchestrator(request):
            exec_result, status, error_msg = await self._run_direct_llm_bypass(request, ident, preflight)
            response = self._build_response(ident, status, error_msg, exec_result)
            await self._after_response(request, ident, preflight, response, exec_result, status, error_msg)
            return response

        # orchestrator path
        exec_result, status, error_msg = await self._run_orchestrator_path(request, ident, preflight)
        response = await self._maybe_export_markdown(request, ident, response=self._build_response(
            ident, status, error_msg, exec_result
        ))

        await self._after_response(request, ident, preflight, response, exec_result, status, error_msg)
        return response

    # ---------------------------------------------------------------------
    # 1) INIT
    # ---------------------------------------------------------------------
    def _init_identity(self, request: WorkflowRequest) -> WorkflowIdentity:
        workflow_run_id = str(uuid.uuid4())
        correlation_id = request.correlation_id or f"req-{uuid.uuid4()}"
        return WorkflowIdentity(workflow_run_id=workflow_run_id, correlation_id=correlation_id, start_time=time.time())

    def _init_config(self, request: WorkflowRequest, ident: WorkflowIdentity) -> Dict[str, Any]:
        original_execution_config = request.execution_config or {}
        config: Dict[str, Any] = dict(original_execution_config)

        # canonical flags
        config["use_llm_intent"] = bool(original_execution_config.get("use_llm_intent", False))
        config["correlation_id"] = ident.correlation_id
        config["workflow_id"] = ident.workflow_run_id  # run id

        # caller-selected workflow/template id (UI chooses workflow_id)
        requested = (getattr(request, "workflow_id", None) or "").strip()
        if requested:
            # "selected_workflow_id" is the template id; run id stays in workflow_id
            config["selected_workflow_id"] = requested
            config["routing_source"] = "caller"

        # optional agents restriction (only if non-empty)
        if request.agents:
            config["agents"] = request.agents

        return config

    # ---------------------------------------------------------------------
    # 2) PREFLIGHT (ANALYSIS + GATES + GRAPH RESOLVE)
    # ---------------------------------------------------------------------
    async def _preflight_analysis_and_routing(self, request: WorkflowRequest, config: Dict[str, Any]) -> PreflightResult:
        # Always attempt analysis; if it fails, fall back to safe qp/decision.
        try:
            qp = await self._ensure_query_profile(
                workflow_id=config["workflow_id"],
                query=request.query,
                use_llm_intent=bool(config.get("use_llm_intent", False)),
                llm=None,
                config=config,
            )

            # policy/tone hooks BEFORE graph runs
            self._apply_tone_policy(config, qp)

            query_profile = QueryProfile.model_validate(qp)
            decision_model = build_routing_decision(query_profile)
            decision = decision_model.model_dump()

            config["query_profile"] = qp
            config["routing_decision"] = decision

            # ✅ apply caller workflow_id -> selected_graph mapping
            self._apply_caller_workflow_override(config)

            # gates may override graph (unless caller chose one)
            if config.get("routing_source") != "caller":
                self._apply_confidence_gates(config)

            # resolve graph if none chosen by caller or gate
            if not config.get("selected_graph"):
                graph_id = GRAPH_REGISTRY.resolve(decision)
                config["selected_graph"] = graph_id
                config["routing_source"] = "registry"
            else:
                config.setdefault("routing_source", "caller_or_gate")

            # gates may override graph (unless caller chose one)
            if config.get("routing_source") != "caller":
                self._apply_confidence_gates(config)

            # resolve graph if none chosen by caller or gate
            if not config.get("selected_graph"):
                graph_id = GRAPH_REGISTRY.resolve(decision)
                config["selected_graph"] = graph_id
                config["routing_source"] = "registry"
            else:
                config.setdefault("routing_source", "caller_or_gate")

            return PreflightResult(
                qp=self._get_or_default_query_profile(config),
                decision=config.get("routing_decision") or {},
                selected_graph=str(config.get("selected_graph") or ""),
                routing_source=str(config.get("routing_source") or "unknown"),
                config=config,
            )

        except Exception as e:
            # single fallback block; keep it minimal & deterministic
            logger.warning(
                "Global preflight analysis failed; using safe fallback",
                extra={"workflow_id": config.get("workflow_id"), "error": str(e)},
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
            config["routing_decision"] = {"action": "read", "intent": "general", "tone": "neutral", "sub_intent": "general"}

            # gates can still pick a graph
            if config.get("routing_source") != "caller":
                self._apply_confidence_gates(config)

            if not config.get("selected_graph"):
                config["selected_graph"] = GRAPH_REGISTRY.resolve(config["routing_decision"])
                config["routing_source"] = "registry:fallback"
            else:
                config.setdefault("routing_source", "gate_or_caller:fallback")

            return PreflightResult(
                qp=qp,
                decision=config["routing_decision"],
                selected_graph=str(config.get("selected_graph") or ""),
                routing_source=str(config.get("routing_source") or "unknown"),
                config=config,
            )

    def _log_routing_selected(self, workflow_run_id: str, preflight: PreflightResult) -> None:
        logger.info(
            "Routing selected",
            extra={
                "workflow_id": workflow_run_id,
                "selected_graph": preflight.selected_graph,
                "routing_source": preflight.routing_source,
                "routing_gates": preflight.config.get("routing_gates"),
            },
        )

    # ---------------------------------------------------------------------
    # 3) RUNNERS
    # ---------------------------------------------------------------------
    def _should_bypass_orchestrator(self, request: WorkflowRequest) -> bool:
        return isinstance(request.agents, list) and len(request.agents) == 0

    async def _run_direct_llm_bypass(
        self,
        request: WorkflowRequest,
        ident: WorkflowIdentity,
        preflight: PreflightResult,
    ) -> Tuple[ExecutionResult, str, Optional[str]]:
        # telemetry start (best-effort)
        self._track_active_workflow(ident, request, status="running", query_profile=preflight.qp)
        self._emit_started_safe(ident, request, agents=[],
                                metadata={"routing_source": "direct_llm_bypass", "query_profile": preflight.qp})

        llm_answer = await self._call_direct_llm(request.query)
        elapsed = time.time() - ident.start_time

        agent_output_meta = self._build_base_meta(preflight, final_agents=[], graph="llm", source="direct_llm_bypass")
        agent_output_meta["llm"] = {
            "agent": "llm",
            "action": "read",
            "intent": preflight.qp.get("intent", "general"),
            "intent_confidence": preflight.qp.get("intent_confidence", 0.5),
            "sub_intent": preflight.qp.get("sub_intent", "general"),
            "sub_intent_confidence": preflight.qp.get("sub_intent_confidence", 0.5),
            "tone": preflight.qp.get("tone", "neutral"),
            "tone_confidence": preflight.qp.get("tone_confidence", 0.5),
            "signals": preflight.qp.get("signals", {}),
            "matched_rules": preflight.qp.get("matched_rules", []),
            "analysis_source": (preflight.qp.get("signals") or {}).get("analysis_source", "rules"),
        }

        exec_result = ExecutionResult(
            context=None,
            agent_outputs={"llm": llm_answer},
            agent_output_meta=agent_output_meta,
            executed_agents=["llm"],
        )
        return exec_result, "completed", None

    async def _run_orchestrator_path(
        self,
        request: WorkflowRequest,
        ident: WorkflowIdentity,
        preflight: PreflightResult,
    ) -> Tuple[ExecutionResult, str, Optional[str]]:
        self._track_active_workflow(ident, request, status="running", query_profile=preflight.qp)

        safe_agents = list(request.agents or [])
        self._emit_started_safe(ident, request, agents=safe_agents, metadata={"query_profile": preflight.qp})

        # orchestrator call
        result_context = await self._run_selected_graph(request.query, preflight.config)
        exec_result = self._extract_execution_result(request, preflight, result_context)

        # decide final status once
        if not exec_result.agent_outputs:
            exec_result.agent_outputs = {"synthesis": "No agent outputs produced."}
            err = "No agent outputs produced."
            self._append_error(exec_result.agent_output_meta, err, preflight)
            return exec_result, "failed", err

        return exec_result, "completed", None

    # ---------------------------------------------------------------------
    # 4) OUTPUT + META EXTRACTION (single place)
    # ---------------------------------------------------------------------
    def _extract_execution_result(
        self,
        request: WorkflowRequest,
        preflight: PreflightResult,
        result_context: Any,
    ) -> ExecutionResult:
        exec_state: Dict[str, Any] = {}
        maybe_state = getattr(result_context, "execution_state", None)
        if isinstance(maybe_state, dict):
            exec_state = maybe_state

        structured_outputs = exec_state.get("structured_outputs") if isinstance(exec_state.get("structured_outputs"), dict) else {}
        state_agent_outputs = exec_state.get("agent_outputs") if isinstance(exec_state.get("agent_outputs"), dict) else {}
        raw_agent_outputs = getattr(result_context, "agent_outputs", None) if isinstance(getattr(result_context, "agent_outputs", None), dict) else {}

        executed_agents = list(dict.fromkeys(list(structured_outputs.keys()) + list(state_agent_outputs.keys()) + list(raw_agent_outputs.keys())))
        agent_outputs = {}
        for name in executed_agents:
            if name in structured_outputs:
                agent_outputs[name] = structured_outputs[name]
            elif name in state_agent_outputs:
                agent_outputs[name] = state_agent_outputs[name]
            else:
                agent_outputs[name] = raw_agent_outputs.get(name, "")

        serialized_agent_outputs = self._convert_agent_outputs_to_serializable(agent_outputs)

        # meta
        agent_output_meta = {}
        aom = exec_state.get("agent_output_meta")
        if isinstance(aom, dict):
            agent_output_meta = aom

        base_meta = self._build_base_meta(
            preflight,
            final_agents=(preflight.config.get("agents") or []),
            graph=preflight.config.get("selected_graph"),
            source=preflight.config.get("routing_source", "unknown"),
        )
        agent_output_meta.update(base_meta)

        # Fan-out base qp into each agent envelope (simple/consistent)
        self._fanout_profile_into_agent_envelopes(agent_output_meta, serialized_agent_outputs.keys(), preflight.qp)

        return ExecutionResult(
            context=result_context,
            agent_outputs=serialized_agent_outputs,
            agent_output_meta=agent_output_meta,
            executed_agents=executed_agents,
        )

    def _build_base_meta(self, preflight: PreflightResult, final_agents: List[str], graph: str, source: str) -> Dict[str, Any]:
        qp = preflight.qp or {}
        return {
            "_query_profile": qp,
            "_routing": {
                "source": source,
                "decision": preflight.decision,
                "gates": preflight.config.get("routing_gates", {}),
                "graph": graph,
                "selected_workflow_id": preflight.config.get("selected_workflow_id"),
                "final_agents": final_agents,
            },
        }

    def _fanout_profile_into_agent_envelopes(self, agent_output_meta: Dict[str, Any], agent_names, qp: Dict[str, Any]) -> None:
        intent = qp.get("intent", "general")
        sub_intent = qp.get("sub_intent", "general")
        tone = qp.get("tone", "neutral")

        intent_c = float(qp.get("intent_confidence") or 0.5)
        sub_c = float(qp.get("sub_intent_confidence") or 0.5)
        tone_c = float(qp.get("tone_confidence") or 0.5)

        signals = qp.get("signals") or {}
        matched = qp.get("matched_rules") or []

        for agent_name in agent_names:
            env = agent_output_meta.get(agent_name)
            if not isinstance(env, dict):
                env = {}
                agent_output_meta[agent_name] = env

            env.setdefault("agent", agent_name)
            env.setdefault("action", "read")
            env.setdefault("intent", intent)
            env.setdefault("sub_intent", sub_intent)
            env.setdefault("tone", tone)
            env.setdefault("intent_confidence", intent_c)
            env.setdefault("sub_intent_confidence", sub_c)
            env.setdefault("tone_confidence", tone_c)
            env.setdefault("signals", signals)
            env.setdefault("matched_rules", matched)
            env.setdefault("analysis_source", signals.get("analysis_source") or "rules")

    def _append_error(self, agent_output_meta: Dict[str, Any], msg: str, preflight: PreflightResult) -> None:
        err_bucket = agent_output_meta.setdefault("_errors", {})
        items = err_bucket.setdefault("items", [])
        if isinstance(items, list):
            items.append({
                "type": "workflow_error",
                "message": msg,
                "selected_graph": preflight.selected_graph,
                "routing_source": preflight.routing_source,
                "agents_requested": list(preflight.config.get("agents") or []),
            })

    # ---------------------------------------------------------------------
    # 5) RESPONSE BUILDING
    # ---------------------------------------------------------------------
    def _build_response(
        self,
        ident: WorkflowIdentity,
        status: str,
        error_message: Optional[str],
        exec_result: ExecutionResult,
    ) -> WorkflowResponse:
        elapsed = time.time() - ident.start_time
        return WorkflowResponse(
            workflow_id=ident.workflow_run_id,
            status=status,
            agent_outputs=exec_result.agent_outputs or {},
            agent_output_meta=exec_result.agent_output_meta or {},
            execution_time_seconds=elapsed,
            correlation_id=ident.correlation_id,
            error_message=error_message,
            markdown_export=None,
        )

    # ---------------------------------------------------------------------
    # 6) OPTIONAL EXPORT (kept isolated)
    # ---------------------------------------------------------------------
    async def _maybe_export_markdown(self, request: WorkflowRequest, ident: WorkflowIdentity, response: WorkflowResponse) -> WorkflowResponse:
        if not request.export_md:
            return response
        if response.status != "completed":
            response.markdown_export = {
                "error": "Export skipped",
                "message": "Workflow did not complete successfully; no outputs to export.",
                "export_timestamp": datetime.now(timezone.utc).isoformat(),
            }
            return response

        try:
            from OSSS.ai.store.wiki_adapter import MarkdownExporter
            from OSSS.ai.store.topic_manager import TopicManager
            from OSSS.ai.llm.openai import OpenAIChatLLM
            from OSSS.ai.config.openai_config import OpenAIConfig

            llm_config = OpenAIConfig.load()
            llm = OpenAIChatLLM(api_key=llm_config.api_key, model=llm_config.model, base_url=llm_config.base_url)
            topic_manager = TopicManager(llm=llm)

            try:
                topic_analysis = await topic_manager.analyze_and_suggest_topics(
                    query=request.query,
                    agent_outputs=response.agent_outputs,
                )
                suggested_topics = [s.topic for s in topic_analysis.suggested_topics]
                suggested_domain = topic_analysis.suggested_domain
            except Exception:
                suggested_topics, suggested_domain = [], None

            exporter = MarkdownExporter()
            md_path = exporter.export(
                agent_outputs=response.agent_outputs,
                question=request.query,
                topics=suggested_topics,
                domain=suggested_domain,
            )
            md_path_obj = Path(md_path)

            response.markdown_export = {
                "file_path": str(md_path_obj.absolute()),
                "filename": md_path_obj.name,
                "export_timestamp": datetime.now(timezone.utc).isoformat(),
                "suggested_topics": (suggested_topics[:5] if suggested_topics else []),
                "suggested_domain": suggested_domain,
            }
            return response

        except Exception as e:
            response.markdown_export = {
                "error": "Export failed",
                "message": str(e),
                "export_timestamp": datetime.now(timezone.utc).isoformat(),
            }
            return response

    # ---------------------------------------------------------------------
    # 7) AFTER RESPONSE: persistence, telemetry, cleanup
    # ---------------------------------------------------------------------
    async def _after_response(
        self,
        request: WorkflowRequest,
        ident: WorkflowIdentity,
        preflight: PreflightResult,
        response: WorkflowResponse,
        exec_result: ExecutionResult,
        status: str,
        error_message: Optional[str],
    ) -> None:
        # update in-memory tracking
        if ident.workflow_run_id in self._active_workflows:
            self._active_workflows[ident.workflow_run_id].update({"status": status, "response": response, "end_time": time.time()})

        # persist workflow (best-effort)
        try:
            await self._persist_workflow_to_database(
                request,
                response,
                exec_result.context,
                ident.workflow_run_id,
                request.execution_config or {},
            )
        except Exception as e:
            logger.error(f"Failed to persist workflow {ident.workflow_run_id}: {e}")

        # telemetry complete (best-effort)
        try:
            await emit_workflow_completed(
                workflow_id=ident.workflow_run_id,
                status=status,
                execution_time_seconds=(time.time() - ident.start_time),
                agent_outputs=(response.agent_outputs if status == "completed" else {}),
                error_message=(error_message if status != "completed" else None),
                correlation_id=ident.correlation_id,
                metadata={"api_version": self.api_version, "agent_output_meta": response.agent_output_meta},
            )
        except Exception:
            pass

        self._cleanup_query_profile_state(ident.workflow_run_id)

    # ---------------------------------------------------------------------
    # 8) SMALL IO HELPERS (keep existing behavior)
    # ---------------------------------------------------------------------
    def _track_active_workflow(self, ident: WorkflowIdentity, request: WorkflowRequest, status: str, query_profile: Dict[str, Any]) -> None:
        self._active_workflows[ident.workflow_run_id] = {
            "status": status,
            "request": request,
            "start_time": ident.start_time,
            "workflow_id": ident.workflow_run_id,
            "query_profile": query_profile,
        }
        self._total_workflows += 1

    def _emit_started_safe(self, ident: WorkflowIdentity, request: WorkflowRequest, agents: List[str], metadata: Dict[str, Any]) -> None:
        try:
            _fire_and_forget(emit_workflow_started(
                workflow_id=ident.workflow_run_id,
                query=request.query,
                agents=list(agents or []),
                execution_config=request.execution_config or {},
                correlation_id=ident.correlation_id,
                metadata={"api_version": self.api_version, "start_time": ident.start_time, **(metadata or {})},
            ))
        except Exception:
            pass

    async def _call_direct_llm(self, query: str) -> str:
        from OSSS.ai.config.openai_config import OpenAIConfig
        from OSSS.ai.llm.openai import OpenAIChatLLM

        llm_config = OpenAIConfig.load()
        llm = OpenAIChatLLM(api_key=llm_config.api_key, model=llm_config.model, base_url=llm_config.base_url)

        system_prompt = (
            "You are OSSS. Answer the user's request directly and concretely.\n"
            "If the user asks for a list, return a list.\n"
            "Do not rewrite the request into meta-analysis."
        )
        resp = await llm.ainvoke(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": query}]
        )
        return _coerce_llm_text(resp).strip()

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

                try:

                    await question_repo.create_question(
                        query=request.query,
                        correlation_id=response.correlation_id,
                        execution_id=workflow_id,
                        nodes_executed=nodes_executed,
                        execution_metadata=execution_metadata,
                    )

                except IntegrityError as ie:
                    # ✅ idempotent retry: correlation_id already stored
                    # asyncpg UniqueViolationError is usually ie.orig
                    logger.info(
                        "Question already exists for correlation_id; treating as idempotent success",
                        extra={"workflow_id": workflow_id, "correlation_id": response.correlation_id},
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

                try:

                    await question_repo.create_question(
                        query=request.query,
                        correlation_id=response.correlation_id,
                        execution_id=workflow_id,
                        nodes_executed=nodes_executed,
                        execution_metadata=execution_metadata,
                    )

                except IntegrityError as ie:
                    # ✅ idempotent retry: correlation_id already stored
                    # asyncpg UniqueViolationError is usually ie.orig
                    msg = str(getattr(ie, "orig", ie))
                    if "questions_correlation_id_key" in msg or "correlation_id" in msg:
                        logger.info(
                            "Question already exists for correlation_id; treating as idempotent success",
                            extra={"workflow_id": workflow_id, "correlation_id": response.correlation_id},
                        )
                    else:
                        raise

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
