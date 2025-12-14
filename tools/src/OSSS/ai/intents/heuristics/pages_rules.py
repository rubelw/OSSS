from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='pages__explicit_show',
        intent='pages',
        priority=55,
        keywords=['show pages', 'pages', 'site pages', 'osss pages', 'dcg website pages', 'content pages', 'page list'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "pages_rules"},
    ),
]
