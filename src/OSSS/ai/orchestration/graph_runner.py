from __future__ import annotations
from typing import Any, Dict, Awaitable, Callable
from OSSS.ai.orchestration.orchestrator import LangGraphOrchestrator
from OSSS.ai.observability import get_logger

# Set up logger for this module
logger = get_logger(__name__)

AsyncRunner = Callable[[str, Dict[str, Any]], Awaitable[Any]]

class GraphRunner:
    def __init__(self, *, orchestrator: LangGraphOrchestrator) -> None:
        self._orchestrator = orchestrator
        logger.debug("GraphRunner initialized", extra={"orchestrator": str(orchestrator)})

    async def run(self, *, graph_id: str, query: str, config: Dict[str, Any]) -> Any:
        logger.info("Starting graph execution", extra={
            "graph_id": graph_id,
            "query": query[:100],  # logging the first 100 chars of the query for visibility
            "config": config,
        })

        from OSSS.ai.orchestration.advanced_adapter import AdvancedOrchestratorAdapter

        if graph_id == "graph_default":
            logger.debug(f"Running default graph: {graph_id}", extra={"query": query})
            result = await self._orchestrator.run(query, config)
            logger.info("Graph execution completed for graph_default", extra={"graph_id": graph_id, "result": result})
            return result

        # Map graph_id to a specific adapter
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
            logger.debug(f"Running graph with adapter: {graph_name}", extra={"graph_id": graph_id})
            result = await AdvancedOrchestratorAdapter(graph=graph_name).run(query, config)
            logger.info(f"Graph execution completed for {graph_name}", extra={"graph_id": graph_id, "result": result})
            return result

        # fallback to default orchestrator
        logger.warning(f"Graph ID {graph_id} not found in adapter map. Falling back to default orchestrator.", extra={"graph_id": graph_id})
        result = await self._orchestrator.run(query, config)
        logger.info("Fallback graph execution completed", extra={"graph_id": graph_id, "result": result})
        return result
