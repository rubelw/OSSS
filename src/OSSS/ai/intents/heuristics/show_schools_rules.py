from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='schools__explicit_show',
        intent='schools',
        priority=55,
        keywords=['show schools', 'schools', 'school list', 'list schools', 'dcg schools', 'district schools', 'school buildings', 'school directory'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "schools_rules"},
    ),
]
