from __future__ import annotations
from OSSS.ai.intents.heuristics import HeuristicRule

RULES: list[HeuristicRule] = [
    HeuristicRule(
        name="student_info_withdrawn",
        priority=10,
        intent="student_info",  # must exist in Intent enum OR be aliased
        action="show_withdrawn_students",
        keywords=[
            "withdrawn students",
            "inactive students",
            "unenrolled students",
            "not enrolled students",
        ],
        word_boundary=True,
        metadata={"mode": "student_info", "enrolled_only": False},
    ),
    HeuristicRule(
        name="student_info_generic",
        priority=50,
        intent="student_info",
        action="read",
        keywords=[
            "student info",
            "show students",
            "students list",
            "list students",
        ],
        word_boundary=True,
        metadata={"mode": "student_info"},
    ),
]
