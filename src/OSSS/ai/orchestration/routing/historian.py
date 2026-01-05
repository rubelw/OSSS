from __future__ import annotations
from typing import Any

def should_run_historian(exec_state: dict[str, Any] | None) -> bool:
    """
    Central policy for whether historian should run.

    Conservative default:
    - Never run when history is suppressed / wizard bailed.
    - Otherwise allow.
    """
    es = exec_state or {}
    if bool(es.get("suppress_history")):
        return False
    if bool(es.get("wizard_bailed")):
        return False
    if bool(es.get("checkpoints_skipped")):
        return False
    return True
