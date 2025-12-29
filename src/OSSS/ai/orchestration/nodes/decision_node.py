"""
Decision Node Implementation for OSSS.

This module implements the DecisionNode class which handles conditional
routing and flow control in the advanced node execution system.
"""

from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass  # Keep for any remaining dataclasses
import inspect

from pydantic import BaseModel, Field, ConfigDict
from OSSS.ai.agents.metadata import AgentMetadata
from OSSS.ai.events import emit_decision_made
from .base_advanced_node import BaseAdvancedNode, NodeExecutionContext

from OSSS.ai.observability import get_logger

logger = get_logger(__name__)


class DecisionCriteria(BaseModel):
    """
    Represents a single decision criterion.

    Migrated from dataclass to Pydantic BaseModel for enhanced validation,
    serialization, and integration with the OSSS Pydantic ecosystem.
    """

    name: str = Field(
        ...,
        description="Name/identifier of the decision criterion",
        min_length=1,
        max_length=100,
        json_schema_extra={"example": "complexity_check"},
    )
    evaluator: Callable[[NodeExecutionContext], float] = Field(
        ...,
        description="Function that evaluates the criterion against context",
    )
    weight: float = Field(
        default=1.0,
        description="Weight/importance of this criterion in decision making",
        ge=0.0,
        le=10.0,
        json_schema_extra={"example": 2.0},
    )
    threshold: float = Field(
        default=0.5,
        description="Threshold value for criterion to be considered passed",
        ge=0.0,
        le=1.0,
        json_schema_extra={"example": 0.8},
    )

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        arbitrary_types_allowed=True,  # For Callable evaluator function
    )

    def evaluate(self, context: NodeExecutionContext) -> float:
        """Evaluate this criterion against the context."""
        return self.evaluator(context)


