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
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone  # UTC timestamps for telemetry/metadata
from pathlib import Path     # Filesystem paths (markdown export)
import json
import re

from OSSS.ai.analysis.pipeline import analyze_query
from OSSS.ai.analysis.policy import build_execution_plan
from OSSS.ai.analysis.models import QueryProfile
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
    for hit in mr:
        a = hit.get("action")
        if isinstance(a, str):
            a2 = _ACTION_ALIASES.get(a.strip().lower(), a.strip().lower())
        else:
            a2 = "read"

        if a2 not in _ALLOWED_ACTIONS:
            a2 = "read"

        hit["action"] = a2

    cleaned["matched_rules"] = mr

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
                qp = prof.model_dump()
            else:
                prof = analyze_query(query)
                prof.signals = dict(prof.signals or {})
                prof.signals.setdefault("analysis_source", "rules")
                qp = prof.model_dump()

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

    def _sanitize_query_profile_dict(data: dict) -> dict:
        """
        Make LLM-produced dict compatible with QueryProfile (Pydantic extra=forbid).
        - drops/renames unknown keys
        - coerces required string fields
        - normalizes matched_rules actions
        """
        if not isinstance(data, dict):
            return {}

        # --- key normalization (common LLM mistakes) ---
        if "sub_intentConfidence" in data and "sub_intent_confidence" not in data:
            data["sub_intent_confidence"] = data.pop("sub_intentConfidence")
        if "intentConfidence" in data and "intent_confidence" not in data:
            data["intent_confidence"] = data.pop("intentConfidence")
        if "toneConfidence" in data and "tone_confidence" not in data:
            data["tone_confidence"] = data.pop("toneConfidence")

        # --- required-ish string fields ---
        if data.get("intent") is None:
            data["intent"] = "general"
        if data.get("tone") is None:
            data["tone"] = "neutral"
        if data.get("sub_intent") is None:
            data["sub_intent"] = "general"

        # ensure strings (not None / numbers / dicts)
        for k, default in (("intent", "general"), ("tone", "neutral"), ("sub_intent", "general")):
            v = data.get(k)
            data[k] = v.strip() if isinstance(v, str) and v.strip() else default

        # confidences: coerce to float
        for k, default in (
                ("intent_confidence", 0.50),
                ("tone_confidence", 0.50),
                ("sub_intent_confidence", 0.50),
        ):
            v = data.get(k)
            data[k] = float(v) if isinstance(v, (int, float)) else float(default)

        # matched_rules normalization: your helper already drops extras,
        # but we also map invalid actions like "inform"
        action_map = {
            "inform": "explain",
            "answer": "explain",
            "search": "read",
            "research": "read",
        }

        mr = data.get("matched_rules")
        data["matched_rules"] = _normalize_rule_hits(mr)

        for hit in data["matched_rules"]:
            a = hit.get("action")
            if isinstance(a, str):
                a2 = action_map.get(a.lower().strip())
                if a2:
                    hit["action"] = a2

        # drop any remaining unknown top-level keys to satisfy extra=forbid
        allowed = {
            "intent", "intent_confidence",
            "tone", "tone_confidence",
            "sub_intent", "sub_intent_confidence",
            "signals",
            "matched_rules",
        }
        return {k: data[k] for k in list(data.keys()) if k in allowed}


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
      "action": "read|troubleshoot|create|review|explain|route",
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
        workflow_id = str(uuid.uuid4())
        start_time = time.time()

        # Preserve original config as received for persistence/auditing
        original_execution_config = request.execution_config or {}

        try:
            logger.info(
                f"Starting workflow {workflow_id} with query: {request.query[:100]}..."
            )

            # Emit workflow started event for telemetry systems
            emit_workflow_started(
                workflow_id=workflow_id,
                query=request.query,
                agents=request.agents,
                execution_config=request.execution_config,
                correlation_id=request.correlation_id,
                metadata={"api_version": self.api_version, "start_time": start_time},
            )

            # Track workflow execution in memory (used by get_status(), debugging)
            self._active_workflows[workflow_id] = {
                "status": "running",
                "request": request,
                "start_time": start_time,
                "workflow_id": workflow_id,
            }
            self._total_workflows += 1

            # Build orchestrator execution config from request data
            # IMPORTANT: copy dict to avoid mutating request.execution_config
            config = dict(original_execution_config)

            # ✅ Explicit flag (so downstream can rely on a real bool)
            config["use_llm_intent"] = bool(original_execution_config.get("use_llm_intent", False))

            # Preserve correlation_id for request tracing across services
            if request.correlation_id:
                config["correlation_id"] = request.correlation_id

            # Pass workflow_id so orchestrator doesn't generate a second ID
            config["workflow_id"] = workflow_id

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

            # ----------------------------------------------------------------
            # Preflight query analysis (intent / tone / sub-intent) + policy
            # ----------------------------------------------------------------

            llm: Optional[Any] = None
            query_profile: Optional[QueryProfile] = None

            try:
                use_llm_intent = bool(config.get("use_llm_intent", False))

                # ✅ One canonical path: ensure query_profile once per workflow_id
                qp = await self._ensure_query_profile(
                    workflow_id=workflow_id,
                    query=request.query,
                    use_llm_intent=use_llm_intent,
                    llm=llm,  # may be None; _ensure_query_profile will build it if needed
                    config=config,  # will be populated with config["query_profile"]
                )

                # If you need the typed object for build_execution_plan, reconstruct it
                # (If qp is malformed, fall back to deterministic rules)
                try:
                    query_profile = QueryProfile.model_validate(qp)
                except Exception:
                    query_profile = analyze_query(request.query)
                    query_profile.signals = dict(query_profile.signals or {})
                    query_profile.signals.setdefault("analysis_source", "rules_fallback")

                    # Also keep config in sync with the recovered profile
                    config["query_profile"] = query_profile.model_dump()
                    qp = config["query_profile"]

                logger.info(
                    "Preflight query_profile result",
                    extra={
                        "workflow_id": workflow_id,
                        "use_llm_intent": use_llm_intent,
                        "intent": query_profile.intent,
                        "intent_confidence": query_profile.intent_confidence,
                        "analysis_source": (query_profile.signals or {}).get("analysis_source"),
                        "llm_base_url": (getattr(llm, "base_url", None) if llm else None),
                        "llm_model": (getattr(llm, "model", None) if llm else None),
                    },
                )

            except Exception as analysis_error:
                logger.warning(
                    f"Preflight analysis failed; continuing with request config. error={analysis_error}"
                )

                # Ensure downstream always has a query_profile key
                config.setdefault("query_profile", {
                    "intent": "general",
                    "intent_confidence": 0.50,
                    "sub_intent": "general",
                    "sub_intent_confidence": 0.50,
                    "tone": "neutral",
                    "tone_confidence": 0.50,
                    "signals": {"analysis_source": "rules_fallback"},
                    "matched_rules": [{"rule": "intent:general:fallback", "action": "read"}],
                })

                try:
                    query_profile = QueryProfile.model_validate(config["query_profile"])
                except Exception:
                    query_profile = analyze_query(request.query)

                # 2) Build execution plan (maps profile -> agents/workflow/strategy)
                #    If you don't have a complexity score yet, start with a neutral default.
                plan = build_execution_plan(
                    query_profile,
                    complexity_score=float(config.get("complexity_score", 0.5)),
                )

                # -------------------------------
                # Confidence-based routing gates
                # -------------------------------
                thresholds = {
                    "min_intent_confidence": float(config.get("min_intent_confidence", 0.70)),
                    "min_plan_confidence": float(config.get("min_plan_confidence", 0.65)),
                    "min_sub_intent_confidence": float(config.get("min_sub_intent_confidence", 0.60)),
                    "min_tone_confidence": float(config.get("min_tone_confidence", 0.50)),
                }

                intent_ok = float(query_profile.intent_confidence or 0.0) >= thresholds["min_intent_confidence"]
                sub_intent_ok = float(query_profile.sub_intent_confidence or 0.0) >= thresholds["min_sub_intent_confidence"]
                tone_ok = float(query_profile.tone_confidence or 0.0) >= thresholds["min_tone_confidence"]
                plan_ok = float(getattr(plan, "confidence", 0.0) or 0.0) >= thresholds["min_plan_confidence"]

                # If intent is weak, we treat the whole routing decision as weak.
                routing_ok = intent_ok and plan_ok

                logger.info(
                    "Routing confidence gates evaluated",
                    extra={
                        "workflow_id": workflow_id,
                        "use_llm_intent": bool(config.get("use_llm_intent", False)),
                        "intent": query_profile.intent,
                        "intent_conf": query_profile.intent_confidence,
                        "sub_intent": query_profile.sub_intent,
                        "sub_intent_conf": query_profile.sub_intent_confidence,
                        "tone": query_profile.tone,
                        "tone_conf": query_profile.tone_confidence,
                        "plan_conf": getattr(plan, "confidence", None),
                        "thresholds": thresholds,
                        "routing_ok": routing_ok,
                    },
                )

                # Attach gates for debugging / persistence
                config["routing_gates"] = {
                    "thresholds": thresholds,
                    "intent_ok": intent_ok,
                    "sub_intent_ok": sub_intent_ok,
                    "tone_ok": tone_ok,
                    "plan_ok": plan_ok,
                    "routing_ok": routing_ok,
                }


                # 3) Attach to config so orchestrator and agents can see it (optional)
                #    This is useful for "Refiner-first" behavior, verbosity controls, etc.
                config["query_profile"] = query_profile.model_dump()

                logger.info(
                    "Preflight query_profile",
                    extra={
                        "workflow_id": workflow_id,
                        "use_llm_intent": use_llm_intent,
                        "intent": query_profile.intent,
                        "intent_confidence": query_profile.intent_confidence,
                        "analysis_source": (query_profile.signals or {}).get("analysis_source"),
                    },
                )

                """
                Exaple dump:
                {
                    "execution_strategy": "data_query_with_synthesis",
                    "confidence": 0.82,
                
                    # Agents the policy engine believes are best suited
                    "preferred_agents": [
                        "data_view_read",
                        "critic",
                        "synthesis"
                    ],
                
                    # Optional: a specific workflow template ID (if you support them)
                    "workflow_id": None,
                
                    # Optional: complexity estimate used for throttling / depth decisions
                    "complexity_score": 0.35,
                
                    # Optional: policy signals explaining *why* this plan was chosen
                    "signals": {
                        "primary_intent": "read",
                        "sub_intent": "data_query",
                        "data_domain": "students",
                        "requires_write_confirmation": False,
                        "safe_read_only": True
                    },
                
                    # Optional: rule-based decisions that influenced routing
                    "matched_rules": [
                        {
                            "rule": "intent:read",
                            "action": "read",
                            "category": "intent",
                            "score": 0.91
                        },
                        {
                            "rule": "domain:student_records",
                            "action": "read",
                            "category": "policy",
                            "score": 0.87
                        }
                    ]
                }

                """
                config["execution_plan"] = plan.model_dump()

                # 4) If the incoming request did NOT specify agents, honor policy agents
                #    (If request.agents is set, the caller is explicitly controlling routing.)
                # Caller always wins if they specified agents
                if not request.agents:
                    if routing_ok and plan.preferred_agents:
                        config["agents"] = plan.preferred_agents
                        config["routing_source"] = "policy"
                    else:
                        # fall back to safe default (or keep existing config["agents"] if already set)
                        config.setdefault("agents", ["refiner", "critic", "historian", "synthesis"])
                        config["routing_source"] = "default"
                else:
                    config["routing_source"] = "caller"

                # 5) Optional: honor workflow_id if your orchestrator supports it
                #    (Only apply if caller didn't already specify a workflow via config.)
                if routing_ok and plan.workflow_id and "workflow_id" not in original_execution_config:
                    # Keep workflow_id as the execution UUID; do NOT overwrite it.
                    config["selected_workflow_id"] = plan.workflow_id

                logger.info(
                    "Preflight analysis complete",
                    extra={
                        "workflow_id": workflow_id,
                        "intent": query_profile.intent,
                        "sub_intent": query_profile.sub_intent,
                        "tone": query_profile.tone,
                        "plan_strategy": plan.execution_strategy,
                        "plan_agents": plan.preferred_agents,
                        "plan_confidence": plan.confidence,
                    },
                )


            except Exception as analysis_error:

                logger.warning(

                    f"Preflight analysis failed; continuing with request config. error={analysis_error}"

                )

                # Ensure downstream always has a query_profile key

                config.setdefault("query_profile", {
                    "intent": "general",
                    "intent_confidence": 0.50,
                    "sub_intent": "general",
                    "sub_intent_confidence": 0.50,
                    "tone": "neutral",
                    "tone_confidence": 0.50,
                    "signals": {},
                    "matched_rules": [{"rule": "intent:general:fallback", "action": "read"}],

                })

            if bool(config.get("use_advanced_orchestrator", False)):
                from OSSS.ai.orchestration.advanced_adapter import AdvancedOrchestratorAdapter
                result_context = await AdvancedOrchestratorAdapter().run(request.query, config)
            else:
                result_context = await self._orchestrator.run(request.query, config)


            # Compute end-to-end duration
            execution_time = time.time() - start_time

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
            qp: Dict[str, Any] = {}
            try:
                qp = config.get("query_profile") or {}
                if not isinstance(qp, dict):
                    qp = {
                        "intent": "general",
                        "intent_confidence": 0.50,
                        "sub_intent": "general",
                        "sub_intent_confidence": 0.50,
                        "tone": "neutral",
                        "tone_confidence": 0.50,
                        "signals": {"fallback": True},
                        "matched_rules": [{"rule": "intent:general:fallback", "action": "read"}],
                    }
            except Exception:
                qp = {
                    "intent": "general",
                    "intent_confidence": 0.50,
                    "sub_intent": "general",
                    "sub_intent_confidence": 0.50,
                    "tone": "neutral",
                    "tone_confidence": 0.50,
                    "signals": {"fallback": True},
                    "matched_rules": [{"rule": "intent:general:fallback", "action": "read"}],
                }

            logger.info(
                "Query profile finalized",
                extra={
                    "workflow_id": workflow_id,
                    "intent": qp.get("intent"),
                    "sub_intent": qp.get("sub_intent"),
                    "tone": qp.get("tone"),
                    "analysis_source": qp.get("signals", {}).get("analysis_source"),
                    "use_llm_intent": use_llm_intent,
                },
            )

            # If preflight analysis didn't populate query_profile (or it is empty),
            # compute it now (cheap + deterministic) so envelope never returns nulls.
            if not qp:
                try:
                    if use_llm_intent:
                        if llm is None:
                            from OSSS.ai.llm.openai import OpenAIChatLLM
                            from OSSS.ai.config.openai_config import OpenAIConfig
                            cfg = OpenAIConfig.load()
                            llm = OpenAIChatLLM(api_key=cfg.api_key, model=cfg.model, base_url=cfg.base_url)

                        query_profile = await self._llm_analyze_query_profile_best_effort(
                            request.query,
                            llm=llm,
                        )


                    else:
                        query_profile = analyze_query(request.query)
                        query_profile.signals = dict(query_profile.signals or {})
                        query_profile.signals.setdefault("analysis_source", "rules")

                    qp = query_profile.model_dump()
                    config["query_profile"] = qp
                except Exception as e:
                    logger.warning(f"Failed to compute query_profile fallback: {e}")
                    qp = {
                        "intent": "general",
                        "intent_confidence": 0.50,
                        "sub_intent": "general",
                        "sub_intent_confidence": 0.50,
                        "tone": "neutral",
                        "tone_confidence": 0.50,
                        "signals": {"analysis_source": "rules_fallback", "fallback": True},
                        "matched_rules": [{"rule": "intent:general:fallback", "action": "read"}],
                    }


            # Keep a copy at a stable location for debugging/clients
            use_llm_intent = bool(config.get("use_llm_intent", False))

            # Keep a copy at a stable location for debugging/clients
            # ----------------------------------------------------------------
            # Canonical query profile envelope (ALWAYS present)
            # ----------------------------------------------------------------
            agent_output_meta["_query_profile"] = qp
            agent_output_meta["_query_profile"].setdefault("signals", {})

            # preserve more specific source if it exists (e.g., rules_fallback)
            agent_output_meta["_query_profile"]["signals"].setdefault(
                "analysis_source",
                "llm" if use_llm_intent else "rules",
            )

            agent_output_meta["_routing"] = {
                "source": config.get("routing_source", "unknown"),
                "gates": config.get("routing_gates", {}),
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
                # Legacy: List[str] -> upgrade to structured hits
                if qp_matched and isinstance(qp_matched[0], str):
                    normalized_matched = [
                        {
                            "category": "analysis",
                            "rule_id": r,
                            "label": r,
                            "action": "read",
                            "confidence": 0.50,
                        }
                        for r in qp_matched
                    ]

                # Preferred: List[dict] (RuleHit)
                elif qp_matched and isinstance(qp_matched[0], dict):
                    for item in qp_matched:
                        if not isinstance(item, dict):
                            continue
                        # Ensure required-ish fields exist without overwriting real values
                        item.setdefault("action", "read")
                        item.setdefault("confidence", 0.50)
                        item.setdefault("label", item.get("rule_id") or item.get("rule") or "rule_hit")
                        # If someone used "rule" instead of "rule_id", normalize gently
                        if "rule_id" not in item and "rule" in item:
                            item["rule_id"] = item["rule"]
                        normalized_matched.append(item)

            qp_matched = normalized_matched

            # ----------------------------------------------------------------
            # Optional: Per-agent LLM analysis (intent/tone/sub-intent)
            # NOTE: must happen AFTER we know executed agents and have exec_state,
            #       but BEFORE we fan-out envelopes.
            # ----------------------------------------------------------------
            enable_llm_agent_analysis = False
            try:
                enable_llm_agent_analysis = bool(
                    config.get("enable_llm_query_analysis", False) or config.get("use_llm_intent", False)
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
            for agent_name in serialized_agent_outputs.keys():
                envelope = agent_output_meta.get(agent_name)
                if not isinstance(envelope, dict):
                    envelope = {}
                    agent_output_meta[agent_name] = envelope

                envelope.setdefault("agent", agent_name)
                envelope.setdefault("action", "read")

                prof = agent_profiles.get(agent_name)

                if prof is not None:
                    # QueryProfile instance or dict-like
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
                    envelope["matched_rules"] = prof_dict.get("matched_rules") or []

                    envelope["analysis_source"] = "llm"
                else:
                    # Existing behavior (base query_profile)
                    if envelope.get("intent") is None:
                        envelope["intent"] = qp_intent
                    if envelope.get("sub_intent") is None:
                        envelope["sub_intent"] = qp_sub_intent
                    if envelope.get("tone") is None:
                        envelope["tone"] = qp_tone

                    if envelope.get("intent_confidence") is None:
                        envelope["intent_confidence"] = float(qp_intent_conf)
                    if envelope.get("sub_intent_confidence") is None:
                        envelope["sub_intent_confidence"] = float(qp_sub_intent_conf)
                    if envelope.get("tone_confidence") is None:
                        envelope["tone_confidence"] = float(qp_tone_conf)

                    if envelope.get("signals") is None:
                        envelope["signals"] = qp_signals
                    if envelope.get("matched_rules") is None:
                        envelope["matched_rules"] = qp_matched

                    envelope.setdefault("analysis_source", "rules")

            # Build response model for API clients
            response = WorkflowResponse(
                workflow_id=workflow_id,
                status="completed",
                agent_outputs=serialized_agent_outputs,
                execution_time_seconds=execution_time,
                correlation_id=request.correlation_id,
                agent_output_meta=agent_output_meta,  # ✅ now stable + contains action
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

                                # Read markdown content from disk for persistence
                                with open(md_path_obj, "r", encoding="utf-8") as md_file:
                                    markdown_content = md_file.read()

                                topics_list = suggested_topics[:5] if suggested_topics else []

                                await doc_repo.get_or_create_document(
                                    title=request.query[:200],  # Prevent oversized titles
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
                    # Markdown export is optional: failure becomes response metadata, not a crash
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
                {"status": "completed", "response": response, "end_time": time.time()}
            )

            # Emit completion event for telemetry
            emit_workflow_completed(
                workflow_id=workflow_id,
                status="completed",
                execution_time_seconds=execution_time,
                agent_outputs=result_context.agent_outputs,
                correlation_id=request.correlation_id,
                metadata={
                    "api_version": self.api_version,
                    "end_time": time.time(),
                    "agent_output_meta": agent_output_meta,  # ✅ safe: nested under metadata
                },
            )

            logger.info(
                f"Workflow {workflow_id} completed successfully in {execution_time:.2f}s"
            )
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
                correlation_id=request.correlation_id,
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
            emit_workflow_completed(
                workflow_id=workflow_id,
                status="failed",
                execution_time_seconds=execution_time,
                error_message=str(e),
                error_type=type(e).__name__,
                correlation_id=request.correlation_id,
                metadata={"api_version": self.api_version, "end_time": time.time()},
            )

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

        if status in ("completed", "failed"):
            # Completed/failed workflows are considered 100% "done"
            progress = 100.0

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
                    "agents_requested": request.agents
                    or ["refiner", "critic", "historian", "synthesis"],
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
                    "agents_requested": request.agents
                    or ["refiner", "critic", "historian", "synthesis"],
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
