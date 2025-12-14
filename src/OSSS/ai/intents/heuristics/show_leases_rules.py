from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='leases__explicit_show',
        intent='leases',
        priority=55,
        keywords=['show leases', 'leases', 'facility leases', 'equipment leases', 'rental agreements', 'dcg leases'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "leases_rules"},
    ),
]
