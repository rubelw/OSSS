# src/OSSS/ai/orchestration/advanced_adapter.py
from __future__ import annotations

from typing import Any, Dict

from OSSS.ai.orchestration.orchestrator import LangGraphOrchestrator


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
        if self.graph not in {"diagnostics", "builder", "data_read", "data_views", "clarify", "explain_calm"}:
            raise ValueError(f"Unknown graph '{self.graph}' (no fallback allowed)")

    async def run(self, query: str, config: Dict[str, Any]) -> Any:
        # Make routing/debug metadata visible but don't require advanced modules
        if self.graph:

            if self.graph not in {"diagnostics", "builder", "data_read", "data_views", "clarify", "explain_calm"}:
                raise ValueError(f"Unknown graph '{self.graph}' (no fallback allowed)")

            config.setdefault("selected_graph", f"graph_{self.graph}")
            config.setdefault("routing_source", "advanced_adapter_shim")

        # LangGraphOrchestrator should honor config["agents"] if you implemented it there
        return await self._orch.run(query, config)