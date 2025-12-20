# OSSS/ai/preflight/preflight_service.py
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional

from OSSS.ai.analysis.models import QueryProfile, build_routing_decision
from OSSS.ai.analysis.pipeline import analyze_query
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
from OSSS.ai.workflows.template_loader import WorkflowTemplateLoader  # ✅ add

logger = get_logger(__name__)


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

        # ✅ load workflow templates once per process (cache in loader)
        # (keep your existing attribute name if you want; this is the requested behavior)
        self._templates = WorkflowTemplateLoader()

    def _qp_cache_key(self, query: str, use_llm_intent: bool) -> str:
        q = (query or "").strip().lower()
        return f"{'llm' if use_llm_intent else 'rules'}::{q}"

    def _lock(self, key: str) -> asyncio.Lock:
        self._locks.setdefault(key, asyncio.Lock())
        return self._locks[key]

    # ✅ treat underscores and hyphens as equivalent for caller convenience
    #    (file name might be data_views_demo.yaml, but workflow_id is data-views-demo)
    def _normalize_workflow_slug(self, slug: str) -> str:
        s = (slug or "").strip()
        if not s:
            return ""
        return s.replace("_", "-")

    async def preflight(self, *, request, config: Dict[str, Any]) -> PreflightResult:
        qp = await self._ensure_query_profile(
            cache_key=self._qp_cache_key(
                request.query, bool(config.get("use_llm_intent", False))
            ),
            query=request.query,
            use_llm_intent=bool(config.get("use_llm_intent", False)),
            config=config,
        )

        self._apply_tone_policy(config, qp)

        decision_model = build_routing_decision(QueryProfile.model_validate(qp))
        decision = decision_model.model_dump()
        config["query_profile"] = qp
        config["routing_decision"] = decision

        # precedence: caller workflow -> gates -> registry
        self._apply_caller_workflow_override(request=request, config=config)

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

    def _apply_caller_workflow_override(self, *, request, config: Dict[str, Any]) -> None:
        requested_raw = (config.get("selected_workflow_id") or "").strip()
        if not requested_raw:
            return

        requested = self._normalize_workflow_slug(requested_raw)

        # Allow direct graph id
        if requested.startswith("graph_"):
            config["selected_graph"] = requested
            config["routing_source"] = "caller"
            config["routing_gates"] = {
                "bypassed": True,
                "reason": "caller_selected_graph",
            }
            config["resolved_workflow_id"] = requested
            return

        # ✅ load templates from YAML
        # NOTE: your WorkflowTemplateLoader currently supports .get() and .list();
        # we preserve that, but we ALSO try .get_templates() if it exists.
        templates_map = None
        if hasattr(self._templates, "get_templates"):
            try:
                templates_map = self._templates.get_templates()
            except Exception:
                templates_map = None

        if isinstance(templates_map, dict):
            known = sorted(list(templates_map.keys()))
            tpl = templates_map.get(requested)
            if tpl is None and requested_raw != requested:
                tpl = templates_map.get(requested_raw)
        else:
            # fallback to your existing loader interface
            known = sorted([t.workflow_id for t in self._templates.list()])
            tpl = self._templates.get(requested)
            if tpl is None and requested_raw != requested:
                tpl = self._templates.get(requested_raw)

        if tpl is None:
            raise ValueError(f"Unknown workflow_id '{requested_raw}'. Known: {known}")

        # ✅ apply template plan (graph selection)
        # support either attribute name: tpl.graph_id (new) or tpl.graph (your current)
        graph_id = getattr(tpl, "graph_id", None) or getattr(tpl, "graph", None)
        if graph_id:
            config["selected_graph"] = graph_id

        config["routing_source"] = "caller"
        config["routing_gates"] = {
            "bypassed": True,
            "reason": "caller_selected_workflow",
        }

        # ✅ guaranteed surfaced in response later
        config["resolved_workflow_id"] = getattr(tpl, "workflow_id", None) or requested
        config["resolved_workflow_version"] = getattr(tpl, "version", None)

        # optional: if you want preflight to also force an agent plan
        if getattr(tpl, "agents", None):
            config["agents"] = list(tpl.agents)

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
            config["routing_gates"] = {
                "intent_confidence_below_threshold": True,
                "min": min_conf,
                "got": intent_conf,
            }
            config["selected_graph"] = "graph_clarify"
            config["routing_source"] = "gate:intent_confidence"

    async def _ensure_query_profile(
        self, *, cache_key: str, query: str, use_llm_intent: bool, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        if cache_key in self._cache:
            config["query_profile"] = self._cache[cache_key]
            return self._cache[cache_key]

        async with self._lock(cache_key):
            if cache_key in self._cache:
                config["query_profile"] = self._cache[cache_key]
                return self._cache[cache_key]

            if use_llm_intent:
                qp = await self._llm_query_profile_best_effort(query)
            else:
                prof = analyze_query(query)
                qp = prof.model_dump(mode="json")
                qp.setdefault("signals", {})
                qp["signals"].setdefault("analysis_source", "rules")

            self._cache[cache_key] = qp
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
            data = sanitize_query_profile_dict(
                __import__("json").loads(extract_first_json_object(text))
            )
            prof = QueryProfile.model_validate(data)
            out = prof.model_dump(mode="json")
            out.setdefault("signals", {})
            out["signals"]["analysis_source"] = "llm"
            return out
        except Exception as e:
            logger.warning(
                "LLM query_profile failed; falling back to rules", extra={"error": str(e)}
            )
            prof = analyze_query(q)
            out = prof.model_dump(mode="json")
            out.setdefault("signals", {})
            out["signals"]["analysis_source"] = "rules_fallback"
            out["signals"]["llm_error"] = str(e)
            return out
