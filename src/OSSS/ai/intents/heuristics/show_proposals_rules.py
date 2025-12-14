from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='proposals__explicit_show',
        intent='proposals',
        priority=55,
        keywords=['show proposals', 'proposals', 'proposal', 'grant proposals', 'DCG proposals', 'OSSS proposals'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "proposals_rules"},
    ),
]
