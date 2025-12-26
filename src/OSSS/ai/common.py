from __future__ import annotations

from enum import Enum


class CircuitState(str, Enum):
    CLOSED = "closed"      # normal operation
    OPEN = "open"          # failing fast (circuit tripped)
    HALF_OPEN = "half_open"  # probing recovery
