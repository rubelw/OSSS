from __future__ import annotations

from typing import Any, Dict, Optional
from dataclasses import dataclass

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
"""

async def classify_intent_llm(query: str) -> IntentResult:
    cfg = OpenAIConfig.load()
    llm = OpenAIChatLLM(
        api_key=cfg.api_key,
        model=cfg.model,
        base_url=cfg.base_url,
    )

    # You likely already have a structured/json mode helper; if not, do a simple parse.
    resp = await llm.ainvoke(
        [
            {"role": "system", "content": _INTENT_PROMPT},
            {"role": "user", "content": query},
        ]
    )

    # If your OpenAIChatLLM returns a string, parse JSON here.
    # Replace this with your existing "safe_json_loads" utility if you have one.
    import json
    data = json.loads(resp) if isinstance(resp, str) else resp

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
    return {
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
