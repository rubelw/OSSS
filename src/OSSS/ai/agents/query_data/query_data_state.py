from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel


class StudentQueryState(BaseModel):
    """
    Minimal per-session state for the query_data flow.

    You can expand this later (filters, search term, grade level, etc.).
    """

    session_id: str
    skip: int = 0
    limit: int = 25
    last_results: Optional[List[dict[str, Any]]] = None
