from __future__ import annotations

from typing import Any, Dict, Optional
from dataclasses import dataclass
import json

from OSSS.ai.config.openai_config import OpenAIConfig
from OSSS.ai.llm.openai import OpenAIChatLLM
from OSSS.ai.observability import get_logger

logger = get_logger(__name__)


@dataclass
class IntentResult:
    intent: str
    intent_confidence: float
    sub_intent: str
    sub_intent_confidence: float
    tone: str
    tone_confidence: float
    signals: Dict[str, Any]


_INTENT_PROMPT = """You are an intent classifier for a school software AI assistant.

Given a user query, return ONLY JSON with this schema:
{
  "intent": "general|search|explain|summarize|compare|debug|plan|write|code|operate",
  "intent_confidence": 0.0-1.0,
  "sub_intent": "short string",
  "sub_intent_confidence": 0.0-1.0,
  "tone": "neutral|urgent|curious|frustrated|formal|casual",
  "tone_confidence": 0.0-1.0,
  "signals": { "keywords": [...], "entities": [...], "domain": "..." }
}

Rules:
- Be conservative with confidence unless the intent is obvious.
- Keep sub_intent compact.
"""


async def classify_intent_llm(query: str) -> IntentResult:
    """
    Call LLM to classify user intent, with observability logging.
    """
    normalized_query = (query or "").strip()

    logger.debug(
        "Starting classify_intent_llm",
        extra={
            "event": "intent_classify_start",
            "query_length": len(normalized_query),
            "query_preview": normalized_query[:256],
        },
    )

    try:
        cfg = OpenAIConfig.load()
        logger.debug(
            "Loaded OpenAIConfig for intent classification",
            extra={
                "event": "intent_classify_config_loaded",
                "model": getattr(cfg, "model", None),
                "base_url": getattr(cfg, "base_url", None),
            },
        )
    except Exception as exc:
        logger.error(
            "Failed to load OpenAIConfig in classify_intent_llm",
            exc_info=True,
            extra={
                "event": "intent_classify_config_error",
                "error_type": type(exc).__name__,
            },
        )
        # Fail-safe: very low-confidence generic result
        fallback = IntentResult(
            intent="general",
            intent_confidence=0.0,
            sub_intent="unknown",
            sub_intent_confidence=0.0,
            tone="neutral",
            tone_confidence=0.0,
            signals={"error": "config_load_failed"},
        )
        logger.debug(
            "Returning fallback IntentResult after config load error",
            extra={
                "event": "intent_classify_fallback",
                "intent": fallback.intent,
                "sub_intent": fallback.sub_intent,
            },
        )
        return fallback

    try:
        llm = OpenAIChatLLM(
            api_key=cfg.api_key,
            model=cfg.model,
            base_url=cfg.base_url,
        )
        logger.debug(
            "Initialized OpenAIChatLLM for intent classification",
            extra={
                "event": "intent_classify_llm_init",
                "model": getattr(cfg, "model", None),
                "has_base_url": bool(getattr(cfg, "base_url", None)),
            },
        )
    except Exception as exc:
        logger.error(
            "Failed to init OpenAIChatLLM in classify_intent_llm",
            exc_info=True,
            extra={
                "event": "intent_classify_llm_init_error",
                "error_type": type(exc).__name__,
            },
        )
        fallback = IntentResult(
            intent="general",
            intent_confidence=0.0,
            sub_intent="unknown",
            sub_intent_confidence=0.0,
            tone="neutral",
            tone_confidence=0.0,
            signals={"error": "llm_init_failed"},
        )
        logger.debug(
            "Returning fallback IntentResult after LLM init error",
            extra={
                "event": "intent_classify_fallback",
                "intent": fallback.intent,
                "sub_intent": fallback.sub_intent,
            },
        )
        return fallback

    try:
        # You likely already have a structured/json mode helper; if not, do a simple parse.
        resp = await llm.ainvoke(
            [
                {"role": "system", "content": _INTENT_PROMPT},
                {"role": "user", "content": normalized_query},
            ]
        )
        logger.debug(
            "Received response from LLM for intent classification",
            extra={
                "event": "intent_classify_llm_response",
                "response_type": type(resp).__name__,
            },
        )
    except Exception as exc:
        logger.error(
            "LLM invocation failed in classify_intent_llm",
            exc_info=True,
            extra={
                "event": "intent_classify_llm_invoke_error",
                "error_type": type(exc).__name__,
            },
        )
        fallback = IntentResult(
            intent="general",
            intent_confidence=0.0,
            sub_intent="unknown",
            sub_intent_confidence=0.0,
            tone="neutral",
            tone_confidence=0.0,
            signals={"error": "llm_invoke_failed"},
        )
        logger.debug(
            "Returning fallback IntentResult after LLM invoke error",
            extra={
                "event": "intent_classify_fallback",
                "intent": fallback.intent,
                "sub_intent": fallback.sub_intent,
            },
        )
        return fallback

    try:
        # If your OpenAIChatLLM returns a string, parse JSON here.
        # Replace this with your existing "safe_json_loads" utility if you have one.
        data = json.loads(resp) if isinstance(resp, str) else resp

        logger.debug(
            "Parsed LLM response into intent data",
            extra={
                "event": "intent_classify_parse_success",
                "keys": list(data.keys()) if isinstance(data, dict) else None,
            },
        )
    except Exception as exc:
        logger.error(
            "Failed to parse LLM response as JSON in classify_intent_llm",
            exc_info=True,
            extra={
                "event": "intent_classify_parse_error",
                "response_type": type(resp).__name__,
            },
        )
        # Fall back to generic intent with low confidence but preserve raw response
        fallback = IntentResult(
            intent="general",
            intent_confidence=0.0,
            sub_intent="unknown",
            sub_intent_confidence=0.0,
            tone="neutral",
            tone_confidence=0.0,
            signals={"raw_response": resp},
        )
        logger.debug(
            "Returning fallback IntentResult after parse error",
            extra={
                "event": "intent_classify_fallback",
                "intent": fallback.intent,
                "sub_intent": fallback.sub_intent,
            },
        )
        return fallback

    # Normal path: construct IntentResult
    result = IntentResult(
        intent=str(data.get("intent", "general")),
        intent_confidence=float(data.get("intent_confidence", 0.5)),
        sub_intent=str(data.get("sub_intent", "general")),
        sub_intent_confidence=float(data.get("sub_intent_confidence", 0.5)),
        tone=str(data.get("tone", "neutral")),
        tone_confidence=float(data.get("tone_confidence", 0.5)),
        signals=dict(data.get("signals") or {}),
    )

    logger.debug(
        "classify_intent_llm completed",
        extra={
            "event": "intent_classify_complete",
            "intent": result.intent,
            "intent_confidence": result.intent_confidence,
            "sub_intent": result.sub_intent,
            "sub_intent_confidence": result.sub_intent_confidence,
            "tone": result.tone,
            "tone_confidence": result.tone_confidence,
            # Avoid logging full signals; just presence + a few keys
            "has_signals": bool(result.signals),
            "signal_keys": list(result.signals.keys())[:10],
        },
    )

    return result


def to_query_profile(result: IntentResult) -> Dict[str, Any]:
    profile = {
        "intent": result.intent,
        "intent_confidence": result.intent_confidence,
        "sub_intent": result.sub_intent,
        "sub_intent_confidence": result.sub_intent_confidence,
        "tone": result.tone,
        "tone_confidence": result.tone_confidence,
        "signals": result.signals,
        "matched_rules": [],
        "analysis_source": "llm",
    }

    logger.debug(
        "Converted IntentResult to query_profile",
        extra={
            "event": "intent_to_query_profile",
            "intent": result.intent,
            "intent_confidence": result.intent_confidence,
            "sub_intent": result.sub_intent,
            "tone": result.tone,
            "has_signals": bool(result.signals),
        },
    )

    return profile
