from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='projects__explicit_show',
        intent='projects',
        priority=55,
        keywords=['show projects', 'projects', 'project list', 'dcg projects', 'osss projects', 'grant projects', 'district projects'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "projects_rules"},
    ),
]
