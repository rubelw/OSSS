from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='standards__explicit_show',
        intent='standards',
        priority=55,
        keywords=['show standards', 'standards', 'academic standards', 'learning standards', 'state standards', 'standards codes'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "standards_rules"},
    ),
]
