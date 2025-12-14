from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='scan_results__explicit_show',
        intent='scan_results',
        priority=55,
        keywords=['show scan results', 'scan_results', 'scan results', 'security scans', 'scan findings', 'scan output', 'scanner results'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "scan_results_rules"},
    ),
]
