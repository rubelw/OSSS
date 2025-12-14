from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='scorecard_kpis__explicit_show',
        intent='scorecard_kpis',
        priority=55,
        keywords=['show scorecard kpis', 'scorecard_kpis', 'scorecard kpis', 'kpis on scorecards', 'plan kpis', 'performance indicators'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "scorecard_kpis_rules"},
    ),
]
