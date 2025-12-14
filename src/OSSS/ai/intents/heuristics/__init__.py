# src/OSSS/ai/intents/heuristics/__init__.py
from .apply import HeuristicRule, apply_heuristics
from .staff_info_rules import RULES as STAFF_INFO_RULES
from .student_info_rules import RULES as STUDENT_INFO_RULES
from .enrollment_rules import RULES as ENROLLMENT_RULES

ALL_RULES = [
    *STAFF_INFO_RULES,
    *STUDENT_INFO_RULES,
    *ENROLLMENT_RULES,
]

__all__ = [
    "HeuristicRule",
    "apply_heuristics",
    "ALL_RULES",
]
