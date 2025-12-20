from __future__ import annotations

from typing import Any, Dict
from OSSS.ai.orchestration.orchestrator import LangGraphOrchestrator
from OSSS.ai.observability import get_logger

# Get logger for this module
logger = get_logger(__name__)


class AdvancedOrchestratorAdapter:
    """
    Compatibility adapter for older code paths that expected an "advanced" adapter.

    Since OSSS does not ship an OSSS.ai.orchestration.advanced.* implementation,
    this adapter simply delegates to the existing LangGraphOrchestrator.

    It preserves:
      - run(query, config) async interface
      - optional config["agents"] restriction
      - optional config["selected_graph"] metadata (ignored here unless orchestrator uses it)
    """

    def __init__(self, graph: str | None = None) -> None:
        self.graph = graph  # kept for API compatibility
        self._orch = LangGraphOrchestrator()

        logger.debug("Initializing AdvancedOrchestratorAdapter", extra={"graph": self.graph})

        if self.graph not in {"diagnostics", "builder", "data_read", "data_views", "clarify", "explain_calm"}:
            logger.error(f"Unknown graph '{self.graph}'", extra={"graph": self.graph})
            raise ValueError(f"Unknown graph '{self.graph}' (no fallback allowed)")

        logger.info(f"AdvancedOrchestratorAdapter initialized with graph: {self.graph}")

    async def run(self, query: str, config: Dict[str, Any]) -> Any:
        """
        Run the query through the LangGraphOrchestrator after ensuring configuration and graph selection.
        """
        logger.debug(f"Running AdvancedOrchestratorAdapter with query: {query[:100]}",
                     extra={"query": query[:100], "config": config})

        # Make routing/debug metadata visible but don't require advanced modules
        if self.graph:
            logger.debug(f"Checking if graph is valid: {self.graph}", extra={"graph": self.graph})

            if self.graph not in {"diagnostics", "builder", "data_read", "data_views", "clarify", "explain_calm"}:
                logger.error(f"Unknown graph '{self.graph}' in config", extra={"graph": self.graph})
                raise ValueError(f"Unknown graph '{self.graph}' (no fallback allowed)")

            # Set default config values for graph selection and routing
            config.setdefault("selected_graph", f"graph_{self.graph}")
            config.setdefault("routing_source", "advanced_adapter_shim")

            logger.debug(f"Config after setting defaults: {config}",
                         extra={"selected_graph": config.get("selected_graph"),
                                "routing_source": config.get("routing_source")})

        # Log before calling the orchestrator
        logger.info("Delegating to LangGraphOrchestrator for execution",
                    extra={"graph": self.graph, "query": query[:100]})

        # LangGraphOrchestrator should honor config["agents"] if you implemented it there
        result = await self._orch.run(query, config)

        logger.debug("AdvancedOrchestratorAdapter run completed", extra={"result_preview": str(result)[:100]})

        return result
