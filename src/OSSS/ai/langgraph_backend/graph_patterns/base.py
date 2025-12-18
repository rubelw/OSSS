"""
Graph patterns for OSSS LangGraph backend.

This module defines different graph structures and patterns that can be used
for agent execution. Each pattern defines how agents are connected and the
execution flow between them.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class GraphPattern(ABC):
    """
    Abstract base class for graph patterns.

    Graph patterns define the structure and execution flow for different
    agent combinations and use cases.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Pattern name identifier."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable pattern description."""
        pass

    @abstractmethod
    def get_edges(self, agents: List[str]) -> List[Dict[str, str]]:
        """
        Get edge definitions for the given agents.

        Parameters
        ----------
        agents : List[str]
            List of agent names in the graph

        Returns
        -------
        List[Dict[str, str]]
            List of edge dictionaries with 'from' and 'to' keys
        """
        pass

    @abstractmethod
    def get_entry_point(self, agents: List[str]) -> Optional[str]:
        """
        Get the entry point agent for the graph.

        Parameters
        ----------
        agents : List[str]
            List of agent names in the graph

        Returns
        -------
        Optional[str]
            Name of the entry point agent, or None if no specific entry point
        """
        pass

    @abstractmethod
    def get_exit_points(self, agents: List[str]) -> List[str]:
        """
        Get the exit point agents for the graph.

        Parameters
        ----------
        agents : List[str]
            List of agent names in the graph

        Returns
        -------
        List[str]
            List of exit point agent names
        """
        pass

    def validate_agents(self, agents: List[str]) -> bool:
        """
        Validate that the given agents are compatible with this pattern.

        Parameters
        ----------
        agents : List[str]
            List of agent names to validate

        Returns
        -------
        bool
            True if agents are compatible with this pattern
        """
        return True  # Default: accept any agents

    def get_parallel_groups(self, agents: List[str]) -> List[List[str]]:
        """
        Get groups of agents that can execute in parallel.

        Parameters
        ----------
        agents : List[str]
            List of agent names in the graph

        Returns
        -------
        List[List[str]]
            List of agent groups that can execute in parallel
        """
        return []  # Default: no parallel groups


