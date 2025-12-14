from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='resolutions__explicit_show',
        intent='resolutions',
        priority=55,
        keywords=['show resolutions', 'resolutions', 'board resolutions', 'policy resolutions', 'meeting resolutions', 'dcg resolutions', 'osss resolutions', 'adopted resolutions', 'approved resolutions', 'resolution records', 'list resolutions'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "resolutions_rules"},
    ),
]
