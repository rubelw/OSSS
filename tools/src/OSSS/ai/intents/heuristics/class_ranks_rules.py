from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='class_ranks__explicit_show',
        intent='class_ranks',
        priority=55,
        keywords=['show class ranks', 'class_ranks', 'class ranks', 'class rank', 'graduation rank'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "class_ranks_rules"},
    ),
]
