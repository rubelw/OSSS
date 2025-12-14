from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='health_profiles__explicit_show',
        intent='health_profiles',
        priority=55,
        keywords=['show health profiles', 'health_profiles', 'health profiles', 'student health profiles', 'medical profiles'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "health_profiles_rules"},
    ),
]
