from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='agenda_workflow_steps__explicit_show',
        intent='agenda_workflow_steps',
        priority=55,
        keywords=['show agenda workflow steps', 'agenda_workflow_steps', 'agenda workflow steps', 'agenda approval steps'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "agenda_workflow_steps_rules"},
    ),
]
