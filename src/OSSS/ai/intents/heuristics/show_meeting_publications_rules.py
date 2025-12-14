from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='meeting_publications__explicit_show',
        intent='meeting_publications',
        priority=55,
        keywords=['show meeting publications', 'meeting_publications', 'meeting publications', 'board meeting publications', 'published meetings', 'dcg meeting publications'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "meeting_publications_rules"},
    ),
]
