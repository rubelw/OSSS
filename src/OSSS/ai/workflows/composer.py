from typing import Dict, List, Any, Optional, Type, Callable, TYPE_CHECKING, Union
from dataclasses import dataclass
from abc import ABC, abstractmethod
import json
import time
import logging

from langgraph.graph import StateGraph
from OSSS.ai.observability import get_logger

logger = get_logger(__name__)

# Forward imports to resolve circular dependencies
if TYPE_CHECKING:
    from OSSS.ai.workflows.definition import (
        WorkflowDefinition,
        WorkflowNodeConfiguration,
        EdgeDefinition,
    )
    from OSSS.ai.workflows.executor import CompositionResult

# Plugin registry is a future feature - using type alias for now
from typing import Any

PluginRegistry = Any

# Import actual advanced node implementations with proper typing
from typing import Any, Type

# Define type aliases for node classes to handle import failures gracefully
DecisionNodeType: Type[Any]
AggregatorNodeType: Type[Any]
ValidatorNodeType: Type[Any]
TerminatorNodeType: Type[Any]

try:
    from OSSS.ai.orchestration.nodes.decision_node import DecisionNode
    from OSSS.ai.orchestration.nodes.aggregator_node import AggregatorNode
    from OSSS.ai.orchestration.nodes.validator_node import ValidatorNode
    from OSSS.ai.orchestration.nodes.terminator_node import TerminatorNode

    # Assign the real implementations
    DecisionNodeType = DecisionNode
    AggregatorNodeType = AggregatorNode
    ValidatorNodeType = ValidatorNode
    TerminatorNodeType = TerminatorNode

except ImportError:
    # Fallback placeholder classes for testing or incomplete installations
    class _PlaceholderDecisionNode:
        """Placeholder for DecisionNode class."""
        pass

    class _PlaceholderAggregatorNode:
        """Placeholder for AggregatorNode class."""
        pass

    class _PlaceholderValidatorNode:
        """Placeholder for ValidatorNode class."""
        pass

    class _PlaceholderTerminatorNode:
        """Placeholder for TerminatorNode class."""
        pass

    # Assign placeholders
    DecisionNodeType = _PlaceholderDecisionNode
    AggregatorNodeType = _PlaceholderAggregatorNode
    ValidatorNodeType = _PlaceholderValidatorNode
    TerminatorNodeType = _PlaceholderTerminatorNode


class WorkflowCompositionError(Exception):
    """Exception raised during workflow composition process."""

    def __init__(self, message: str, workflow_id: Optional[str] = None) -> None:
        super().__init__(message)
        self.workflow_id = workflow_id


def get_agent_class(agent_type: Optional[str]) -> Type[Any]:
    """Get agent class by type name."""
    logger.debug(f"Getting agent class for agent type: {agent_type}")
    
    from OSSS.ai.agents.refiner.agent import RefinerAgent
    from OSSS.ai.agents.critic.agent import CriticAgent
    from OSSS.ai.agents.historian.agent import HistorianAgent
    from OSSS.ai.agents.synthesis.agent import SynthesisAgent

    agent_map = {
        "refiner": RefinerAgent,
        "critic": CriticAgent,
        "historian": HistorianAgent,
        "synthesis": SynthesisAgent,
    }
    
    # Handle None case by defaulting to RefinerAgent
    if agent_type is None:
        logger.warning("No agent type provided, defaulting to RefinerAgent")
        return RefinerAgent
    
    agent_class = agent_map.get(agent_type, RefinerAgent)
    logger.info(f"Resolved agent class: {agent_class}")
    return agent_class


def create_agent_config(
    agent_type: str, config_dict: Optional[Dict[str, Any]] = None
) -> Any:
    """
    Create agent configuration object from workflow node configuration.
    """
    logger.debug(f"Creating agent config for agent type: {agent_type} with config: {config_dict}")
    
    from OSSS.ai.config.agent_configs import (
        RefinerConfig,
        CriticConfig,
        HistorianConfig,
        SynthesisConfig,
    )
    from OSSS.ai.config.config_mapper import ConfigMapper

    if not config_dict:
        logger.info(f"Returning default configuration for agent type: {agent_type}")
        config_classes = {
            "refiner": RefinerConfig,
            "critic": CriticConfig,
            "historian": HistorianConfig,
            "synthesis": SynthesisConfig,
        }
        config_class = config_classes.get(agent_type, RefinerConfig)
        return config_class()

    # Use ConfigMapper for dual format support
    try:
        config = ConfigMapper.validate_and_create_config(config_dict, agent_type)
        logger.info(f"Successfully created agent configuration for {agent_type}")
        return config
    except Exception as e:
        logger.error(f"Failed to create {agent_type} configuration: {e}")
        # Fallback to default configuration if mapping fails
        config_classes = {
            "refiner": RefinerConfig,
            "critic": CriticConfig,
            "historian": HistorianConfig,
            "synthesis": SynthesisConfig,
        }
        config_class = config_classes.get(agent_type, RefinerConfig)
        return config_class()


