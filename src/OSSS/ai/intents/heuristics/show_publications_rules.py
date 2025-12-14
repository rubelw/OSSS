from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='publications__explicit_show',
        intent='publications',
        priority=55,
        keywords=['show publications', 'publications', 'board publications', 'district publications', 'policy publications', 'meeting publications', 'dcg publications', 'osss publications'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "publications_rules"},
    ),
]
