# OSSS/ai/orchestration/intent_classifier.py
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict

from OSSS.ai.config.openai_config import OpenAIConfig
from OSSS.ai.llm.openai import OpenAIChatLLM


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
""".strip()

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

    candidate = m.group(0)
    json.loads(candidate)  # validate
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
        # If your OpenAIChatLLM supports these, they help a lot:
        response_format={"type": "json_object"},
        temperature=0.0,
    )

    text = _coerce_llm_text(resp)

    # Optional: if the model refused, don't try JSON parsing
    if _looks_like_policy_refusal(text):
        return _safe_intent_result("llm_refusal")

    json_text = _extract_first_json_object(text)
    data = json.loads(json_text)

    # data is guaranteed dict-ish now
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
