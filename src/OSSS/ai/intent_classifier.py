# src/OSSS/ai/intent_classifier.py
from __future__ import annotations

from typing import Optional, Any, Dict, List
import httpx
import logging
import json
import re
from pydantic import BaseModel

from OSSS.ai.intents.types import Intent, IntentResult
from OSSS.ai.intents.registry import INTENT_ALIASES
from OSSS.ai.intents.prompt import build_intent_system_prompt
from OSSS.ai.intents.heuristics import apply_heuristics

logger = logging.getLogger("OSSS.ai.intent_classifier")

# --- Action aliasing -------------------------------------------------------

# Allow the classifier to keep "show_withdrawn_students" as a first-class action.
ACTION_ALIASES: dict[str, str] = {
    "show_withdrawn_students": "show_withdrawn_students",
    # or map it to "read" if you don't want a special downstream action:
    # "show_withdrawn_students": "read",
}

ALLOWED_ACTIONS = {"read", "create", "update", "delete", "show_withdrawn_students"}

# --- SAFE SETTINGS IMPORT (same pattern as rag_router) ---------------------
try:
    from OSSS.config import settings as _settings  # type: ignore

    settings = _settings
except Exception:
    # Fallback for local/dev or tests
    class _Settings:
        VLLM_ENDPOINT: str = "http://host.containers.internal:11434"
        INTENT_MODEL: str = "llama3.2-vision"

    settings = _Settings()  # type: ignore


def _general_intent() -> Intent:
    """Return the 'general' intent in a tolerant way."""
    if hasattr(Intent, "GENERAL"):
        return getattr(Intent, "GENERAL")
    # fallback if enum doesn’t define GENERAL constant but has value "general"
    try:
        return Intent("general")
    except Exception:
        # last resort: first enum member
        return list(Intent)[0]


# ---------------------------------------------------------------------------
# Heuristic rule model + table (scalable for many patterns)
# ---------------------------------------------------------------------------

class IntentHeuristicRule(BaseModel):
    """
    A simple, config-like rule for matching text to an intent without
    calling the LLM.

    - If any `contains_any` keyword is found (case-insensitive), the rule matches.
    - If `regex` is provided and matches, the rule matches.
    - If either condition matches, the rule fires.
    """
    name: str

    # matching
    contains_any: List[str] = []
    regex: Optional[str] = None

    # what intent/action to return
    intent: str
    action: Optional[str] = "read"
    urgency: Optional[str] = "low"
    tone_major: Optional[str] = "informal_casual"
    tone_minor: Optional[str] = "friendly"

    # optional extra metadata if you ever want to propagate it later
    metadata: Dict[str, Any] = {}


HEURISTIC_RULES: List[IntentHeuristicRule] = [
    IntentHeuristicRule(
        name="student_info_withdrawn",
        contains_any=[
            "withdrawn students",
            "withdrawn student",
            "show withdrawn students",
            "inactive students",
            "unenrolled students",
            "not enrolled students",
        ],
        intent="student_info",
        action="show_withdrawn_students",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="friendly",
        metadata={"mode": "student_info", "enrolled_only": False},
    ),
    IntentHeuristicRule(
        name="student_info_generic",
        contains_any=[
            "student info",
            "show student info",
            "show students",
            "students list",
            "list students",
            "query student information",
            "query student info",
            "show male students",
            "show female students",
            "list male students",
            "list female students",
            "query male students",
            "query female students",
            "last name beginning with",
            "last name starting with",
            "grade level",
            "third grade",
            "grade third",
        ],
        intent="student_info",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="friendly",
        metadata={"mode": "student_info"},
    ),
]

TABLES: List[str] = []

# Auto-extend HEURISTIC_RULES
for table in TABLES:
    HEURISTIC_RULES.append(
        IntentHeuristicRule(
            name=f"{table}_query_rule",
            contains_any=[
                table,
                f"show {table}",
                f"{table} query",
            ],
            intent="query_data",
            action="read",
            urgency="low",
            tone_major="informal_casual",
            tone_minor="friendly",
            metadata={"mode": table},
        )
    )


