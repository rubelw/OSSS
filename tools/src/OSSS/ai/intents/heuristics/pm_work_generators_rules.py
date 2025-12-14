from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='pm_work_generators__explicit_show',
        intent='pm_work_generators',
        priority=55,
        keywords=['show pm work generators', 'pm_work_generators', 'pm work generators', 'plan work generators', 'work generation templates', 'dcg pm work generators', 'osss pm work generators'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "pm_work_generators_rules"},
    ),
]