class StandardPattern(GraphPattern):
    """
    Standard 4-agent pattern: refiner → [critic, historian] → synthesis

    This is the default OSSS pattern where:
    1. Refiner processes the initial query
    2. Critic and Historian execute in parallel after Refiner
    3. Synthesis integrates all outputs for final analysis
    """

    @property
    def name(self) -> str:
        return "standard"

    @property
    def description(self) -> str:
        return "Standard 4-agent pattern: refiner → [critic, historian] → synthesis"

    def get_edges(self, agents: List[str]) -> List[Dict[str, str]]:
        """Get standard pattern edges (supports guard + data_view)."""
        agents_lower = [agent.lower() for agent in agents]

        def chain_to_end(chain: List[str]) -> List[Dict[str, str]]:
            if not chain:
                return []
            if len(chain) == 1:
                return [{"from": chain[0], "to": "END"}]
            chain_edges: List[Dict[str, str]] = []
            for i in range(len(chain) - 1):
                chain_edges.append({"from": chain[i], "to": chain[i + 1]})
            chain_edges.append({"from": chain[-1], "to": "END"})
            return chain_edges

        edges: List[Dict[str, str]] = []

        has_guard = "guard" in agents_lower
        has_data_view = "data_view" in agents_lower

        core = [a for a in agents_lower if a not in ("guard", "data_view")]
        recognized = {"refiner", "critic", "historian", "synthesis"}
        has_any_recognized = any(a in recognized for a in core)

        # If none of the standard agents are present, just chain (but keep guard first, data_view last)
        if not has_any_recognized:
            ordered = []
            if has_guard:
                ordered.append("guard")
            ordered.extend([a for a in core if a != "guard"])
            if has_data_view:
                ordered.append("data_view")
            return chain_to_end(ordered)

        # ---- Standard DAG behavior for classic agents ----
        # Build DAG among core recognized nodes.
        core_set = set(core)

        if "refiner" in core_set:
            # Refiner to Critic and Historian
            if "critic" in core_set:
                edges.append({"from": "refiner", "to": "critic"})
            if "historian" in core_set:
                edges.append({"from": "refiner", "to": "historian"})

            if "synthesis" in core_set:
                if "critic" in core_set:
                    edges.append({"from": "critic", "to": "synthesis"})
                if "historian" in core_set:
                    edges.append({"from": "historian", "to": "synthesis"})
                if not ("critic" in core_set or "historian" in core_set):
                    edges.append({"from": "refiner", "to": "synthesis"})
            else:
                # No synthesis: critic/historian terminal
                if "critic" in core_set:
                    edges.append({"from": "critic", "to": "END"})
                if "historian" in core_set:
                    edges.append({"from": "historian", "to": "END"})

        elif "critic" in core_set or "historian" in core_set:
            # No refiner: critic/historian feed synthesis if present, else terminal
            if "synthesis" in core_set:
                if "critic" in core_set:
                    edges.append({"from": "critic", "to": "synthesis"})
                if "historian" in core_set:
                    edges.append({"from": "historian", "to": "synthesis"})
            else:
                if "critic" in core_set:
                    edges.append({"from": "critic", "to": "END"})
                if "historian" in core_set:
                    edges.append({"from": "historian", "to": "END"})

        elif "synthesis" in core_set:
            # Synthesis-only case
            pass

        # ---- Add guard + data_view framing ----
        # Guard should precede the actual entrypoint if present.
        entry = self.get_entry_point(agents)  # will return guard if present with our update below
        if has_guard:
            # Determine the first "real" node after guard.
            after_guard = None
            if "refiner" in core_set:
                after_guard = "refiner"
            elif core:
                after_guard = core[0]
            elif has_data_view:
                after_guard = "data_view"

            if after_guard and after_guard != "guard":
                edges.append({"from": "guard", "to": after_guard})
            else:
                edges.append({"from": "guard", "to": "END"})

        # Determine terminal behavior:
        # If synthesis exists, synthesis is terminal of the core DAG.
        # If synthesis does not exist, terminals may already go to END above.
        if "synthesis" in core_set:
            if has_data_view:
                edges.append({"from": "synthesis", "to": "data_view"})
                edges.append({"from": "data_view", "to": "END"})
            else:
                edges.append({"from": "synthesis", "to": "END"})
        else:
            # No synthesis: if data_view exists, try to attach it to the last core agent
            if has_data_view:
                # Find likely terminal node among core
                terminal = None
                for candidate in ["critic", "historian", "refiner"]:
                    if candidate in core_set:
                        terminal = candidate
                        break
                if terminal:
                    edges.append({"from": terminal, "to": "data_view"})
                    edges.append({"from": "data_view", "to": "END"})
                else:
                    # No core terminals found; chain guard->data_view or data_view->END
                    if has_guard:
                        edges.append({"from": "guard", "to": "data_view"})
                    edges.append({"from": "data_view", "to": "END"})

        return edges if edges else chain_to_end(
            (["guard"] if has_guard else []) + core + (["data_view"] if has_data_view else [])
        )

    def get_entry_point(self, agents: List[str]) -> Optional[str]:
        agents_lower = [agent.lower() for agent in agents]

        # ✅ guard is preferred entry point if present
        if "guard" in agents_lower:
            return "guard"

        if "refiner" in agents_lower:
            return "refiner"

        return agents_lower[0] if agents_lower else None

    def get_exit_points(self, agents: List[str]) -> List[str]:
        agents_lower = [agent.lower() for agent in agents]

        if "data_view" in agents_lower:
            return ["data_view"]
        if "synthesis" in agents_lower:
            return ["synthesis"]

        exit_points = []
        if "critic" in agents_lower:
            exit_points.append("critic")
        if "historian" in agents_lower:
            exit_points.append("historian")

        return exit_points if exit_points else agents_lower

    def get_parallel_groups(self, agents: List[str]) -> List[List[str]]:
        agents_lower = [agent.lower() for agent in agents]

        parallel_group = []
        if "critic" in agents_lower:
            parallel_group.append("critic")
        if "historian" in agents_lower:
            parallel_group.append("historian")

        return [parallel_group] if len(parallel_group) > 1 else []


