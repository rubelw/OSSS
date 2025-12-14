from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='states__explicit_show',
        intent='states',
        priority=55,
        keywords=['show states', 'states', 'state list', 'list of states', 'us states', 'state codes', 'state abbreviations', 'show state list'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "states_rules"},
    ),
]
