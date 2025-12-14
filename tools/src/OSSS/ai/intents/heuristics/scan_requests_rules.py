from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='scan_requests__explicit_show',
        intent='scan_requests',
        priority=55,
        keywords=['show scan requests', 'scan_requests', 'scan requests', 'scan queue', 'queued scans', 'requested scans', 'pending scans', 'scheduled scans'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "scan_requests_rules"},
    ),
]
