from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='behavior_interventions__explicit_show',
        intent='behavior_interventions',
        priority=55,
        keywords=['show behavior interventions', 'behavior_interventions', 'behavior interventions', 'behavior supports', 'mtss interventions'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "behavior_interventions_rules"},
    ),
]
