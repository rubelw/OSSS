# src/OSSS/ai/intents/heuristics/apply.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence
import json
import re

from OSSS.ai.intents.types import Intent, IntentResult
from OSSS.ai.intents.registry import INTENT_ALIASES


@dataclass(frozen=True)
class HeuristicRule:
  name: str
  priority: int = 100
  intent: str = "general"
  action: Optional[str] = "read"
  keywords: Sequence[str] = field(default_factory=tuple)
  regex: Optional[str] = None
  word_boundary: bool = True
  metadata: dict[str, Any] = field(default_factory=dict)


def _compile_keyword_pattern(keyword: str, *, word_boundary: bool) -> re.Pattern[str]:
  kw = re.escape(keyword.strip())
  if word_boundary:
    # allow spaces/punctuation boundaries; good for avoiding “enroll” matching “re-enrollmentzzz”
    return re.compile(rf"(?<!\w){kw}(?!\w)", re.IGNORECASE)
  return re.compile(kw, re.IGNORECASE)


def apply_heuristics(text: str, rules: Sequence[HeuristicRule]) -> Optional[IntentResult]:
  t = text or ""

  # Higher priority first
  ordered = sorted(rules, key=lambda r: r.priority)

  for rule in ordered:
    matched = False

    if rule.keywords:
      for kw in rule.keywords:
        if not kw:
          continue
        if _compile_keyword_pattern(kw, word_boundary=rule.word_boundary).search(t):
          matched = True
          break

    if not matched and rule.regex:
      if re.search(rule.regex, t, flags=re.IGNORECASE):
        matched = True

    if not matched:
      continue

    # map string -> Intent enum (aliases allowed)
    aliased = INTENT_ALIASES.get(rule.intent, rule.intent)
    try:
      intent_enum = Intent(aliased)
    except Exception:
      intent_enum = Intent.GENERAL

    bundle = {
      "source": "heuristic",
      "rule": {
        "name": rule.name,
        "priority": rule.priority,
        "intent": rule.intent,
        "action": rule.action,
        "keywords": list(rule.keywords),
        "regex": rule.regex,
        "word_boundary": rule.word_boundary,
        "metadata": rule.metadata,
      },
      "text": text,
    }

    return IntentResult(
      intent=intent_enum,
      confidence=0.95,
      raw=bundle,
      action=rule.action,
      action_confidence=0.95,
      raw_model_content=json.dumps(bundle, ensure_ascii=False),
      raw_model_output=json.dumps(bundle, ensure_ascii=False),
      source="heuristic",
    )

  return None
