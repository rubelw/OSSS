# OSSS/ai/agents/query_data/query_data_errors.py
from __future__ import annotations

from typing import Optional


class QueryDataError(Exception):
    """Raised when querying one of the external OSSS data APIs fails.

    We keep URLs as attributes so the agent can surface them in debug info.
    """

    def __init__(
        self,
        message: str,
        *,
        students_url: Optional[str] = None,
        persons_url: Optional[str] = None,
        scorecards_url: Optional[str] = None,
        live_scorings_url: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.students_url = students_url
        self.persons_url = persons_url
        self.scorecards_url = scorecards_url
        self.live_scorings_url = live_scorings_url
