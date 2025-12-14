from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='state_reporting_snapshots__explicit_show',
        intent='state_reporting_snapshots',
        priority=55,
        keywords=['show state reporting snapshots', 'state_reporting_snapshots', 'state reporting snapshots', 'state reporting snapshot', 'state reporting export', 'state reporting submission'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "state_reporting_snapshots_rules"},
    ),
]
