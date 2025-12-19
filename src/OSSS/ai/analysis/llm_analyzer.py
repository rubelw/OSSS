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

- action: one of
  ["read", "create", "add", "update", "edit", "delete", "troubleshoot", "review", "explain", "route"]

- intent: one of
  [
    "information_lookup",
    "entity_listing",
    "record_inspection",
    "record_mutation",
    "analysis",
    "comparison",
    "explanation",
    "instruction",
    "troubleshooting",
    "navigation",
    "freeform",
  ]

- intent_confidence: number between 0.0 and 1.0

- sub_intent: short snake_case string describing the specific goal
  (examples: "dcg_teachers", "teacher_schedule", "record_update", "policy_lookup")

- sub_intent_confidence: number between 0.0 and 1.0

- tone: one of
  ["neutral","informative","questioning","instructional","imperative","exploratory","critical","supportive"]

- tone_confidence: number between 0.0 and 1.0

- complexity: one of
  ["low", "medium", "high"]

- safety: one of
  ["safe_read_only", "requires_confirmation", "restricted"]

- requires_tools: boolean

- signals: object containing any helpful flags

- matched_rules: array of objects with:
  - rule_id: string
  - action: one of ["read", "create", "update", "delete", "block"]
  - confidence: number between 0.0 and 1.0

If information is unclear, make a best-effort guess and lower confidence scores.

User query:
\"\"\"{query}\"\"\"
""".strip()


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

# For *rule hit* actions we keep a conservative set (what your rules/engine can execute).
_ALLOWED_RULE_ACTIONS = {"read", "create", "update", "delete","block"}

# For *top-level* LLM action we allow the richer set (what your envelope accepts).
_ALLOWED_TOP_LEVEL_ACTIONS = {
    "read",
    "create",
    "add",
    "update",
    "edit",
    "delete",
    "troubleshoot",
    "review",
    "explain",
    "route",
}

# Synonyms and older schemas
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
    "list": "read",
    "compare": "read",
    "general": "read",
    "read": "read",

    # Create-like
    "create": "create",
    "insert": "create",
    "new": "create",
    "add": "add",  # keep as add for top-level, normalize later if desired

    # Update-like
    "modify": "update",
    "change": "update",
    "edit": "edit",  # keep as edit for top-level, normalize later if desired
    "fix": "update",
    "correct": "update",
    "patch": "update",
    "update": "update",

    # Delete-like
    "remove": "delete",
    "erase": "delete",
    "destroy": "delete",
    "delete": "delete",

    # Other explicit actions
    "troubleshoot": "troubleshoot",
    "review": "review",
    "explain": "explain",
    "route": "route",

    # Old “write” category
    "write": "create",

    # Older “block/deny” handling: default to safest
    "block": "block",
    "deny": "block",
}

_ALLOWED_TONE = {
    "neutral",
    "informative",
    "questioning",
    "instructional",
    "imperative",
    "exploratory",
    "critical",
    "supportive",
}

_ALLOWED_COMPLEXITY = {"low", "medium", "high"}
_ALLOWED_SAFETY = {"safe_read_only", "requires_confirmation", "restricted"}

ACTION_NORMALIZATION = {
    "add": "create",
    "edit": "update",
}

_TONE_ALIASES = {
    "question": "questioning",
    "instruction": "instructional",
    "command": "imperative",
}

def normalize_top_level_action(action: Any) -> str:
    if not isinstance(action, str) or not action.strip():
        return "read"
    a = action.strip().lower()
    a = _ACTION_ALIASES.get(a, a)
    a = ACTION_NORMALIZATION.get(a, a)
    return a if a in _ALLOWED_TOP_LEVEL_ACTIONS else "read"


def normalize_rule_action(action: Any) -> str:
    """
    Normalize LLM rule-hit actions into what RuleHit expects.
    Keep conservative: read/create/update/delete/block.
    """
    if not isinstance(action, str) or not action.strip():
        return "read"
    a = action.strip().lower()
    a = _ACTION_ALIASES.get(a, a)
    a = ACTION_NORMALIZATION.get(a, a)

    # Map richer actions into rule-safe actions
    if a in {"troubleshoot", "review", "explain", "route"}:
        return "read"

    return a if a in _ALLOWED_RULE_ACTIONS else "read"

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

        action = normalize_rule_action(item.get("action"))
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
        signals.setdefault("llm_action", normalize_top_level_action(data.get("action")))
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
    intent_raw = _as_str(data.get("intent"), "freeform")
    tone_raw = _as_str(data.get("tone"), "neutral")
    sub_intent_raw = _as_str(data.get("sub_intent"), "freeform")

    # Normalize tone to allowed set (keep neutral if unknown)
    tone = _TONE_ALIASES.get(tone_raw.lower(), tone_raw.lower())
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
