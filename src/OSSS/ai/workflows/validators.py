from __future__ import annotations

from typing import List, Dict, Set, Any, Optional, Tuple
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

from OSSS.ai.workflows.definition import (
    WorkflowDefinition,
    WorkflowNodeConfiguration,
    FlowDefinition,
    EdgeDefinition,
    NodeCategory,
    AdvancedNodeType,
    BaseNodeType,
)
from OSSS.ai.validation.base import (
    WorkflowValidationIssue,
    ValidationSeverity,
)
from OSSS.ai.observability import get_logger

logger = get_logger(__name__)

class WorkflowValidationLevel(str, Enum):
    """Validation strictness levels."""
    BASIC = "basic"  # Essential workflow integrity checks
    STANDARD = "standard"  # Standard validation with business rules
    STRICT = "strict"  # Comprehensive validation with all checks
    PEDANTIC = "pedantic"  # Maximum validation including style checks


class ValidationIssueType(str, Enum):
    """Types of validation issues."""
    ERROR = "error"  # Critical issues that prevent execution
    WARNING = "warning"  # Issues that may cause problems
    INFO = "info"  # Informational suggestions
    STYLE = "style"  # Style and convention recommendations


# Use WorkflowValidationIssue from base module with backward compatibility alias
ValidationIssue = WorkflowValidationIssue


class WorkflowValidationResult(BaseModel):
    """Comprehensive validation result with detailed issue tracking."""
    is_valid: bool = Field(description="Whether the workflow passed validation")
    validation_level: WorkflowValidationLevel = Field(description="Level of validation performed")
    issues: List[WorkflowValidationIssue] = Field(default_factory=list, description="List of validation issues found")
    summary: Dict[str, int] = Field(default_factory=dict, description="Summary counts by issue type")
    workflow_metadata: Dict[str, Any] = Field(default_factory=dict, description="Workflow analysis metadata")
    model_config = ConfigDict(extra="forbid")

    def has_errors(self) -> bool:
        """Check if validation found any errors."""
        return any(
            issue.issue_type == ValidationIssueType.ERROR for issue in self.issues
        )

    def has_warnings(self) -> bool:
        """Check if validation found any warnings."""
        return any(
            issue.issue_type == ValidationIssueType.WARNING for issue in self.issues
        )

    def get_issues_by_type(self, issue_type: ValidationIssueType) -> List[WorkflowValidationIssue]:
        """Get all issues of a specific type."""
        return [issue for issue in self.issues if issue.issue_type == issue_type.value]

    def get_highest_severity(self) -> int:
        """Get the highest severity level found."""
        if not self.issues:
            return 0
        return max(issue.get_numeric_severity() for issue in self.issues)


