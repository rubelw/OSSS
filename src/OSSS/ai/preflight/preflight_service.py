# OSSS/ai/preflight/preflight_service.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional

import asyncio

from OSSS.ai.analysis.pipeline import analyze_query
from OSSS.ai.analysis.models import QueryProfile, build_routing_decision
from OSSS.ai.config.openai_config import OpenAIConfig
from OSSS.ai.llm.openai import OpenAIChatLLM
from OSSS.ai.llm.utils import call_llm_text
from OSSS.ai.observability import get_logger
from OSSS.ai.orchestration.graph_registry import GRAPH_REGISTRY
from OSSS.ai.preflight.query_profile_codec import (
    coerce_llm_text,
    extract_first_json_object,
    sanitize_query_profile_dict,
)

logger = get_logger(__name__)

WORKFLOW_TO_GRAPH = {
    "data-views-demo": "graph_data_views",
}

@dataclass
class PreflightResult:
    qp: Dict[str, Any]
    decision: Dict[str, Any]
    selected_graph: str
    routing_source: str
    config: Dict[str, Any]


class PreflightService:
    def __init__(self) -> None:
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    def _lock(self, workflow_id: str) -> asyncio.Lock:
        self._locks.setdefault(workflow_id, asyncio.Lock())
        return self._locks[workflow_id]

    async def preflight(self, *, request, config: Dict[str, Any]) -> PreflightResult:
        qp = await self._ensure_query_profile(
            workflow_id=config["workflow_id"],
            query=request.query,
            use_llm_intent=bool(config.get("use_llm_intent", False)),
            config=config,
        )

        self._apply_tone_policy(config, qp)

        decision_model = build_routing_decision(QueryProfile.model_validate(qp))
        decision = decision_model.model_dump()
        config["query_profile"] = qp
        config["routing_decision"] = decision

        # precedence: caller -> gates -> registry
        self._apply_caller_workflow_override(config)

        if config.get("routing_source") != "caller":
            self._apply_confidence_gates(config)

        if not config.get("selected_graph"):
            config["selected_graph"] = GRAPH_REGISTRY.resolve(decision)
            config["routing_source"] = "registry"
        else:
            config.setdefault("routing_source", "caller_or_gate")

        return PreflightResult(
            qp=qp,
            decision=decision,
            selected_graph=str(config.get("selected_graph") or ""),
            routing_source=str(config.get("routing_source") or "unknown"),
            config=config,
        )

    def _apply_caller_workflow_override(self, config: Dict[str, Any]) -> None:
        requested = (config.get("selected_workflow_id") or "").strip()
        if not requested:
            return
        if requested.startswith("graph_"):
            config["selected_graph"] = requested
            config["routing_source"] = "caller"
            return
        mapped = WORKFLOW_TO_GRAPH.get(requested)
        if mapped:
            config["selected_graph"] = mapped
            config["routing_source"] = "caller"

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
        if intent_conf < min_conf:
            config["routing_gates"] = {"intent_confidence_below_threshold": True, "min": min_conf, "got": intent_conf}
            config["selected_graph"] = "graph_clarify"
            config["routing_source"] = "gate:intent_confidence"

    async def _ensure_query_profile(self, *, workflow_id: str, query: str, use_llm_intent: bool, config: Dict[str, Any]) -> Dict[str, Any]:
        if workflow_id in self._cache:
            config["query_profile"] = self._cache[workflow_id]
            return self._cache[workflow_id]

        async with self._lock(workflow_id):
            if workflow_id in self._cache:
                config["query_profile"] = self._cache[workflow_id]
                return self._cache[workflow_id]

            if use_llm_intent:
                qp = await self._llm_query_profile_best_effort(query)
            else:
                prof = analyze_query(query)
                qp = prof.model_dump(mode="json")
                qp.setdefault("signals", {})
                qp["signals"].setdefault("analysis_source", "rules")

            self._cache[workflow_id] = qp
            config["query_profile"] = qp
            return qp

    async def _llm_query_profile_best_effort(self, query: str) -> Dict[str, Any]:
        q = (query or "").strip()
        if not q:
            prof = QueryProfile()
            return prof.model_dump(mode="json")

        cfg = OpenAIConfig.load()
        llm = OpenAIChatLLM(api_key=cfg.api_key, model=cfg.model, base_url=cfg.base_url)

        prompt = "... your JSON schema prompt ..."
        try:
            raw = await call_llm_text(llm, prompt)
            text = coerce_llm_text(raw).strip()
            data = sanitize_query_profile_dict(__import__("json").loads(extract_first_json_object(text)))
            prof = QueryProfile.model_validate(data)
            out = prof.model_dump(mode="json")
            out.setdefault("signals", {})
            out["signals"]["analysis_source"] = "llm"
            return out
        except Exception as e:
            logger.warning("LLM query_profile failed; falling back to rules", extra={"error": str(e)})
            prof = analyze_query(q)
            out = prof.model_dump(mode="json")
            out.setdefault("signals", {})
            out["signals"]["analysis_source"] = "rules_fallback"
            out["signals"]["llm_error"] = str(e)
            return out
