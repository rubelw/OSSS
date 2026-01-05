from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Plan:
    pattern_name: str
    planned_agents: List[str]
    entry_point: Optional[str] = None
    reason: str = ""
    signals: Dict[str, Any] | None = None
