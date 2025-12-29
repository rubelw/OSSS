# OSSS/ai/orchestration/models_internal.py

from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field, ConfigDict

# Re-use canonical envelope model from context
from OSSS.ai.context import AgentOutputEnvelope


class RoutingMeta(BaseModel):
    source: str
    planned_agents: List[str] = []
    executed_agents: List[str] = []
    pre_agents: List[str] = []
    selected_workflow_id: Optional[str] = None
    graph_pattern: Optional[str] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


class WorkflowResult(BaseModel):
    query: str
    graph_pattern: Optional[str]
    routing: RoutingMeta
    envelopes: List[AgentOutputEnvelope] = []
    execution_state: Dict[str, Any] = {}

    # Optional convenience: already-computed final answer
    final_answer_agent: Optional[str] = None
    final_answer: Any = None

    model_config = ConfigDict(arbitrary_types_allowed=True)
