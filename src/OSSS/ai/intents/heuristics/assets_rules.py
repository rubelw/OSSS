from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name="assets__explicit_show",
        intent="assets",
        priority=55,
        keywords=[
            "assets",
            "show assets",
            "list assets",
            "view assets",
            "asset inventory",
            "inventory assets",
            "fixed assets",
            "equipment",
            "equipment inventory",
        ],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.85,
        confidence=0.98,
        metadata={"source": "assets_rules"},
    ),
]
