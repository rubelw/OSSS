# src/OSSS/ai/orchestration/advanced_adapter.py
from __future__ import annotations
from typing import Any, Dict, List, Optional

from OSSS.ai.context import AgentContext
from OSSS.ai.agents.base_agent import BaseAgent
from OSSS.ai.agents.registry import get_agent_registry

from OSSS.ai.orchestration.advanced.graph_engine import DependencyGraphEngine, DependencyNode
from OSSS.ai.orchestration.advanced.orchestrator import AdvancedOrchestrator, OrchestratorConfig

class AdvancedOrchestratorAdapter:
    """
    Adapter that provides a `run(query, config)` interface like LangGraphOrchestrator.
    """

    def __init__(self) -> None:
        self.registry = get_agent_registry()

    async def run(self, query: str, config: Dict[str, Any]) -> AgentContext:
        # 1) Determine which agents should run
        agent_names: List[str] = list(config.get("agents") or [])
        if not agent_names:
            # fallback: run default if nothing was specified
            agent_names = ["refiner", "historian", "final"]

        # 2) Build dependency graph engine with only those agents
        graph = DependencyGraphEngine()

        # Load agents from registry (you may want to pass llm/config to registry.create_agent)
        for name in agent_names:
            agent = self.registry.create_agent(name)  # if you need llm injection, do it here
            if agent is None:
                continue

            node = DependencyNode(
                agent_id=name,
                agent=agent,
                # optionally tune these:
                max_retries=int(config.get("agent_max_retries", 2)),
                timeout_ms=int(config.get("agent_timeout_ms", 30000)),
                resource_constraints=[],  # optional
            )
            graph.add_node(node)

        # 3) Add dependencies (either:
        #    A) from registry metadata, OR
        #    B) from your plan model (recommended), OR
        #    C) hard-coded per route)
        #
        # Option A: reuse registry dependencies (your orchestrator already does this)
        # graph.add_dependency(from_agent="refiner", to_agent="synthesis", ...)

        # 4) Create AdvancedOrchestrator with config
        orch_cfg = OrchestratorConfig(
            max_concurrent_agents=int(config.get("max_concurrent_agents", 4)),
            enable_failure_recovery=bool(config.get("enable_failure_recovery", True)),
            enable_resource_scheduling=bool(config.get("enable_resource_scheduling", True)),
            enable_dynamic_composition=bool(config.get("enable_dynamic_composition", False)),
        )

        orch = AdvancedOrchestrator(graph_engine=graph, config=orch_cfg)

        # 5) Initialize agents inside it (loads agents + validates graph)
        await orch.initialize_agents()

        # 6) Create context and run pipeline
        ctx = AgentContext(query=query)
        ctx.execution_state["execution_config"] = config  # keep your convention
        result_ctx = await orch.run(query)

        return result_ctx