async def classify_intent(text: str) -> IntentResult:
    """
    Classify text into:
      - intent (Intent)
      - action (CRUD + optional custom actions)
      - urgency
      - tone_major / tone_minor

    Heuristics are applied first; if any rule matches, we skip the LLM.

    Uses the intent registry prompt builder from OSSS.ai.intents.prompt.
    """
    base = getattr(settings, "VLLM_ENDPOINT", "http://host.containers.internal:11434").rstrip("/")
    chat_url = f"{base}/v1/chat/completions"
    model = getattr(settings, "INTENT_MODEL", "llama3.2-vision")

    logger.info("[intent_classifier] classifying text=%r", text[:300] if isinstance(text, str) else text)
    logger.debug("[intent_classifier] endpoint=%s model=%s", chat_url, model)

    # --- 1) Heuristic fast-path --------------------------------------------
    heuristic_result = apply_heuristics(text)
    if heuristic_result is not None:
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
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": 0.0,
                    "stream": False,
                },
            )
            logger.info("[intent_classifier] upstream_v1 status=%s bytes=%s", resp.status_code, len(resp.content))
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        logger.error(
            "[intent_classifier] HTTP error when calling %s: %s (falling back to general intent)",
            chat_url,
            e,
        )
        fallback_intent = _general_intent()
        bundle = {
            "source": "fallback",
            "heuristic_rule": None,
            "text": text,
            "llm": {"error": str(e), "endpoint": chat_url},
        }
        bundle_json = json.dumps(bundle, ensure_ascii=False)
        return IntentResult(
            intent=fallback_intent,
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

    # ---- Extract raw content ----------------------------------------------
    content = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )
    logger.debug("[intent_classifier] raw model content: %r", content[-500:] if isinstance(content, str) else content)

    # ---- Parse JSON --------------------------------------------------------
    obj: Optional[dict] = None
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

            logger.info(
                "[intent_classifier] parsed JSON raw_intent=%r confidence=%r raw_action=%r raw_urgency=%r raw_tone_major=%r raw_tone_minor=%r",
                raw_intent,
                confidence,
                raw_action,
                raw_urgency,
                raw_tone_major,
                raw_tone_minor,
            )
        except Exception as e:
            logger.warning(
                "[intent_classifier] JSON parse failed for content prefix=%r error=%s (fallback general)",
                content[:120],
                e,
            )
            obj = None
            raw_intent = "general"
    else:
        logger.info("[intent_classifier] model returned non-JSON content, falling back to general")

    # ---- Map string -> Intent enum (using registry aliases) ----------------
    try:
        raw_intent_aliased = INTENT_ALIASES.get(raw_intent, raw_intent)
        intent = Intent(raw_intent_aliased)
    except Exception as e:
        logger.warning("[intent_classifier] unknown intent %r -> general (%s)", raw_intent, e)
        intent = _general_intent()

    # ---- Normalize action --------------------------------------------------
    action_norm: Optional[str]
    if isinstance(raw_action, str):
        action_norm = raw_action.lower().strip()
        action_norm = ACTION_ALIASES.get(action_norm, action_norm)
        if action_norm not in ALLOWED_ACTIONS:
            logger.warning("[intent_classifier] unknown action %r -> None", raw_action)
            action_norm = None
    else:
        action_norm = None

    # ---- Normalize urgency -------------------------------------------------
    urgency_norm: Optional[str]
    if isinstance(raw_urgency, str):
        urgency_norm = raw_urgency.lower().strip()
        if urgency_norm not in {"low", "medium", "high"}:
            logger.warning("[intent_classifier] unknown urgency %r -> None", raw_urgency)
            urgency_norm = None
    else:
        urgency_norm = None

    # ---- Normalize tones ---------------------------------------------------
    valid_tone_major = {
        "formal",
        "formal_professional",
        "informal_casual",
        "emotional_attitude",
        "action_persuasive",
        "other",
    }
    if isinstance(raw_tone_major, str):
        tone_major_norm = raw_tone_major.lower().strip()
        if tone_major_norm not in valid_tone_major:
            logger.warning("[intent_classifier] unknown tone_major %r -> None", raw_tone_major)
            tone_major_norm = None
    else:
        tone_major_norm = None

    valid_tone_minor = {
        "formal",
        "objective",
        "authoritative",
        "respectful",
        "informal",
        "casual",
        "friendly",
        "enthusiastic",
        "humorous",
        "optimistic",
        "pessimistic",
        "serious",
        "empathetic_compassionate",
        "assertive",
        "sarcastic",
        "persuasive",
        "encouraging",
        "didactic",
        "curious",
        "candid",
        "apologetic",
        "dramatic",
        "concerned",
        "helpful",
    }
    if isinstance(raw_tone_minor, str):
        tone_minor_norm = raw_tone_minor.lower().strip()
        if tone_minor_norm not in valid_tone_minor:
            logger.warning("[intent_classifier] unknown tone_minor %r -> None", raw_tone_minor)
            tone_minor_norm = None
    else:
        tone_minor_norm = None

    logger.info(
        "[intent_classifier] final intent=%s confidence=%r action=%r urgency=%r tone_major=%r tone_minor=%r",
        getattr(intent, "value", str(intent)),
        confidence,
        action_norm,
        urgency_norm,
        tone_major_norm,
        tone_minor_norm,
    )

    # Bundle for raw_model_output (LLM path)
    bundle = {
        "source": "llm",
        "heuristic_rule": None,
        "text": text,
        "llm": obj,  # parsed JSON if available
    }
    bundle_json = json.dumps(bundle, ensure_ascii=False)

    return IntentResult(
        intent=intent,
        confidence=confidence,
        raw=obj or data,
        action=action_norm,
        action_confidence=action_confidence,
        urgency=urgency_norm,
        urgency_confidence=urgency_confidence,
        tone_major=tone_major_norm,
        tone_major_confidence=tone_major_confidence,
        tone_minor=tone_minor_norm,
        tone_minor_confidence=tone_minor_confidence,
        raw_model_content=content,       # verbatim model text (if any)
        raw_model_output=bundle_json,    # structured bundle
        source="llm",
    )