class WorkflowValidator(BaseModel):
    """
    Comprehensive Pydantic-based workflow validator.

    Provides schema-based validation enhanced with business logic validation
    for complex workflow constraints, dependencies, and best practices.
    """
    config: WorkflowValidationConfig = Field(
        default_factory=WorkflowValidationConfig, description="Validation configuration"
    )
    model_config = ConfigDict(extra="forbid")

    def _create_issue(
        self,
        issue_type: ValidationIssueType,
        severity_level: int,
        message: str,
        location: str,
        rule_id: str,
        suggestion: Optional[str] = None,
    ) -> WorkflowValidationIssue:
        """Helper to create ValidationIssue with proper severity mapping."""
        severity_map = {
            ValidationIssueType.ERROR: ValidationSeverity.ERROR,
            ValidationIssueType.WARNING: ValidationSeverity.WARNING,
            ValidationIssueType.INFO: ValidationSeverity.INFO,
            ValidationIssueType.STYLE: ValidationSeverity.STYLE,
        }

        issue = WorkflowValidationIssue(
            severity=severity_map[issue_type],
            severity_level=severity_level,
            issue_type=issue_type.value,
            message=message,
            location=location,
            rule_id=rule_id,
            suggestion=suggestion,
        )

        # Log the issue creation for verbose tracking
        logger.debug("Created validation issue", extra={
            "issue_type": issue_type.value,
            "severity_level": severity_level,
            "message": message,
            "location": location,
            "rule_id": rule_id,
            "suggestion": suggestion,
        })

        return issue

    def validate_workflow(self, workflow: WorkflowDefinition) -> WorkflowValidationResult:
        """
        Perform comprehensive validation of a workflow definition.

        Parameters
        ----------
        workflow : WorkflowDefinition
            The workflow to validate

        Returns
        -------
        ValidationResult
            Comprehensive validation result with all issues found
        """
        issues: List[WorkflowValidationIssue] = []
        logger.info(f"Starting validation for workflow: {workflow.workflow_id}", extra={
            "workflow_name": workflow.name,
            "workflow_id": workflow.workflow_id,
        })

        # Basic structural validation (always performed)
        logger.debug("Validating basic structure")
        issues.extend(self._validate_basic_structure(workflow))

        # Standard validation
        if self.config.validation_level in [
            WorkflowValidationLevel.STANDARD,
            WorkflowValidationLevel.STRICT,
            WorkflowValidationLevel.PEDANTIC,
        ]:
            logger.debug("Performing standard validation")
            issues.extend(self._validate_flow_integrity(workflow))
            issues.extend(self._validate_node_references(workflow))
            issues.extend(self._validate_business_rules(workflow))

        # Strict validation
        if self.config.validation_level in [
            WorkflowValidationLevel.STRICT,
            WorkflowValidationLevel.PEDANTIC,
        ]:
            logger.debug("Performing strict validation")
            issues.extend(self._validate_advanced_constraints(workflow))
            issues.extend(self._validate_performance_considerations(workflow))

        # Pedantic validation
        if self.config.validation_level == WorkflowValidationLevel.PEDANTIC:
            logger.debug("Performing pedantic validation")
            issues.extend(self._validate_style_conventions(workflow))
            issues.extend(self._validate_best_practices(workflow))

        # Compute summary
        summary = {
            "errors": len([i for i in issues if i.issue_type == ValidationIssueType.ERROR]),
            "warnings": len([i for i in issues if i.issue_type == ValidationIssueType.WARNING]),
            "info": len([i for i in issues if i.issue_type == ValidationIssueType.INFO]),
            "style": len([i for i in issues if i.issue_type == ValidationIssueType.STYLE]),
        }

        # Determine if valid
        has_errors = summary["errors"] > 0
        has_warnings = summary["warnings"] > 0
        is_valid = not has_errors and (
            not self.config.fail_on_warnings or not has_warnings
        )

        logger.info("Validation completed", extra={
            "is_valid": is_valid,
            "validation_level": self.config.validation_level,
            "issues_found": len(issues),
            "summary": summary,
        })

        # Generate metadata
        workflow_metadata = {
            "node_count": len(workflow.nodes),
            "edge_count": len(workflow.flow.edges),
            "terminal_node_count": len(workflow.flow.terminal_nodes) if workflow.flow.terminal_nodes else 0,
            "max_possible_depth": self._calculate_max_depth(workflow),
            "has_cycles": self._has_cycles(workflow),
            "node_types": list(set(node.node_type for node in workflow.nodes)),
            "categories": list(set(node.category for node in workflow.nodes)),
        }

        return WorkflowValidationResult(
            is_valid=is_valid,
            validation_level=self.config.validation_level,
            issues=issues,
            summary=summary,
            workflow_metadata=workflow_metadata,
        )

    def _validate_basic_structure(self, workflow: WorkflowDefinition) -> List[WorkflowValidationIssue]:
        """Validate basic workflow structure."""
        issues: List[WorkflowValidationIssue] = []
        logger.debug(f"Validating basic structure for workflow {workflow.workflow_id}")

        # Check required fields
        if not workflow.name or not workflow.name.strip():
            issues.append(self._create_issue(
                issue_type=ValidationIssueType.ERROR,
                severity_level=10,
                message="Workflow name is required and cannot be empty",
                location="workflow.name",
                suggestion="Provide a descriptive name for the workflow",
                rule_id="STRUCT_001",
            ))

        if not workflow.workflow_id or not workflow.workflow_id.strip():
            issues.append(self._create_issue(
                issue_type=ValidationIssueType.ERROR,
                severity_level=10,
                message="Workflow ID is required and cannot be empty",
                location="workflow.workflow_id",
                suggestion="Provide a unique identifier for the workflow",
                rule_id="STRUCT_002",
            ))

        # Check nodes exist
        if not workflow.nodes:
            issues.append(self._create_issue(
                issue_type=ValidationIssueType.ERROR,
                severity_level=10,
                message="Workflow must contain at least one node",
                location="workflow.nodes",
                suggestion="Add at least one node to the workflow",
                rule_id="STRUCT_003",
            ))

        # Check flow exists
        if not workflow.flow:
            issues.append(self._create_issue(
                issue_type=ValidationIssueType.ERROR,
                severity_level=10,
                message="Workflow must have a flow definition",
                location="workflow.flow",
                suggestion="Define the execution flow for the workflow",
                rule_id="STRUCT_004",
            ))

        return issues

    # ... other validation methods remain unchanged, but should also log with logger.debug/info/warning/error as appropriate
