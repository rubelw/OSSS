from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='export_runs__explicit_show',
        intent='export_runs',
        priority=55,
        keywords=['show export runs', 'export_runs', 'export runs', 'data export runs', 'export history', 'csv export runs', 'job export runs'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "export_runs_rules"},
    ),
]
