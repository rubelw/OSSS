from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='subjects__explicit_show',
        intent='subjects',
        priority=55,
        keywords=['show subjects', 'subjects', 'course subjects', 'subject list', 'list subjects', 'all subjects'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "subjects_rules"},
    ),
]
