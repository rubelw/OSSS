# OSSS/ai/analysis/llm_analyzer.py
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional, List

from pydantic import ValidationError

from OSSS.ai.analysis.models import QueryProfile
from OSSS.ai.analysis.rules.types import RuleAction, RuleCategory, make_hit
from OSSS.ai.analysis.pipeline import analyze_query  # deterministic fallback

from OSSS.ai.llm.openai import OpenAIChatLLM
from OSSS.ai.config.openai_config import OpenAIConfig


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_CLASSIFIER_SYSTEM_PROMPT = """\
You are an AI query classification engine for OSSS.

Return ONLY a single valid JSON object and nothing else.
No markdown. No commentary. No code fences.
""".strip()

# Keep your richer schema prompt. We'll fold extra keys into signals safely.
_CLASSIFIER_USER_TEMPLATE = """\
Analyze the following user query and classify it.

Return a JSON object with the following fields:

- intent: one of
  ["read", "write", "update", "delete", "analyze", "summarize", "compare", "list", "explain", "general"]

- intent_confidence: number between 0.0 and 1.0

- sub_intent: short snake_case string describing the specific goal
  (examples: "data_query", "policy_lookup", "entity_listing", "record_update", "freeform_qa")

- sub_intent_confidence: number between 0.0 and 1.0

- tone: one of
  ["neutral", "question", "instruction", "command", "exploratory"]

- tone_confidence: number between 0.0 and 1.0

- complexity: one of
  ["low", "medium", "high"]

- safety: one of
  ["safe_read_only", "requires_confirmation", "restricted"]

- requires_tools: boolean

- signals: object containing any helpful flags

- matched_rules: array of objects with:
  - rule_id: string
  - action: one of ["read", "write", "block"]
  - confidence: number between 0.0 and 1.0

If information is unclear, make a best-effort guess and lower confidence scores.

User query:
\"\"\"{query}\"\"\"
""".strip()


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

_ALLOWED_ACTIONS = {"read", "write", "update", "delete", "block"}

_ACTION_ALIASES = {
    # Read-like
    "inform": "read",
    "answer": "read",
    "respond": "read",
    "research": "read",
    "lookup": "read",
    "search": "read",
    "analyze": "read",
    "summarize": "read",
    "explain": "read",
    "list": "read",
    "compare": "read",
    "general": "read",

    # Write-like
    "create": "write",
    "insert": "write",
    "add": "write",
    "new": "write",

    # Update-like
    "modify": "update",
    "change": "update",
    "edit": "update",
    "fix": "update",
    "correct": "update",
    "patch": "update",

    # Delete-like
    "remove": "delete",
    "erase": "delete",
    "destroy": "delete",

    # “block” from older schemas → safest default (no destructive action)
    "block": "read",
    "deny": "read",
}

_ALLOWED_TONE = {"neutral", "question", "instruction", "command", "exploratory"}
_ALLOWED_COMPLEXITY = {"low", "medium", "high"}
_ALLOWED_SAFETY = {"safe_read_only", "requires_confirmation", "restricted"}

def _coerce_llm_text(raw: Any) -> str:
    """
    Normalize common LLM client return shapes into plain assistant text.
    Supports:
      - plain string
      - OpenAI-style dict: {"choices":[{"message":{"content":"..."}}]}
      - {"content": "..."} or {"text": "..."}
      - objects with .content / .text
      - objects with model_dump()/dict()
    """
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

    if hasattr(raw, "model_dump"):
        try:
            return _coerce_llm_text(raw.model_dump())
        except Exception:
            pass

    if hasattr(raw, "dict"):
        try:
            return _coerce_llm_text(raw.dict())
        except Exception:
            pass

    for attr in ("text", "content"):
        v = getattr(raw, attr, None)
        if isinstance(v, str):
            return v

    return str(raw)

def normalize_action(action: Any) -> str:
    if not isinstance(action, str) or not action.strip():
        return "read"
    a = action.strip().lower()
    if a in _ALLOWED_ACTIONS:
        return a
    return _ACTION_ALIASES.get(a, "read")


def _extract_first_json_object(text: str) -> str:
    if not text:
        raise ValueError("empty LLM response")
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)

    try:
        json.loads(t)
        return t
    except Exception:
        pass

    m = re.search(r"\{.*\}", t, flags=re.DOTALL)
    if not m:
        raise ValueError("no JSON object found")
    candidate = m.group(0)
    json.loads(candidate)
    return candidate


def _as_float(v: Any, default: float) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _as_str(v: Any, default: str) -> str:
    return v.strip() if isinstance(v, str) and v.strip() else default


def _normalize_rule_hits_llm(value: Any) -> List[Dict[str, Any]]:
    """
    Convert LLM rule hits into something RuleHit can validate.
    We produce a conservative superset, then do a 2-pass validate below.
    """
    if not value:
        return []

    out: List[Dict[str, Any]] = []
    if not isinstance(value, list):
        return out

    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(
                {
                    "rule_id": item.strip(),
                    "action": "read",
                    "confidence": 0.5,
                }
            )
            continue

        if not isinstance(item, dict):
            continue

        rule_id = (
            item.get("rule_id")
            or item.get("rule")
            or item.get("id")
            or item.get("name")
        )
        if not isinstance(rule_id, str) or not rule_id.strip():
            continue

        action = normalize_action(item.get("action"))
        conf = item.get("confidence", item.get("score", 0.5))
        conf_f = _as_float(conf, 0.5)
        if conf_f < 0.0:
            conf_f = 0.0
        if conf_f > 1.0:
            conf_f = 1.0

        out.append(
            {
                "rule_id": rule_id.strip(),
                "action": action,
                "confidence": conf_f,
            }
        )

    return out


