from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass(frozen=True)
class WizardNormalizationResult:
    effective_query: str
    wizard_bailed: bool
    wizard_in_progress: bool
    patch: Dict[str, Any]         # state updates to merge into execution_state
    wizard_state: Optional[Dict[str, Any]] = None
