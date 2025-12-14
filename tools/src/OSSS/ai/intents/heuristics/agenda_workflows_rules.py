from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='agenda_workflows__explicit_show',
        intent='agenda_workflows',
        priority=55,
        keywords=['show agenda workflows', 'agenda_workflows', 'agenda workflows', 'board agenda workflows'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "agenda_workflows_rules"},
    ),
]
