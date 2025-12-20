# OSSS/ai/orchestration/intent_classifier.py
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict

from OSSS.ai.config.openai_config import OpenAIConfig
from OSSS.ai.llm.openai import OpenAIChatLLM
from OSSS.ai.utils.json_debug import json_loads_debug


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
- Return a single JSON object. Do not wrap in markdown. Do not include backticks.
- Use double quotes for all keys and string values.
""".strip()


def _safe_preview(text: str, *, limit: int = 500) -> str:
    if not text:
        return ""
    t = text.strip().replace("\n", "\\n")
    return t[:limit]


def _safe_intent_result(reason: str) -> IntentResult:
    return IntentResult(
        intent="general",
        intent_confidence=0.5,
        sub_intent="general",
        sub_intent_confidence=0.5,
        tone="neutral",
        tone_confidence=0.5,
        signals={"analysis_source": reason},
    )


def _looks_like_policy_refusal(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    # keep this broad; you just need to know "not JSON because refusal"
    return (
        "i can't provide a response" in t
        or "self-harm" in t
        or "suicide" in t
        or "crisis hotline" in t
        or "seek help" in t
    )

import ast
import json
from typing import Any, Dict

def _coerce_json_object(text: str) -> Dict[str, Any]:
    """
    Best-effort coercion:
      1) strict json.loads
      2) python literal dict via ast.literal_eval (handles single quotes)
    """
    t = (text or "").strip()
    if not t:
        raise ValueError("empty response")

    # 1) strict JSON
    try:
        obj = json.loads(t)
        if isinstance(obj, dict):
            return obj
        raise ValueError(f"expected JSON object, got {type(obj).__name__}")
    except Exception:
        pass

    # 2) python-literal fallback (e.g. {'a': 1})
    try:
        obj = ast.literal_eval(t)
    except Exception as e:
        raise ValueError(f"not valid JSON or python-literal: {e}") from e

    if not isinstance(obj, dict):
        raise ValueError(f"expected object after literal_eval, got {type(obj).__name__}")
    return obj


def _coerce_llm_text(resp: Any) -> str:
    """
    Normalize different LLM client return types into plain text.
    Supports:
      - plain strings
      - objects with .text
      - objects with .content (string or list of chunks)
    """
    if resp is None:
        return ""
    if isinstance(resp, str):
        return resp

    text = getattr(resp, "text", None)
    if isinstance(text, str):
        return text

    content = getattr(resp, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # common patterns: [{"type":"text","text":"..."}, ...]
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                t = item.get("text") or item.get("content")
                if isinstance(t, str):
                    parts.append(t)
        return "\n".join(parts)

    return str(resp)


def _extract_first_json_object(text: str) -> str:
    if not text:
        raise ValueError("empty LLM response")
    t = text.strip()
    # strip accidental code fences
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)

    # if it's already valid JSON, use it
    try:
        json.loads(t)
        return t
    except Exception:
        pass

    # otherwise, grab the first {...} blob
    m = re.search(r"\{.*\}", t, flags=re.DOTALL)
    if not m:
        raise ValueError("no JSON object found in LLM response")

    candidate = m.group(0).strip()
    # validate JSON
    json.loads(candidate)
    return candidate


async def classify_intent_llm_safe(query: str) -> IntentResult:
    """
    Backwards-compatible wrapper used by older graphs/nodes.
    Never raises; always returns a usable IntentResult.
    """
    q = (query or "").strip()
    if not q:
        return IntentResult(
            intent="general",
            intent_confidence=0.5,
            sub_intent="general",
            sub_intent_confidence=0.5,
            tone="neutral",
            tone_confidence=0.5,
            signals={"analysis_source": "rules_fallback", "empty_query": True},
        )

    try:
        r = await classify_intent_llm(q)
        # guarantee dict signals
        r.signals = dict(r.signals or {})
        r.signals.setdefault("analysis_source", "llm")
        return r
    except Exception as e:
        return IntentResult(
            intent="general",
            intent_confidence=0.5,
            sub_intent="general",
            sub_intent_confidence=0.5,
            tone="neutral",
            tone_confidence=0.5,
            signals={"analysis_source": "llm_fallback", "error": str(e)},
        )


async def classify_intent_llm(query: str) -> IntentResult:
    cfg = OpenAIConfig.load()
    llm = OpenAIChatLLM(
        api_key=cfg.api_key,
        model=cfg.model,
        base_url=cfg.base_url,
    )

    resp = await llm.ainvoke(
        [
            {"role": "system", "content": _INTENT_PROMPT},
            {"role": "user", "content": (query or "").strip()},
        ],
        response_format={"type": "json_object"},
        extra_json={"format": "json"},
        temperature=0.0,
    )

    correlation_id = "intent_classifier"  # better: thread through from orchestrator
    raw_text = _coerce_llm_text(resp).strip()

    if _looks_like_policy_refusal(raw_text):
        return _safe_intent_result("llm_refusal")

    # Try raw parse first; if that fails, try extracted blob
    try:
        json_loads_debug(
            raw_text,
            label="intent_classifier:raw_text",
            correlation_id=correlation_id,
        )
        data = _coerce_json_object(raw_text)
    except Exception:
        json_text = _extract_first_json_object(raw_text)
        json_loads_debug(
            json_text,
            label="intent_classifier:extracted_json",
            correlation_id=correlation_id,
        )
        data = _coerce_json_object(json_text)

    return IntentResult(
        intent=str(data.get("intent", "general")),
        intent_confidence=float(data.get("intent_confidence", 0.5)),
        sub_intent=str(data.get("sub_intent", "general")),
        sub_intent_confidence=float(data.get("sub_intent_confidence", 0.5)),
        tone=str(data.get("tone", "neutral")),
        tone_confidence=float(data.get("tone_confidence", 0.5)),
        signals=dict(data.get("signals") or {}),
    )


def to_query_profile(result: IntentResult) -> Dict[str, Any]:
    # NOTE: in your other code, QueryProfile expects "analysis_source" in signals,
    # not as a top-level field. Keep this consistent.
    signals = dict(result.signals or {})
    signals.setdefault("analysis_source", "llm")

    return {
        "intent": result.intent,
        "intent_confidence": result.intent_confidence,
        "sub_intent": result.sub_intent,
        "sub_intent_confidence": result.sub_intent_confidence,
        "tone": result.tone,
        "tone_confidence": result.tone_confidence,
        "signals": signals,
        "matched_rules": [],
    }
