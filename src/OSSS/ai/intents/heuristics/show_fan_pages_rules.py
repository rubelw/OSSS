from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='fan_pages__explicit_show',
        intent='fan_pages',
        priority=55,
        keywords=['show fan pages', 'fan_pages', 'fan pages', 'fan page', 'school fan page', 'athletics fan page', 'game day fan page'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "fan_pages_rules"},
    ),
]
