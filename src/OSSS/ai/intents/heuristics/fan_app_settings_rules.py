from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='fan_app_settings__explicit_show',
        intent='fan_app_settings',
        priority=55,
        keywords=['show fan app settings', 'fan_app_settings', 'fan app settings', 'fan app config', 'fan app configuration', 'fan app preferences', 'athletics app settings', 'fan experience settings'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "fan_app_settings_rules"},
    ),
]
