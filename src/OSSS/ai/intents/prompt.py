# src/OSSS/ai/intents/prompt.py
from __future__ import annotations
from .registry import INTENTS

def build_intent_system_prompt() -> str:
    lines = []
    lines.append("You are an intent classifier for questions about Dallas Center-Grimes (DCG) schools.")
    lines.append('Return ONLY one JSON object on one line with keys: intent, confidence, action, action_confidence, urgency, urgency_confidence, tone_major, tone_major_confidence, tone_minor, tone_minor_confidence.')
    lines.append("")
    lines.append("Valid intents:")

    for spec in INTENTS.values():
        lines.append(f'- "{spec.intent.value}": {spec.description}')
        if spec.examples:
            ex = "; ".join(spec.examples[:2])
            lines.append(f"  examples: {ex}")

    lines.append("")
    lines.append('If unsure, use "general".')
    return "\n".join(lines)