class DecisionNode(BaseAdvancedNode):
    """
    Conditional routing decision point node.

    This node evaluates multiple criteria to make routing decisions,
    selecting the appropriate execution path based on the context.
    """

    def __init__(
        self,
        metadata: AgentMetadata,
        node_name: str,
        decision_criteria: List[DecisionCriteria],
        paths: Dict[str, List[str]],
    ) -> None:
        """
        Initialize the DecisionNode.

        Parameters
        ----------
        metadata : AgentMetadata
            The agent metadata containing multi-axis classification
        node_name : str
            Unique name for this node instance
        decision_criteria : List[DecisionCriteria]
            List of criteria to evaluate for decision making
        paths : Dict[str, List[str]]
            Mapping of path names to lists of agent/node names
        """
        super().__init__(metadata, node_name)

        if self.execution_pattern != "decision":
            raise ValueError(
                f"DecisionNode requires execution_pattern='decision', "
                f"got '{self.execution_pattern}'"
            )

        if not decision_criteria:
            raise ValueError("DecisionNode requires at least one decision criterion")

        if not paths:
            raise ValueError("DecisionNode requires at least one path")

        self.decision_criteria = decision_criteria
        self.paths = paths
        self.default_path = list(paths.keys())[0]  # First path is default

    async def execute(self, context: NodeExecutionContext) -> Dict[str, Any]:
        await self.pre_execute(context)

        # -------------------------------
        # (3) Fill missing root attributes from execution_state
        # -------------------------------
        try:
            exec_state = getattr(context, "execution_state", {}) or {}

            # Task classification fallback
            if not getattr(context, "task_classification", None):
                task_from_state = exec_state.get("task_classification")
                if task_from_state:
                    logger.debug(
                        "[DecisionNode:%s] populate missing task_classification from execution_state",
                        self.node_name,
                    )
                    context.task_classification = task_from_state

            # Cognitive classification fallback
            if not getattr(context, "cognitive_classification", None):
                cognitive_from_state = exec_state.get("cognitive_classification")
                if cognitive_from_state:
                    logger.debug(
                        "[DecisionNode:%s] populate missing cognitive_classification from execution_state",
                        self.node_name,
                    )
                    context.cognitive_classification = cognitive_from_state

        except Exception as e:
            logger.warning(
                "[DecisionNode:%s] fallback population failed: %s",
                self.node_name,
                e,
            )

        # -------------------------------
        # Introspection logging (unchanged)
        # -------------------------------
        try:
            exec_state = getattr(context, "execution_state", {}) or {}
            logger.debug(
                "[DecisionNode:%s] execute() context snapshot: "
                "task_classification=%s, cognitive_classification=%s, "
                "exec_state_keys=%s",
                self.node_name,
                getattr(context, "task_classification", None),
                getattr(context, "cognitive_classification", None),
                list(exec_state.keys()),
            )
        except Exception as e:
            logger.warning(
                "[DecisionNode:%s] failed to introspect context: %s",
                self.node_name,
                e,
            )

        # -------------------------------
        # Validation + decision eval
        # -------------------------------
        validation_errors = self.validate_context(context)
        if validation_errors:
            raise ValueError(
                f"Context validation failed: {', '.join(validation_errors)}"
            )

        decision_result = await self._evaluate_criteria(context)

        # Emit decision event (tolerate sync or async emitters)
        try:
            emit_result = emit_decision_made(
                workflow_id=context.workflow_id,
                decision_criteria=[c.name for c in self.decision_criteria],
                selected_path=decision_result["selected_path"],
                confidence_score=decision_result["confidence"],
                alternative_paths=decision_result["alternatives"],
                reasoning=decision_result["reasoning"],
                correlation_id=context.correlation_id,
            )
            if inspect.isawaitable(emit_result):
                await emit_result
        except Exception as e:
            logger.warning(
                "[DecisionNode:%s] failed to emit decision event: %s",
                self.node_name,
                e,
            )

        # Post-execution cleanup
        await self.post_execute(context, decision_result)

        return decision_result

    def can_handle(self, context: NodeExecutionContext) -> bool:
        task = (
            getattr(context, "task_classification", None)
            or context.execution_state.get("task_classification")
        )
        cognitive = (
            getattr(context, "cognitive_classification", None)
            or context.execution_state.get("cognitive_classification")
        )

        # Always return an explicit bool
        return bool(task and cognitive)

    async def _evaluate_criteria(self, context: NodeExecutionContext) -> Dict[str, Any]:
        """
        Evaluate all decision criteria and select the best path.

        Parameters
        ----------
        context : NodeExecutionContext
            The execution context

        Returns
        -------
        Dict[str, Any]
            Decision result with reasoning
        """
        # Evaluate each criterion
        criterion_scores: Dict[str, Any] = {}
        for criterion in self.decision_criteria:
            try:
                score = criterion.evaluate(context)
                criterion_scores[criterion.name] = {
                    "score": score,
                    "weight": criterion.weight,
                    "threshold": criterion.threshold,
                    "passed": score >= criterion.threshold,
                }
            except Exception as e:
                # Handle criteria evaluation failure gracefully
                criterion_scores[criterion.name] = {
                    "score": 0.0,  # Failed criteria get score 0
                    "weight": criterion.weight,
                    "threshold": criterion.threshold,
                    "passed": False,
                    "error": str(e),
                }

        # Calculate weighted scores for each path
        path_scores: Dict[str, float] = {}
        for path_name in self.paths:
            # Simple scoring: sum of weighted scores for passed criteria
            total_score = sum(
                scores["score"] * scores["weight"]
                for scores in criterion_scores.values()
                if scores["passed"]
            )
            path_scores[path_name] = total_score

        # Select the path with highest score
        selected_path = max(path_scores, key=lambda k: path_scores[k])

        total_weight = sum(c.weight for c in self.decision_criteria) or 1.0
        confidence_score = path_scores[selected_path] / total_weight

        # Build result
        return {
            "selected_path": selected_path,
            "selected_agents": self.paths[selected_path],
            "confidence": min(confidence_score, 1.0),  # Cap at 1.0
            "alternatives": [p for p in self.paths if p != selected_path],
            "reasoning": {
                "criterion_scores": criterion_scores,
                "path_scores": path_scores,
                "decision_basis": f"Selected '{selected_path}' with score {path_scores[selected_path]:.2f}",
            },
        }
