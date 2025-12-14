from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='requirements__explicit_show',
        intent='requirements',
        priority=55,
        keywords=['show requirements', 'requirements', 'requirement records', 'list requirements', 'program requirements', 'graduation requirements', 'course requirements', 'eligibility requirements', 'policy requirements', 'dcg requirements', 'osss requirements'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "requirements_rules"},
    ),
]
