# OSSS/ai/preflight/preflight_service.py
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional
import ast
import json
from OSSS.ai.utils.json_debug import json_loads_debug
from OSSS.ai.utils.json_coerce import coerce_json_object  # or coerce_json

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

def _coerce_json_object(text: str) -> Dict[str, Any]:
    """
    Best-effort coercion:
      1) strict json.loads
      2) python literal dict via ast.literal_eval (handles single quotes)
    """
    t = (text or "").strip()
    if not t:
        raise ValueError("empty LLM response")

    # 1) strict JSON
    try:
        logger.debug(f"Attempting to parse JSON: {t[:1000]}")  # Log first 1000 characters of the input
        obj = json.loads(t)
        if isinstance(obj, dict):
            logger.debug(f"Successfully parsed JSON object: {obj}")
            return obj
        raise ValueError(f"expected JSON object, got {type(obj).__name__}")
    except Exception as e:
        logger.error(f"Failed to parse JSON (error: {e}): {t[:500]}")  # Log partial input if error occurs
        pass

    # 2) python-literal fallback (e.g. {'a': 1})
    try:
        logger.debug(f"Attempting to parse as Python literal: {t[:1000]}")
        obj = ast.literal_eval(t)
        if not isinstance(obj, dict):
            raise ValueError(f"expected object after literal_eval, got {type(obj).__name__}")
        logger.debug(f"Successfully parsed Python literal object: {obj}")
        return obj
    except Exception as e:
        logger.error(f"Failed to parse as Python literal (error: {e}): {t[:500]}")
        raise ValueError(f"not valid JSON or python-literal: {e}") from e

    if not isinstance(obj, dict):
        raise ValueError(f"expected object after literal_eval, got {type(obj).__name__}")

    return obj


def _parse_llm_json_best_effort(
    raw_text: str, *, label: str, correlation_id: Optional[str]
) -> Dict[str, Any]:
    """
    Logs with json_loads_debug and returns a dict.
    Tries raw first; then extracted-first-object.
    """
    raw_text = (raw_text or "").strip()
    if not raw_text:
        raise ValueError("empty LLM response")

    # Log the raw (even if it fails)
    try:
        logger.debug(f"Raw text for {label}: {raw_text[:1000]}")  # Log raw text up to 1000 characters

        json_loads_debug(raw_text, label=f"{label}:raw", correlation_id=correlation_id)
    except Exception:
        # keep going; debug logger already emitted details
        logger.error(f"Failed to parse raw JSON for {label}: {raw_text[:500]}")  # Log the partial raw text
        pass

    # Try parsing raw directly (works when model returns exactly the JSON object)
    try:
        return _coerce_json_object(raw_text)
    except Exception:
        pass

    # Otherwise extract the first {...} blob then parse again
    extracted = extract_first_json_object(raw_text)

    try:
        logger.debug(f"Extracted JSON for {label}: {extracted[:1000]}")  # Log extracted JSON
        json_loads_debug(extracted, label=f"{label}:extracted", correlation_id=correlation_id)
    except Exception:
        logger.error(f"Failed to parse extracted JSON for {label}: {extracted[:500]}")  # Log the partial extracted text
        pass

    return _coerce_json_object(extracted)


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
            self,
            *,
            cache_key: str,
            query: str,
            use_llm_intent: bool,
            config: Dict[str, Any],
    ) -> Dict[str, Any]:

        # ✅ Pull the request correlation_id from config ONCE here
        correlation_id = (config.get("correlation_id") or "").strip() or None

        if cache_key in self._cache:
            config["query_profile"] = self._cache[cache_key]
            return self._cache[cache_key]

        async with self._lock(cache_key):
            if cache_key in self._cache:
                config["query_profile"] = self._cache[cache_key]
                return self._cache[cache_key]

            if use_llm_intent:
                qp = await self._llm_query_profile_best_effort(
                    query,
                    correlation_id=correlation_id,
                )
            else:
                prof = analyze_query(query)
                qp = prof.model_dump(mode="json")
                qp.setdefault("signals", {})
                qp["signals"].setdefault("analysis_source", "rules")

            self._cache[cache_key] = qp
            config["query_profile"] = qp
            return qp

    async def _llm_query_profile_best_effort(
            self,
            query: str,
            correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        # ✅ Normalize at the top
        correlation_id = (correlation_id or "").strip() or None

        q = (query or "").strip()
        logger.debug(f"Received query for LLM profile: {q[:500]}")  # Log the first 500 characters of the query
        if not q:
            prof = QueryProfile()
            logger.debug("Empty query, returning default QueryProfile.")
            return prof.model_dump(mode="json")

        # Log configuration and setup
        cfg = OpenAIConfig.load()
        logger.debug(f"Loaded OpenAIConfig: {cfg.api_key[:5]}...")  # Log part of the API key for safety
        llm = OpenAIChatLLM(api_key=cfg.api_key, model=cfg.model, base_url=cfg.base_url)

        # Keep stable fallback ONLY if caller didn't provide one
        correlation_id = correlation_id or "preflight_query_profile"
        logger.debug(f"Using correlation_id: {correlation_id}")

        system = (
            "You are an intent/tone classifier for OSSS.\n"
            "Return ONLY a single valid JSON object. No markdown. No backticks. No extra text.\n"
            "Use double quotes for all keys and string values."
        )
        user = "... your JSON schema prompt ..."  # Include the user query schema (if applicable)

        # Log the system and user messages being sent to the LLM
        logger.debug(f"System prompt: {system[:500]}")  # Log first 500 chars of the system prompt
        logger.debug(f"User prompt: {user[:500]}")  # Log first 500 chars of the user prompt

        try:
            # Call the LLM
            logger.debug("Calling LLM with the provided prompts...")
            raw = await call_llm_text(
                llm,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.0,
                extra_json={"format": "json"},
            )

            logger.debug(f"Raw response from LLM: {raw[:500]}")  # Log part of the raw response
            text = coerce_llm_text(raw).strip()

            logger.debug(f"Processed LLM response text: {text[:500]}")  # Log the first 500 characters of processed text

            try:
                # Try to coerce the raw LLM response into a valid JSON object
                logger.debug(f"Attempting to parse LLM response as JSON...")
                data = coerce_json_object(text)  # ✅ handles {'a':1} and {"a":1}
                logger.debug(f"Successfully parsed LLM response: {data}")
            except Exception as e:
                # Log detailed error when LLM response is not valid JSON
                logger.error(
                    "LLM returned non-JSON",
                    extra={
                        "error": str(e),
                        "correlation_id": correlation_id,
                        "text": text[:500],  # Log part of the raw text that failed
                    },
                )
                raise

            # Sanitize and validate the parsed data
            logger.debug("Sanitizing the query profile data...")
            data = sanitize_query_profile_dict(data)

            # Validate the profile and log the result
            prof = QueryProfile.model_validate(data)
            out = prof.model_dump(mode="json")
            out.setdefault("signals", {})
            out["signals"]["analysis_source"] = "llm"
            logger.debug(f"Final query profile output: {out}")
            return out

        except Exception as e:
            # Log warning and fall back to rules-based analysis
            logger.warning(
                "LLM query_profile failed; falling back to rules",
                extra={
                    "error": str(e),
                    "correlation_id": correlation_id,  # ✅ helpful for log join
                },
            )
            prof = analyze_query(q)
            out = prof.model_dump(mode="json")
            out.setdefault("signals", {})
            out["signals"]["analysis_source"] = "rules_fallback"
            out["signals"]["llm_error"] = str(e)
            logger.debug(f"Rules fallback output: {out}")
            return out
