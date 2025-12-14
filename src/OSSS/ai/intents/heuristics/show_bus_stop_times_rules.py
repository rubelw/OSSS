from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='bus_stop_times__explicit_show',
        intent='bus_stop_times',
        priority=55,
        keywords=['show bus stop times', 'bus_stop_times', 'bus stop times', 'bus schedule', 'transportation schedule'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "bus_stop_times_rules"},
    ),
]
