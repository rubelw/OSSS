from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='curriculum_versions__explicit_show',
        intent='curriculum_versions',
        priority=55,
        keywords=['show curriculum versions', 'curriculum_versions', 'curriculum versions', 'curriculum version history', 'versions of curriculum'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "curriculum_versions_rules"},
    ),
]
