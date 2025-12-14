from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='waivers__explicit_show',
        intent='waivers',
        priority=55,
        keywords=['show waivers', 'waivers', 'waiver', 'student waivers', 'program waivers', 'fee waivers'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "waivers_rules"},
    ),
]
