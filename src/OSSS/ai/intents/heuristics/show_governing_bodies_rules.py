from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='governing_bodies__explicit_show',
        intent='governing_bodies',
        priority=55,
        keywords=['show governing bodies', 'governing_bodies', 'governing bodies', 'school board', 'board of education', 'district governing body', 'governance body', 'oversight body'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "governing_bodies_rules"},
    ),
]