class NodeFactory:
    """
    Factory for creating node instances with plugin architecture preparation.
    """

    def __init__(self) -> None:
        logger.debug("NodeFactory initialized")
        self.plugin_registry: Optional[Any] = None

    def create_node(
        self, node_config: "WorkflowNodeConfiguration"
    ) -> Callable[..., Any]:
        """Create a node function from configuration."""
        logger.debug(f"Creating node for config: {node_config}")
        if node_config.category == "BASE":
            return self._create_base_node(node_config)
        elif node_config.category == "ADVANCED":
            return self._create_advanced_node(node_config)
        else:
            raise WorkflowCompositionError(
                f"Unsupported node category: {node_config.category}"
            )

    def _create_base_node(
        self, node_config: "WorkflowNodeConfiguration"
    ) -> Callable[..., Any]:
        """Create BASE agent node with actual LLM execution."""
        logger.debug(f"Creating base node for {node_config.node_type}")
        agent_class = get_agent_class(node_config.node_type)

        if agent_class is None:
            logger.error(f"Agent class not found for type: {node_config.node_type}")
            raise WorkflowCompositionError(
                f"Agent class not found for type: {node_config.node_type}"
            )

        async def node_func(state: Dict[str, Any]) -> Dict[str, Any]:
            try:
                # Import required modules
                from OSSS.ai.llm.openai import OpenAIChatLLM
                from OSSS.ai.config.openai_config import OpenAIConfig
                from OSSS.ai.context import AgentContext
                from OSSS.ai.workflows.prompt_loader import (
                    apply_prompt_configuration,
                )

                # Create LLM instance
                config = OpenAIConfig.load()
                llm = OpenAIChatLLM(
                    api_key=config.api_key, model=config.model, base_url=config.base_url
                )

                # Create agent configuration from workflow node configuration
                agent_config = create_agent_config(
                    node_config.node_type, node_config.config
                )

                # Create agent instance
                import inspect
                signature = inspect.signature(agent_class.__init__)
                params = list(signature.parameters.keys())

                if len(params) >= 3 and "config" in params:
                    agent = agent_class(llm, agent_config)
                else:
                    agent = agent_class(llm)

                # Convert LangGraph state to AgentContext
                context = AgentContext(query=state.get("query", ""))

                # Add existing agent outputs from state
                for key, value in state.items():
                    if key not in [
                        "query",
                        "successful_agents",
                        "failed_agents",
                        "errors",
                        "execution_metadata",
                    ]:
                        if isinstance(value, dict) and "output" in value:
                            context.add_agent_output(key, value["output"])
                        elif isinstance(value, str):
                            context.add_agent_output(key, value)

                # Execute the real agent
                result_context = await agent.run(context)

                agent_output = result_context.agent_outputs.get(agent.name, "")
                if not agent_output:
                    agent_outputs = list(result_context.agent_outputs.values())
                    agent_output = (
                        agent_outputs[-1]
                        if agent_outputs
                        else f"No output from {node_config.node_id}"
                    )

                logger.debug(f"Agent output for node {node_config.node_id}: {agent_output}")
                return {node_config.node_id: {"output": agent_output}}

            except Exception as e:
                logger.error(f"Error executing agent {node_config.node_id}: {e}")
                return {
                    node_config.node_id: {
                        "output": f"Fallback output from {node_config.node_id} (error: {str(e)})"
                    }
                }

        return node_func

    def _create_advanced_node(
        self, node_config: "WorkflowNodeConfiguration"
    ) -> Callable[..., Any]:
        """Create ADVANCED node (DecisionNode, AggregatorNode, etc.)."""
        logger.debug(f"Creating advanced node {node_config.node_type}")
        try:
            if node_config.node_type == "decision":
                return self._create_decision_node(node_config)
            elif node_config.node_type == "aggregator":
                return self._create_aggregator_node(node_config)
            elif node_config.node_type == "validator":
                return self._create_validator_node(node_config)
            elif node_config.node_type == "terminator":
                return self._create_terminator_node(node_config)
            else:
                logger.error(f"Unsupported advanced node type: {node_config.node_type}")
                raise WorkflowCompositionError(
                    f"Unsupported advanced node type: {node_config.node_type}"
                )
        except ImportError:
            return self._create_fallback_node(node_config)

    # Similar verbose logging will be added for the other methods