class ParallelPattern(GraphPattern):
    """
    Parallel pattern: Maximum parallelization where dependencies allow.

    This pattern attempts to execute as many agents in parallel as possible,
    respecting only essential dependencies.
    """

    @property
    def name(self) -> str:
        return "parallel"

    @property
    def description(self) -> str:
        return "Maximum parallelization pattern with minimal dependencies"

    def get_edges(self, agents: List[str]) -> List[Dict[str, str]]:
        edges: List[Dict[str, str]] = []
        agents_lower = [agent.lower() for agent in agents]

        has_guard = "guard" in agents_lower
        has_data_view = "data_view" in agents_lower
        has_synthesis = "synthesis" in agents_lower

        # nodes that can run before synthesis
        pre = [a for a in agents_lower if a not in ("guard", "synthesis", "data_view")]

        if has_synthesis:
            # guard -> all pre + synthesis (so nothing runs before guard)
            if has_guard:
                for a in pre + ["synthesis"]:
                    edges.append({"from": "guard", "to": a})
            # all pre feed into synthesis
            for a in pre:
                edges.append({"from": a, "to": "synthesis"})

            # terminal: synthesis -> data_view? -> END
            if has_data_view:
                edges.append({"from": "synthesis", "to": "data_view"})
                edges.append({"from": "data_view", "to": "END"})
            else:
                edges.append({"from": "synthesis", "to": "END"})
        else:
            # No synthesis: run everything after guard, then end or data_view last
            # If data_view exists, make it terminal and feed others into it.
            if has_data_view:
                if has_guard:
                    for a in pre:
                        edges.append({"from": "guard", "to": a})
                    edges.append({"from": "guard", "to": "data_view"})
                for a in pre:
                    edges.append({"from": a, "to": "data_view"})
                edges.append({"from": "data_view", "to": "END"})
            else:
                # terminal nodes go to END (guard just gates execution)
                if has_guard:
                    for a in pre:
                        edges.append({"from": "guard", "to": a})
                    edges.append({"from": "guard", "to": "END"})
                for a in pre:
                    edges.append({"from": a, "to": "END"})

        return edges

    def get_entry_point(self, agents: List[str]) -> Optional[str]:
        agents_lower = [agent.lower() for agent in agents]
        if "guard" in agents_lower:
            return "guard"
        return agents_lower[0] if agents_lower else None

    def get_exit_points(self, agents: List[str]) -> List[str]:
        agents_lower = [agent.lower() for agent in agents]
        if "data_view" in agents_lower:
            return ["data_view"]
        if "synthesis" in agents_lower:
            return ["synthesis"]
        return agents_lower

    def get_parallel_groups(self, agents: List[str]) -> List[List[str]]:
        """Get parallel execution groups."""
        agents_lower = [agent.lower() for agent in agents]

        # All non-synthesis agents can run in parallel
        parallel_agents = [agent for agent in agents_lower if agent != "synthesis"]
        return [parallel_agents] if len(parallel_agents) > 1 else []


class ConditionalPattern(GraphPattern):
    """
    Conditional pattern: Dynamic routing based on agent outputs.

    This pattern supports conditional execution where the next agent
    to execute depends on the output of previous agents.
    """

    @property
    def name(self) -> str:
        return "conditional"

    @property
    def description(self) -> str:
        return "Conditional routing pattern with dynamic execution flow"

    def get_edges(self, agents: List[str]) -> List[Dict[str, str]]:
        """Get conditional pattern edges."""
        # For now, implement as standard pattern
        # Future enhancement: add conditional routing logic
        standard_pattern = StandardPattern()
        return standard_pattern.get_edges(agents)

    def get_entry_point(self, agents: List[str]) -> Optional[str]:
        """Get entry point for conditional pattern."""
        agents_lower = [agent.lower() for agent in agents]
        return (
            "refiner"
            if "refiner" in agents_lower
            else (agents_lower[0] if agents_lower else None)
        )

    def get_exit_points(self, agents: List[str]) -> List[str]:
        """Get exit points for conditional pattern."""
        agents_lower = [agent.lower() for agent in agents]
        return ["synthesis"] if "synthesis" in agents_lower else agents_lower


class PatternRegistry:
    """
    Registry for managing available graph patterns.

    This class provides a centralized way to register, retrieve, and
    manage different graph patterns.
    """

    def __init__(self) -> None:
        """Initialize the pattern registry with default patterns."""
        self._patterns: Dict[str, GraphPattern] = {}

        # Register default patterns
        self.register_pattern(StandardPattern())
        self.register_pattern(ParallelPattern())
        self.register_pattern(ConditionalPattern())

        # Register enhanced patterns
        try:
            from .conditional import EnhancedConditionalPattern

            self.register_pattern(EnhancedConditionalPattern())
        except ImportError:
            # Enhanced conditional pattern not available
            pass

    def register_pattern(self, pattern: GraphPattern) -> None:
        """
        Register a new graph pattern.

        Parameters
        ----------
        pattern : GraphPattern
            Pattern to register
        """
        self._patterns[pattern.name] = pattern

    def get_pattern(self, name: str) -> Optional[GraphPattern]:
        """
        Get a pattern by name.

        Parameters
        ----------
        name : str
            Pattern name

        Returns
        -------
        Optional[GraphPattern]
            Pattern instance or None if not found
        """
        return self._patterns.get(name)

    def get_pattern_names(self) -> List[str]:
        """
        Get all registered pattern names.

        Returns
        -------
        List[str]
            List of pattern names
        """
        return list(self._patterns.keys())

    def list_patterns(self) -> Dict[str, str]:
        """
        Get all patterns with their descriptions.

        Returns
        -------
        Dict[str, str]
            Mapping of pattern names to descriptions
        """
        return {name: pattern.description for name, pattern in self._patterns.items()}

    def remove_pattern(self, name: str) -> bool:
        if name in self._patterns:
            del self._patterns[name]
            return True
        return False
