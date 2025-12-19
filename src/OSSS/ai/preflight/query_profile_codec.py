# OSSS/ai/preflight/query_profile_codec.py
from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from OSSS.ai.analysis.rules.types import RuleHit


_ALLOWED_ACTIONS = {"read", "troubleshoot", "create", "review", "explain", "route"}

_ACTION_ALIASES = {
    "inform": "explain",
    "information": "explain",
    "answer": "explain",
    "respond": "explain",
    "debug": "troubleshoot",
    "diagnose": "troubleshoot",
    "fix": "troubleshoot",
    "research": "read",
    "lookup": "read",
    "search": "read",
    "plan": "route",
}

_TOP_LEVEL_ALIASES = {
    "intentConfidence": "intent_confidence",
    "subIntent": "sub_intent",
    "subIntentConfidence": "sub_intent_confidence",
    "sub_intentConfidence": "sub_intent_confidence",
    "toneConfidence": "tone_confidence",
    "matchedRules": "matched_rules",
}

_ALLOWED_TOP_KEYS = {
    "intent",
    "intent_confidence",
    "tone",
    "tone_confidence",
    "sub_intent",
    "sub_intent_confidence",
    "signals",
    "matched_rules",
}


def coerce_rule_hits(raw: Any) -> List[RuleHit]:
    hits: List[RuleHit] = []
    if not raw:
        return hits

    items = raw if isinstance(raw, list) else [raw]
    allowed_keys = set(RuleHit.model_fields.keys())

    for item in items:
        if isinstance(item, RuleHit):
            hits.append(item)
            continue

        if isinstance(item, dict):
            d: Dict[str, Any] = {k: v for k, v in item.items() if k in allowed_keys}

            if "rule" not in d:
                if "rule_id" in item and isinstance(item["rule_id"], str):
                    d["rule"] = item["rule_id"]
                elif "id" in item and isinstance(item["id"], str):
                    d["rule"] = item["id"]

            if "score" not in d:
                if "confidence" in item and isinstance(item["confidence"], (int, float)):
                    d["score"] = float(item["confidence"])

            hits.append(RuleHit.model_validate(d))
            continue

    return hits


def normalize_rule_hits(value: Any) -> List[Dict[str, Any]]:
    if not value:
        return []

    out: List[Dict[str, Any]] = []

    items = value if isinstance(value, list) else [value]
    for item in items:
        if isinstance(item, str) and item.strip():
            out.append({"rule": item.strip(), "action": "read"})
            continue

        if not isinstance(item, dict):
            continue

        rule = (
            item.get("rule")
            or item.get("rule_id")
            or item.get("id")
            or item.get("name")
            or item.get("label")
        )
        if not isinstance(rule, str) or not rule.strip():
            continue

        action = item.get("action") if isinstance(item.get("action"), str) else "read"
        action = action.strip().lower()
        action = _ACTION_ALIASES.get(action, action)
        if action not in _ALLOWED_ACTIONS:
            action = "read"

        hit: Dict[str, Any] = {"rule": rule.strip(), "action": action}

        if isinstance(item.get("category"), str):
            hit["category"] = item["category"]

        if isinstance(item.get("score"), (int, float)):
            hit["score"] = float(item["score"])
        elif isinstance(item.get("confidence"), (int, float)):
            hit["score"] = float(item["confidence"])

        meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
        for k in ("label", "tone", "sub_intent", "parent_intent"):
            if k in item and k not in meta:
                meta[k] = item[k]
        if meta:
            hit["meta"] = meta

        out.append(hit)

    return out


def sanitize_query_profile_dict(data: Any) -> Dict[str, Any]:
    if not isinstance(data, dict):
        return {}

    # rename aliases
    for src, dst in _TOP_LEVEL_ALIASES.items():
        if src in data and dst not in data:
            data[dst] = data.pop(src)

    # drop unknown top-level keys
    cleaned = {k: data[k] for k in list(data.keys()) if k in _ALLOWED_TOP_KEYS}

    def _as_str(v: Any, default: str) -> str:
        if isinstance(v, str) and v.strip():
            return v.strip()
        return default

    def _as_float(v: Any, default: float) -> float:
        try:
            if v is None:
                return default
            return float(v)
        except Exception:
            return default

    cleaned["intent"] = _as_str(cleaned.get("intent"), "general")
    cleaned["tone"] = _as_str(cleaned.get("tone"), "neutral")
    cleaned["sub_intent"] = _as_str(cleaned.get("sub_intent"), "general")

    # tone like "inquiry|neutral" -> "neutral"
    tone = cleaned["tone"]
    if "|" in tone:
        cleaned["tone"] = tone.split("|")[-1].strip() or "neutral"

    cleaned["intent_confidence"] = _as_float(cleaned.get("intent_confidence"), 0.50)
    cleaned["tone_confidence"] = _as_float(cleaned.get("tone_confidence"), 0.50)
    cleaned["sub_intent_confidence"] = _as_float(cleaned.get("sub_intent_confidence"), 0.50)

    if not isinstance(cleaned.get("signals"), dict):
        cleaned["signals"] = {}

    mr = normalize_rule_hits(cleaned.get("matched_rules"))
    hits = coerce_rule_hits(mr)
    cleaned["matched_rules"] = [h.model_dump() for h in hits]

    return cleaned


def coerce_llm_text(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw

    if isinstance(raw, dict):
        if "choices" in raw and isinstance(raw["choices"], list) and raw["choices"]:
            ch0 = raw["choices"][0]
            if isinstance(ch0, dict):
                msg = ch0.get("message")
                if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                    return msg["content"]
                if isinstance(ch0.get("text"), str):
                    return ch0["text"]

        if isinstance(raw.get("content"), str):
            return raw["content"]
        if isinstance(raw.get("text"), str):
            return raw["text"]

        return str(raw)

    for attr in ("content", "text"):
        v = getattr(raw, attr, None)
        if isinstance(v, str):
            return v

    return str(raw)


def extract_first_json_object(text: str) -> str:
    if not text:
        raise ValueError("empty LLM response")

    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        json.loads(text)
        return text
    except Exception:
        pass

    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        raise ValueError("no JSON object found in response")

    candidate = m.group(0)
    json.loads(candidate)  # validate
    return candidate
