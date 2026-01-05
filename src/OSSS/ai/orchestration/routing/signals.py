from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class RoutingSignals:
    target: Optional[str] = None         # "data_query", "refiner", ...
    locked: bool = False
    reason: Optional[str] = None
    key: Optional[str] = None            # e.g. "action", "crud", ...


