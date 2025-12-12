# src/OSSS/ai/intent_classifier.py
from __future__ import annotations

from typing import Optional, Any
import httpx
import logging
import json

from OSSS.ai.intents.types import Intent, IntentResult
from OSSS.ai.intents.registry import INTENT_ALIASES
from OSSS.ai.intents.prompt import build_intent_system_prompt
from OSSS.ai.intents.heuristics.apply import apply_heuristics, HeuristicRule

logger = logging.getLogger("OSSS.ai.intent_classifier")

ACTION_ALIASES: dict[str, str] = {
    "show_withdrawn_students": "show_withdrawn_students",
}
ALLOWED_ACTIONS = {"read", "create", "update", "delete", "show_withdrawn_students"}

try:
    from OSSS.config import settings as _settings  # type: ignore
    settings = _settings
except Exception:
    class _Settings:
        VLLM_ENDPOINT: str = "http://host.containers.internal:11434"
        INTENT_MODEL: str = "llama3.2-vision"
    settings = _Settings()  # type: ignore


def _general_intent() -> Intent:
    if hasattr(Intent, "GENERAL"):
        return getattr(Intent, "GENERAL")
    try:
        return Intent("general")
    except Exception:
        return list(Intent)[0]


async def classify_intent(text: str) -> IntentResult:
    base = getattr(settings, "VLLM_ENDPOINT", "http://host.containers.internal:11434").rstrip("/")
    chat_url = f"{base}/v1/chat/completions"
    model = getattr(settings, "INTENT_MODEL", "llama3.2-vision")

    logger.info("[intent_classifier] classifying text=%r", (text[:300] if isinstance(text, str) else text))
    logger.debug("[intent_classifier] endpoint=%s model=%s", chat_url, model)

    # --- 1) Heuristic fast-path --------------------------------------------
    heuristic_result = apply_heuristics(text)
    if heuristic_result is not None:
        logger.info(
            "[intent_classifier] heuristic hit intent=%s action=%s",
            getattr(heuristic_result.intent, "value", heuristic_result.intent),
            getattr(heuristic_result, "action", None),
        )

        return heuristic_result

    # --- 2) System prompt from intent registry -----------------------------
    system = build_intent_system_prompt()
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": text},
    ]

    # ---- Call upstream LLM -------------------------------------------------
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                chat_url,
                json={"model": model, "messages": messages, "temperature": 0.0, "stream": False},
            )
            logger.info("[intent_classifier] upstream_v1 status=%s bytes=%s", resp.status_code, len(resp.content))
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        logger.error("[intent_classifier] HTTP error calling %s: %s (fallback general)", chat_url, e)
        bundle = {
            "source": "fallback",
            "heuristic_rule": None,
            "text": text,
            "llm": {"error": str(e), "endpoint": chat_url},
        }
        bundle_json = json.dumps(bundle, ensure_ascii=False)
        return IntentResult(
            intent=_general_intent(),
            confidence=None,
            raw={"error": str(e)},
            action=None,
            action_confidence=None,
            urgency=None,
            urgency_confidence=None,
            tone_major=None,
            tone_major_confidence=None,
            tone_minor=None,
            tone_minor_confidence=None,
            raw_model_content=None,
            raw_model_output=bundle_json,
            source="fallback",
        )

    content = (data.get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip()

    obj: Optional[dict[str, Any]] = None
    raw_intent = "general"
    confidence: Optional[float] = None
    raw_action: Optional[str] = None
    action_confidence: Optional[float] = None
    raw_urgency: Optional[str] = None
    urgency_confidence: Optional[float] = None
    raw_tone_major: Optional[str] = None
    tone_major_confidence: Optional[float] = None
    raw_tone_minor: Optional[str] = None
    tone_minor_confidence: Optional[float] = None

    if isinstance(content, str) and content.lstrip().startswith("{"):
        try:
            obj = json.loads(content)
            raw_intent = obj.get("intent", "general")
            confidence = obj.get("confidence")
            raw_action = obj.get("action")
            action_confidence = obj.get("action_confidence")
            raw_urgency = obj.get("urgency")
            urgency_confidence = obj.get("urgency_confidence")
            raw_tone_major = obj.get("tone_major")
            tone_major_confidence = obj.get("tone_major_confidence")
            raw_tone_minor = obj.get("tone_minor")
            tone_minor_confidence = obj.get("tone_minor_confidence")
        except Exception as e:
            logger.warning("[intent_classifier] JSON parse failed: %s (fallback general)", e)
            obj = None
            raw_intent = "general"

    # intent enum via aliases
    try:
        raw_intent_aliased = INTENT_ALIASES.get(raw_intent, raw_intent)
        intent = Intent(raw_intent_aliased)
    except Exception:
        intent = _general_intent()

    # action normalize
    action_norm: Optional[str]
    if isinstance(raw_action, str):
        action_norm = ACTION_ALIASES.get(raw_action.strip().lower(), raw_action.strip().lower())
        if action_norm not in ALLOWED_ACTIONS:
            action_norm = None
    else:
        action_norm = None

    bundle = {"source": "llm", "heuristic_rule": None, "text": text, "llm": obj}
    bundle_json = json.dumps(bundle, ensure_ascii=False)

    return IntentResult(
        intent=intent,
        confidence=confidence,
        raw=obj or data,
        action=action_norm,
        action_confidence=action_confidence,
        urgency=(raw_urgency.lower().strip() if isinstance(raw_urgency, str) else None),
        urgency_confidence=urgency_confidence,
        tone_major=(raw_tone_major.lower().strip() if isinstance(raw_tone_major, str) else None),
        tone_major_confidence=tone_major_confidence,
        tone_minor=(raw_tone_minor.lower().strip() if isinstance(raw_tone_minor, str) else None),
        tone_minor_confidence=tone_minor_confidence,
        raw_model_content=content,
        raw_model_output=bundle_json,
        source="llm",
    )
