from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='section_meetings__explicit_show',
        intent='section_meetings',
        priority=55,
        keywords=['show section meetings', 'section_meetings', 'section meetings', 'class meeting times', 'when does this section meet'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "section_meetings_rules"},
    ),
]
