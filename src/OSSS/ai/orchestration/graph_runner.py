# OSSS/ai/orchestration/graph_runner.py
from __future__ import annotations
from typing import Any, Dict, Awaitable, Callable

from OSSS.ai.orchestration.orchestrator import LangGraphOrchestrator

AsyncRunner = Callable[[str, Dict[str, Any]], Awaitable[Any]]

class GraphRunner:
    def __init__(self, *, orchestrator: LangGraphOrchestrator) -> None:
        self._orchestrator = orchestrator

    async def run(self, *, graph_id: str, query: str, config: Dict[str, Any]) -> Any:
        from OSSS.ai.orchestration.advanced_adapter import AdvancedOrchestratorAdapter

        if graph_id == "graph_default":
            return await self._orchestrator.run(query, config)

        adapter_map = {
            "graph_diagnostics": "diagnostics",
            "graph_builder": "builder",
            "graph_data_read": "data_read",
            "graph_data_views": "data_views",
            "graph_explain_deescalate": "explain_calm",
            "graph_clarify": "clarify",
        }
        graph_name = adapter_map.get(graph_id)
        if graph_name:
            return await AdvancedOrchestratorAdapter(graph=graph_name).run(query, config)

        # fallback
        return await self._orchestrator.run(query, config)
