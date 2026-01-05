# OSSS.ai.orchestration.routers.helpers

from __future__ import annotations
from typing import Any, Dict

from OSSS.ai.orchestration.state_schemas import OSSSState


def safe_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def get_exec_state(state: OSSSState) -> Dict[str, Any]:
    return safe_dict(state.get("execution_state"))


def get_agent_output_meta(state: OSSSState) -> Dict[str, Any]:
    exec_state = get_exec_state(state)
    return safe_dict(exec_state.get("agent_output_meta"))