def _sanitize_to_query_profile_dict(data: Any) -> Dict[str, Any]:
    """
    Build a dict that matches QueryProfile exactly:
      intent, intent_confidence, tone, tone_confidence,
      sub_intent, sub_intent_confidence, signals, matched_rules
    Everything else is folded into signals.
    """
    if not isinstance(data, dict):
        data = {}

    signals: Dict[str, Any] = {}
    if isinstance(data.get("signals"), dict):
        signals.update(data["signals"])

    # Fold “extra” fields into signals (so QueryProfile extra=forbid never trips)
    # Keep them namespaced to avoid collisions.
    if "action" in data:
        signals.setdefault("llm_action", normalize_action(data.get("action")))
    if "complexity" in data:
        c = _as_str(data.get("complexity"), "")
        if c.lower() in _ALLOWED_COMPLEXITY:
            signals.setdefault("complexity", c.lower())
    if "safety" in data:
        s = _as_str(data.get("safety"), "")
        if s.lower() in _ALLOWED_SAFETY:
            signals.setdefault("safety", s.lower())
    if "requires_tools" in data:
        signals.setdefault("requires_tools", bool(data.get("requires_tools")))

    # Allow LLM “intent” to be richer but keep QueryProfile intent as-is (string)
    intent_raw = _as_str(data.get("intent"), "general")
    tone_raw = _as_str(data.get("tone"), "neutral")
    sub_intent_raw = _as_str(data.get("sub_intent"), "general")

    # Normalize tone to allowed set (keep neutral if unknown)
    tone = tone_raw.lower()
    if tone not in _ALLOWED_TONE:
        tone = "neutral"

    # Normalize matched rules + actions
    mr = _normalize_rule_hits_llm(data.get("matched_rules"))

    return {
        "intent": intent_raw,
        "intent_confidence": _as_float(data.get("intent_confidence"), 0.5),
        "tone": tone,
        "tone_confidence": _as_float(data.get("tone_confidence"), 0.5),
        "sub_intent": sub_intent_raw,
        "sub_intent_confidence": _as_float(data.get("sub_intent_confidence"), 0.5),
        "signals": signals,
        "matched_rules": mr,
    }


def _validate_query_profile_two_pass(payload: Dict[str, Any]) -> QueryProfile:
    """
    RuleHit field names vary across codebases (rule vs rule_id, score vs confidence).
    We try the common case first (rule_id/confidence), and if that fails,
    we adapt and try again.
    """
    try:
        return QueryProfile.model_validate(payload)
    except ValidationError:
        # Pass 2: map rule_id -> rule, confidence -> score (if your RuleHit expects that)
        mr2: List[Dict[str, Any]] = []
        for hit in (payload.get("matched_rules") or []):
            if not isinstance(hit, dict):
                continue
            h2 = dict(hit)
            if "rule_id" in h2 and "rule" not in h2:
                h2["rule"] = h2.pop("rule_id")
            if "confidence" in h2 and "score" not in h2:
                h2["score"] = h2.pop("confidence")
            mr2.append(h2)

        payload2 = dict(payload)
        payload2["matched_rules"] = mr2
        return QueryProfile.model_validate(payload2)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def analyze_query_with_llm(
    query: str,
    *,
    llm: Optional[OpenAIChatLLM] = None,
    fallback_to_rules: bool = True,
) -> QueryProfile:
    q = (query or "").strip()
    if not q:
        prof = QueryProfile()
        prof.signals = dict(prof.signals or {})
        prof.signals["analysis_source"] = "empty"
        return prof

    if llm is None:
        cfg = OpenAIConfig.load()
        llm = OpenAIChatLLM(api_key=cfg.api_key, model=cfg.model, base_url=cfg.base_url)

    try:
        user_prompt = _CLASSIFIER_USER_TEMPLATE.format(query=q)

        resp = await llm.ainvoke(
            [
                {"role": "system", "content": _CLASSIFIER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )

        text = _coerce_llm_text(resp).strip()
        json_text = _extract_first_json_object(text)
        data = json.loads(json_text)

        safe = _sanitize_to_query_profile_dict(data)
        prof = _validate_query_profile_two_pass(safe)

        prof.signals = dict(prof.signals or {})
        prof.signals["analysis_source"] = "llm"
        prof.signals["llm_mode"] = "json"

        # If LLM gave no matched_rules, add a minimal structured trace
        if not prof.matched_rules:
            prof.matched_rules = [
                make_hit(
                    rule="llm:query_profile:classified",
                    action=RuleAction.READ,
                    category=RuleCategory.POLICY,
                    score=prof.sub_intent_confidence or prof.intent_confidence or 0.5,
                    note="LLM classified query profile",
                )
            ]

        return prof

    except Exception as e:
        if fallback_to_rules:
            prof = analyze_query(q)
            prof.matched_rules.append(
                make_hit(
                    rule="llm:query_profile:error_fallback",
                    action=RuleAction.READ,
                    category=RuleCategory.POLICY,
                    score=0.0,
                    error=str(e),
                )
            )
            prof.signals = dict(prof.signals or {})
            prof.signals["analysis_source"] = "rules_fallback"
            return prof

        return QueryProfile(
            signals={"analysis_source": "llm_error"},
            matched_rules=[
                make_hit(
                    rule="llm:query_profile:error",
                    action=RuleAction.READ,
                    category=RuleCategory.POLICY,
                    score=0.0,
                    error=str(e),
                )
            ],
        )


async def analyze_agent_queries_with_llm(
    agent_queries: Dict[str, str],
    *,
    llm: Optional[OpenAIChatLLM] = None,
) -> Dict[str, QueryProfile]:
    results: Dict[str, QueryProfile] = {}
    for agent_name, q in agent_queries.items():
        results[agent_name] = await analyze_query_with_llm(q, llm=llm)
    return results
