"""
DB Query Router (signals-only, no side effects).

This module is intentionally *pure* and *stable*:
- It does NOT mutate execution_state.
- It does NOT decide graph patterns directly.
- It returns structured RoutingSignals that the Planner can consume.

Long-term design:
    request + exec_state  -->  RoutingSignals  -->  Planner  -->  ExecutionPlan  -->  GraphFactory

The bug you’ve been hitting happens when routing runs *after* the graph is compiled.
This file avoids that by producing signals early (planning phase), and never “forcing”
graph decisions inside the router.

Integration points:
- Call compute_db_query_signals(exec_state, request, ...) during the planning pipeline
  (before GraphFactory.create_graph).
- If signals.locked is True and signals.target == "data_query", the Planner should
  return an ExecutionPlan(pattern="data_query", agents=[...], entry_point="refiner", ...).

Heuristics (configurable):
- Query prefix commands: "query ", "sql ", "select ", etc.
- Known data-query topics/collections (from DataQueryRoute registry or exec_state hints)
- Classifier intent/domain/topic signals
- Lightweight keyword hints ("database", "table", etc.)

This is intentionally conservative: it should only route to data_query when there are
clear signals; otherwise it returns target=None and lets other rules decide.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional, Sequence


# ---------------------------------------------------------------------------
# Public structured output (signals)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RoutingSignals:
    """
    Structured routing result consumed by planning.

    target:
        Intended entry target (e.g. "data_query", "refiner").
        None means "no strong opinion; let planner decide".

    locked:
        When True, planner should treat target as forced (higher priority than other rules).

    reason:
        Human-readable reason (stable string for observability).

    key:
        Optional stable categorization key, e.g. "action", "crud", "query_prefix".
    """

    target: Optional[str] = None
    locked: bool = False
    reason: Optional[str] = None
    key: Optional[str] = None

    def normalized(self) -> "RoutingSignals":
        t = self.target.strip().lower() if isinstance(self.target, str) and self.target.strip() else None
        r = self.reason.strip() if isinstance(self.reason, str) and self.reason.strip() else None
        k = self.key.strip().lower() if isinstance(self.key, str) and self.key.strip() else None
        return RoutingSignals(target=t, locked=bool(self.locked), reason=r, key=k)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_QUERY_PREFIXES: tuple[str, ...] = (
    "query ",
    "sql ",
    "select ",
    "insert ",
    "update ",
    "delete ",
    "explain ",
    "describe ",
    "show ",
)

DEFAULT_DB_KEYWORDS: tuple[str, ...] = (
    "database",
    "db",
    "table",
    "schema",
    "column",
    "columns",
    "view",
    "primary key",
    "foreign key",
    "join",
)

DEFAULT_DATA_DOMAINS: tuple[str, ...] = (
    "data_systems",
    "data",
    "database",
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_db_query_signals(
    exec_state: Mapping[str, Any],
    request: Mapping[str, Any],
    *,
    query_prefixes: Sequence[str] = DEFAULT_QUERY_PREFIXES,
    db_keywords: Sequence[str] = DEFAULT_DB_KEYWORDS,
    # If you have a DataQueryRoute registry available at planning-time,
    # pass its topics/collections here for a strong "has_db_table" signal.
    known_topics: Optional[Iterable[str]] = None,
    known_collections: Optional[Iterable[str]] = None,
    # Safety: only lock when confidence is high.
    lock_on_prefix: bool = True,
    lock_on_known_topic: bool = True,
) -> RoutingSignals:
    """
    Return routing signals indicating whether this request should start in data_query.

    This function is pure and safe to call multiple times.

    Strong signals (can lock):
      - Query prefix (e.g. "query consents")
      - Classifier primary topic matches known data-query topics/collections

    Medium signals (do NOT lock by default):
      - intent=="action" AND domain in DEFAULT_DATA_DOMAINS AND db keyword present

    If no strong signals are present, returns RoutingSignals(target=None).
    """
    q = _extract_query_text(exec_state, request)
    q_norm = _norm_text(q)

    # Build knowledge sets
    topics = _to_lower_set(known_topics) | _infer_known_topics(exec_state)
    colls = _to_lower_set(known_collections) | _infer_known_collections(exec_state)

    # Classifier signals
    classifier_intent = _extract_classifier_intent(exec_state)
    classifier_domain = _extract_classifier_domain(exec_state)
    classifier_topic = _extract_classifier_topic(exec_state)

    # Query prefix command?
    prefix_hit = _starts_with_any(q_norm, query_prefixes)
    has_db_kw = _contains_any(q_norm, db_keywords)

    # Known topic/collection match?
    topic_hit = bool(classifier_topic) and (classifier_topic in topics or classifier_topic in colls)

    # Also allow direct "query <topic>" detection even if classifier is weird:
    # e.g., q="query consents" -> possible_topic="consents"
    possible_topic = _topic_after_prefix(q_norm, query_prefixes)
    possible_topic_hit = bool(possible_topic) and (possible_topic in topics or possible_topic in colls)

    # -----------------------------------------------------------------------
    # Strong signals (lockable)
    # -----------------------------------------------------------------------
    if prefix_hit and lock_on_prefix:
        # If you want: only lock on prefix when it looks like a known table/topic.
        # But your logs show "query consents" should lock reliably.
        return RoutingSignals(
            target="data_query",
            locked=True,
            reason="query_prefix_command",
            key="query_prefix",
        ).normalized()

    if (topic_hit or possible_topic_hit) and lock_on_known_topic:
        return RoutingSignals(
            target="data_query",
            locked=True,
            reason="known_data_query_topic",
            key="has_db_table",
        ).normalized()

    # -----------------------------------------------------------------------
    # Medium signals (non-locking)
    # -----------------------------------------------------------------------
    if classifier_intent == "action" and (classifier_domain in DEFAULT_DATA_DOMAINS) and has_db_kw:
        return RoutingSignals(
            target="data_query",
            locked=False,
            reason="action_domain_db_keyword",
            key="heuristic",
        ).normalized()

    # No strong opinion
    return RoutingSignals(target=None, locked=False, reason=None, key=None).normalized()


# ---------------------------------------------------------------------------
# Optional convenience wrapper class (nice for DI/testing)
# ---------------------------------------------------------------------------

class DBQueryRouter:
    """
    Thin wrapper around compute_db_query_signals for dependency injection.

    Example:
        router = DBQueryRouter(known_topics=data_query_registry.topics())
        signals = router.compute(exec_state, request)
    """

    def __init__(
        self,
        *,
        known_topics: Optional[Iterable[str]] = None,
        known_collections: Optional[Iterable[str]] = None,
        query_prefixes: Sequence[str] = DEFAULT_QUERY_PREFIXES,
        db_keywords: Sequence[str] = DEFAULT_DB_KEYWORDS,
        lock_on_prefix: bool = True,
        lock_on_known_topic: bool = True,
    ) -> None:
        self._known_topics = known_topics
        self._known_collections = known_collections
        self._query_prefixes = query_prefixes
        self._db_keywords = db_keywords
        self._lock_on_prefix = lock_on_prefix
        self._lock_on_known_topic = lock_on_known_topic

    def compute(self, exec_state: Mapping[str, Any], request: Mapping[str, Any]) -> RoutingSignals:
        return compute_db_query_signals(
            exec_state,
            request,
            query_prefixes=self._query_prefixes,
            db_keywords=self._db_keywords,
            known_topics=self._known_topics,
            known_collections=self._known_collections,
            lock_on_prefix=self._lock_on_prefix,
            lock_on_known_topic=self._lock_on_known_topic,
        )


# ---------------------------------------------------------------------------
# Internals (pure helpers)
# ---------------------------------------------------------------------------

def _extract_query_text(exec_state: Mapping[str, Any], request: Mapping[str, Any]) -> str:
    # Prefer explicit request["query"], then stable exec_state fields.
    for src in (request, exec_state):
        if not isinstance(src, Mapping):
            continue
        for k in ("query", "user_query", "raw_user_text", "original_query", "question"):
            v = src.get(k)
            if isinstance(v, str) and v.strip():
                return v
    return ""


def _extract_classifier_intent(exec_state: Mapping[str, Any]) -> str:
    task_cls = exec_state.get("task_classification")
    if isinstance(task_cls, Mapping):
        v = task_cls.get("intent")
        if isinstance(v, str):
            return v.strip().lower()
    cls = exec_state.get("classifier")
    if isinstance(cls, Mapping):
        v = cls.get("intent")
        if isinstance(v, str):
            return v.strip().lower()
    return ""


def _extract_classifier_domain(exec_state: Mapping[str, Any]) -> str:
    cog = exec_state.get("cognitive_classification")
    if isinstance(cog, Mapping):
        v = cog.get("domain")
        if isinstance(v, str):
            return v.strip().lower()
    cls = exec_state.get("classifier")
    if isinstance(cls, Mapping):
        v = cls.get("domain")
        if isinstance(v, str):
            return v.strip().lower()
    return ""


def _extract_classifier_topic(exec_state: Mapping[str, Any]) -> str:
    cog = exec_state.get("cognitive_classification")
    if isinstance(cog, Mapping):
        v = cog.get("topic")
        if isinstance(v, str):
            return v.strip().lower()
    cls = exec_state.get("classifier")
    if isinstance(cls, Mapping):
        v = cls.get("topic")
        if isinstance(v, str):
            return v.strip().lower()
    return ""


def _infer_known_topics(exec_state: Mapping[str, Any]) -> set[str]:
    """
    Tries to infer data_query topics from exec_state if they were injected upstream.

    Recommended long-term:
      - inject known topics/collections explicitly from DataQueryRoute registry
        rather than fishing in exec_state.

    Supported optional exec_state keys (if you choose to set them):
      - exec_state["data_query_topics"] = [...]
      - exec_state["data_query_collections"] = [...]
    """
    topics = exec_state.get("data_query_topics")
    return _to_lower_set(topics)


def _infer_known_collections(exec_state: Mapping[str, Any]) -> set[str]:
    colls = exec_state.get("data_query_collections")
    return _to_lower_set(colls)


def _to_lower_set(values: Optional[Iterable[Any]]) -> set[str]:
    if not values:
        return set()
    out: set[str] = set()
    for v in values:
        if not v:
            continue
        s = str(v).strip().lower()
        if s:
            out.add(s)
    return out


def _norm_text(s: str) -> str:
    return (s or "").strip().lower()


def _starts_with_any(text: str, prefixes: Sequence[str]) -> bool:
    t = text or ""
    for p in prefixes:
        if not p:
            continue
        p2 = str(p).lower()
        if t.startswith(p2):
            return True
    return False


def _contains_any(text: str, needles: Sequence[str]) -> bool:
    t = text or ""
    for n in needles:
        if not n:
            continue
        if str(n).lower() in t:
            return True
    return False


def _topic_after_prefix(text: str, prefixes: Sequence[str]) -> str:
    """
    If text starts with a known prefix, return the next token as a possible topic.
    Example: "query consents" -> "consents"
    """
    t = (text or "").strip().lower()
    for p in prefixes:
        if not p:
            continue
        p2 = str(p).lower()
        if t.startswith(p2):
            rest = t[len(p2):].strip()
            # next token only; keep conservative
            return rest.split()[0] if rest else ""
    return ""
