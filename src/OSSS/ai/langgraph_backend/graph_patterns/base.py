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
    Standard pattern: refiner → [data_query?, critic?, historian?] → synthesis
    """

    @property
    def name(self) -> str:
        return "standard"

    @property
    def description(self) -> str:
        return "Standard pattern: refiner → [data_query?, critic?, historian?] → synthesis"

    def get_entry_point(self, agents: List[str]) -> Optional[str]:
        agents_lower = [a.lower() for a in agents]
        if "refiner" in agents_lower:
            return "refiner"
        return agents_lower[0] if agents_lower else None

    def get_exit_points(self, agents: List[str]) -> List[str]:
        agents_lower = [a.lower() for a in agents]
        if "synthesis" in agents_lower:
            return ["synthesis"]

        exit_points: List[str] = []
        for a in ("data_query", "critic", "historian", "refiner"):
            if a in agents_lower:
                exit_points.append(a)

        return exit_points if exit_points else agents_lower

    def get_parallel_groups(self, agents: List[str]) -> List[List[str]]:
        agents_lower = [a.lower() for a in agents]
        group: List[str] = []
        for a in ("data_query", "critic", "historian"):
            if a in agents_lower:
                group.append(a)
        return [group] if len(group) > 1 else []

    def get_edges(self, agents: List[str]) -> List[Dict[str, str]]:
        edges: List[Dict[str, str]] = []
        agents_lower = [a.lower() for a in agents]

        has_refiner = "refiner" in agents_lower
        has_synthesis = "synthesis" in agents_lower

        branches = [a for a in ("data_query", "critic", "historian") if a in agents_lower]
        has_any_branch = bool(branches)

        # ---------------------------------------------------------------------
        # Preferred structure: refiner is entry
        # ---------------------------------------------------------------------
        if has_refiner:
            # refiner -> each branch that exists
            for b in branches:
                edges.append({"from": "refiner", "to": b})

            if has_synthesis:
                # each existing branch -> synthesis
                for b in branches:
                    edges.append({"from": b, "to": "synthesis"})

                # If no branches exist, connect refiner directly to synthesis
                if not has_any_branch:
                    edges.append({"from": "refiner", "to": "synthesis"})

                edges.append({"from": "synthesis", "to": "END"})
            else:
                # no synthesis: end each branch, or end refiner if nothing else
                if has_any_branch:
                    for b in branches:
                        edges.append({"from": b, "to": "END"})
                else:
                    edges.append({"from": "refiner", "to": "END"})

            return edges

        # ---------------------------------------------------------------------
        # Edge case: no refiner
        # ---------------------------------------------------------------------
        if branches:
            if has_synthesis:
                for b in branches:
                    edges.append({"from": b, "to": "synthesis"})
                edges.append({"from": "synthesis", "to": "END"})
            else:
                for b in branches:
                    edges.append({"from": b, "to": "END"})
            return edges

        # ---------------------------------------------------------------------
        # Synthesis-only
        # ---------------------------------------------------------------------
        if has_synthesis:
            edges.append({"from": "synthesis", "to": "END"})
            return edges

        # Nothing to connect
        return edges


class ParallelPattern(GraphPattern):
    """
    Parallel pattern: Maximum parallelization where dependencies allow.

    In this pattern, all non-synthesis agents can run in parallel and (if present)
    feed into synthesis. If synthesis is absent, all agents are terminal.
    """

    @property
    def name(self) -> str:
        return "parallel"

    @property
    def description(self) -> str:
        return "Maximum parallelization pattern with minimal dependencies"

    def get_entry_point(self, agents: List[str]) -> Optional[str]:
        # No single entry point in parallel pattern (LangGraph can run multiple starters)
        return None

    def get_exit_points(self, agents: List[str]) -> List[str]:
        agents_lower = [a.lower() for a in agents]
        return ["synthesis"] if "synthesis" in agents_lower else agents_lower

    def get_edges(self, agents: List[str]) -> List[Dict[str, str]]:
        edges: List[Dict[str, str]] = []
        agents_lower = [a.lower() for a in agents]

        if "synthesis" in agents_lower:
            # Every other agent feeds synthesis (including data_query if present)
            for a in agents_lower:
                if a != "synthesis":
                    edges.append({"from": a, "to": "synthesis"})
            edges.append({"from": "synthesis", "to": "END"})
        else:
            # No synthesis => all agents terminate
            for a in agents_lower:
                edges.append({"from": a, "to": "END"})

        return edges

    def get_parallel_groups(self, agents: List[str]) -> List[List[str]]:
        agents_lower = [a.lower() for a in agents]

        # All non-synthesis agents can run in parallel
        parallel_agents = [a for a in agents_lower if a != "synthesis"]
        return [parallel_agents] if len(parallel_agents) > 1 else []


class ConditionalPattern(GraphPattern):
    """
    Conditional pattern: Dynamic routing based on agent outputs.

    Today: we model it with the same DAG as StandardPattern. The *conditional*
    behavior comes from orchestration/routing selecting which agents are present
    (e.g., include data_query only for action intent).
    """

    @property
    def name(self) -> str:
        return "conditional"

    @property
    def description(self) -> str:
        return "Conditional routing pattern with dynamic execution flow"

    def get_entry_point(self, agents: List[str]) -> Optional[str]:
        agents_lower = [a.lower() for a in agents]
        if "refiner" in agents_lower:
            return "refiner"
        return agents_lower[0] if agents_lower else None

    def get_exit_points(self, agents: List[str]) -> List[str]:
        agents_lower = [a.lower() for a in agents]
        return ["synthesis"] if "synthesis" in agents_lower else agents_lower

    def get_edges(self, agents: List[str]) -> List[Dict[str, str]]:
        # For now: same structure as StandardPattern, but used when routing dynamically
        # includes/excludes agents like data_query.
        return StandardPattern().get_edges(agents)

    def get_parallel_groups(self, agents: List[str]) -> List[List[str]]:
        # Mirror StandardPattern’s parallelism: these can run after refiner
        agents_lower = [a.lower() for a in agents]
        group = [a for a in ("data_query", "critic", "historian") if a in agents_lower]
        return [group] if len(group) > 1 else []


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
        """
        Remove a pattern from the registry.

        Parameters
        ----------
        name : str
            Pattern name to remove

        Returns
        -------
        bool
            True if pattern was removed, False if not found
        """
        if name in self._patterns:
            del self._patterns[name]
            return True
        return False