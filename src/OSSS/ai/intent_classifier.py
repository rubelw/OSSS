# src/OSSS/ai/intent_classifier.py
from __future__ import annotations

from typing import Optional, Any
import httpx
import logging
import json

from OSSS.ai.intents.types import Intent, IntentResult
from OSSS.ai.intents.prompt import build_intent_system_prompt
from OSSS.ai.intents.heuristics import apply_heuristics, ALL_RULES

# ✅ single source of truth for aw_label = classified.intaliases
from OSSS.ai.agent_routing_config import build_alias_map

logger = logging.getLogger("OSSS.ai.intent_classifier")

# Build alias map once (same one router uses)
ALIAS_MAP: dict[str, str] = build_alias_map()

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


def _normalize_intent_label(raw: Any) -> str:
    """
    Normalize any raw intent string via the canonical alias map.
    """
    if not isinstance(raw, str):
        return "general"
    s = raw.strip()
    if not s:
        return "general"
    return ALIAS_MAP.get(s, s)


def _normalize_action(raw_action: Any) -> Optional[str]:
    if not isinstance(raw_action, str):
        return None
    action_norm = ACTION_ALIASES.get(raw_action.strip().lower(), raw_action.strip().lower())
    if action_norm not in ALLOWED_ACTIONS:
        return None
    return action_norm


def _intent_from_label(label: str) -> Intent:
    """
    Convert a normalized string label into the Intent enum safely.
    """
    try:
        return Intent(label)
    except Exception:
        return _general_intent()


async def classify_intent(text: str) -> IntentResult:
    base = getattr(settings, "VLLM_ENDPOINT", "http://host.containers.internal:11434").rstrip("/")
    chat_url = f"{base}/v1/chat/completions"
    model = getattr(settings, "INTENT_MODEL", "llama3.2-vision")

    logger.info("[intent_classifier] classifying text=%r", (text[:300] if isinstance(text, str) else text))
    logger.debug("[intent_classifier] endpoint=%s model=%s", chat_url, model)

    # --- 1) Heuristic fast-path --------------------------------------------
    # 1️⃣ Heuristic pass (fast, deterministic)
    heuristic_result = apply_heuristics(text, ALL_RULES)
    if heuristic_result is not None:
        rule = (heuristic_result.raw or {}).get("rule", {}) if hasattr(heuristic_result, "raw") else {}
        raw_label = rule.get("intent")

        # Fallback: if rule intent missing, try the enum value / string itself
        if not raw_label:
            try:
                raw_label = heuristic_result.intent.value  # type: ignore[attr-defined]
            except Exception:
                raw_label = str(getattr(heuristic_result, "intent", "general"))

        normalized_label = _normalize_intent_label(raw_label)
        normalized_intent = _intent_from_label(normalized_label)

        logger.info(
            "[intent_classifier] heuristic matched raw_intent=%r normalized=%r rule=%s",
            raw_label,
            normalized_label,
            rule.get("name"),
        )

        # ✅ Return a normalized copy (pydantic v2)
        try:
            return heuristic_result.model_copy(update={"intent": normalized_intent})
        except Exception:
            # pydantic v1 fallback
            return heuristic_result.copy(update={"intent": normalized_intent})

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
    raw_intent: Any = "general"
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

    # ✅ intent enum via canonical alias map (from agent_routing_config)
    normalized_label = _normalize_intent_label(raw_intent)
    intent = _intent_from_label(normalized_label)

    # action normalize (still local here)
    action_norm = _normalize_action(raw_action)

    bundle = {"source": "llm", "heuristic_rule": None, "text": text, "llm": obj}
    bundle_json = json.dumps(bundle, ensure_ascii=False)

    return IntentResult(
        intent=intent or "general",
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
