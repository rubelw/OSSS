# OSSS/ai/agents/utils/dialog_utils.py
from __future__ import annotations

import logging
import re
from datetime import date
from typing import List, Optional

logger = logging.getLogger("OSSS.ai.agents.utils.dialog_utils")


def parse_yes_no_choice(query: str) -> Optional[bool]:
    q = (query or "").strip().lower()
    if not q:
        return None
    if q.endswith((".", ")")):
        q = q[:-1].strip()
    if q in ("1", "yes", "y"):
        return True
    if q in ("2", "no", "n"):
        return False
    return None


def parse_numeric_yes_no(query: str) -> Optional[bool]:
    if not query:
        return None
    q = query.strip().lower()
    if q.endswith((".", ")")):
        q = q[:-1].strip()
    if q == "1":
        return True
    if q == "2":
        return False
    return None


def _has_trigger(query: str, triggers: List[str]) -> bool:
    q = (query or "").lower()
    hit = any(t in q for t in triggers)
    logger.debug("[_has_trigger] query=%r triggers=%r -> hit=%s", q, triggers, hit)
    return hit


def wants_new_registration(query: str) -> bool:
    return _has_trigger(
        query,
        [
            "start a new registration",
            "start another registration",
            "another registration",
            "new registration",
            "register another student",
            "register a different student",
            "register a new student",
            "i would like to register a new student",
            "i want to register a new student",
        ],
    )


def wants_continue_registration(query: str) -> bool:
    return _has_trigger(
        query,
        [
            "continue",
            "resume",
            "pick up where we left off",
            "continue current registration",
            "resume registration",
            "same registration",
            "same student",
        ],
    )


def extract_school_year(query: str) -> Optional[str]:
    if not query:
        logger.debug("[extract_school_year] no query; returning None.")
        return None

    q_norm = query.strip().replace("–", "-").replace("—", "-")
    logger.debug("[extract_school_year] raw_query=%r normalized=%r", query, q_norm)

    m = re.search(r"(20[2-9][0-9])[-/](?:20[2-9][0-9]|[0-9]{2})", q_norm)
    if m:
        logger.info("[extract_school_year] matched school_year=%s", m.group(0))
        return m.group(0)

    logger.debug("[extract_school_year] no match found.")
    return None


def get_default_school_year_options() -> List[str]:
    today = date.today()
    start_year = max(today.year, 2024)
    options: List[str] = []
    for i in range(3):
        y = start_year + i
        next_y = y + 1
        options.append(f"{y}-{str(next_y % 100).zfill(2)}")
    return options


def parse_school_year_choice(query: str, options: List[str]) -> Optional[str]:
    q = (query or "").strip().lower()
    if not q:
        return None

    if q.endswith((".", ")")):
        q = q[:-1].strip()

    if q.isdigit():
        idx = int(q) - 1
        if 0 <= idx < len(options):
            return options[idx]

    detected = extract_school_year(query)
    if detected:
        return detected if detected in options else detected

    return None
