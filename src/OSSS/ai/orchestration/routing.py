"""
Routing utilities for LangGraph conditional execution.

This module defines a collection of routing primitives used by LangGraph-style
directed acyclic graphs (DAGs) to determine the *next node to execute* at runtime.

Routers encapsulate branching logic based on:
- Execution state (success/failure)
- Agent output content
- Retry and circuit-breaker behavior
- Dependency satisfaction between agents
- Pipeline stage progression

All routers implement a common `RoutingFunction` interface, allowing them
to be treated uniformly by the graph builder and executor.
"""

from typing import Callable, Dict, List, Optional, Set
from abc import ABC, abstractmethod
import re
from OSSS.ai.context import AgentContext

HISTORY_TRIGGERS = re.compile(
    r"\b(history|historical|timeline|previous|earlier|last time|recap|what happened|"
    r"prior|meeting notes|notes|minutes|decision|context|background)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Route-lock: DB query heuristic routing (NO LLM)
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(r"[a-z0-9_]+")
ACTION_HINTS = re.compile(r"\b(list|show|get|find|lookup|search|count|who|what|which)\b", re.I)

# These are *domain* entities users ask for that usually live in the DB
# (separate from table names, since users won't always use canonical table names).
SCHOOL_ENTITIES: Set[str] = {
    "teacher",
    "teachers",
    "student",
    "students",
    "staff",
    "school",
    "schools",
    "course",
    "courses",
    "section",
    "sections",
    "board",
    "member",
    "members",
    "guardian",
    "guardians",
}


DB_TABLES: Set[str] = {
    "academic_terms",
    "accommodations",
    "activities",
    "addresses",
    "agenda_item_approvals",
    "agenda_item_files",
    "agenda_items",
    "agenda_workflow_steps",
    "agenda_workflows",
    "alembic_version",
    "alignments",
    "ap_vendors",
    "approvals",
    "asset_parts",
    "assets",
    "assignment_categories",
    "assignments",
    "attendance",
    "attendance_codes",
    "attendance_daily_summary",
    "attendance_events",
    "audit_logs",
    "behavior_codes",
    "behavior_interventions",
    "bell_schedules",
    "buildings",
    "bus_routes",
    "bus_stop_times",
    "bus_stops",
    "calendar_days",
    "calendars",
    "channels",
    "class_ranks",
    "comm_search_index",
    "committees",
    "compliance_records",
    "consents",
    "consequence_types",
    "consequences",
    "contacts",
    "course_prerequisites",
    "course_sections",
    "courses",
    "curricula",
    "curriculum_units",
    "curriculum_versions",
    "data_quality_issues",
    "data_sharing_agreements",
    "deduction_codes",
    "deliveries",
    "department_position_index",
    "departments",
    "document_activity",
    "document_links",
    "document_notifications",
    "document_permissions",
    "document_search_index",
    "document_versions",
    "documents",
    "earning_codes",
    "education_associations",
    "ell_plans",
    "embeds",
    "emergency_contacts",
    "employee_deductions",
    "employee_earnings",
    "entity_tags",
    "evaluation_assignments",
    "evaluation_cycles",
    "evaluation_files",
    "evaluation_questions",
    "evaluation_reports",
    "evaluation_responses",
    "evaluation_sections",
    "evaluation_signoffs",
    "evaluation_templates",
    "events",
    "export_runs",
    "external_ids",
    "facilities",
    "family_portal_access",
    "feature_flags",
    "fees",
    "files",
    "final_grades",
    "fiscal_periods",
    "fiscal_years",
    "floors",
    "folders",
    "frameworks",
    "gl_account_balances",
    "gl_account_segments",
    "gl_accounts",
    "gl_segment_values",
    "gl_segments",
    "goals",
    "google_accounts",
    "governing_bodies",
    "gpa_calculations",
    "grade_levels",
    "grade_scale_bands",
    "grade_scales",
    "gradebook_entries",
    "grading_periods",
    "guardians",
    "health_profiles",
    "hr_employees",
    "hr_position_assignments",
    "hr_positions",
    "iep_plans",
    "immunization_records",
    "immunizations",
    "incident_participants",
    "incidents",
    "initiatives",
    "invoices",
    "journal_batches",
    "journal_entries",
    "journal_entry_lines",
    "kpi_datapoints",
    "kpis",
    "leases",
    "library_checkouts",
    "library_fines",
    "library_holds",
    "library_items",
    "maintenance_requests",
    "meal_accounts",
    "meal_eligibility_statuses",
    "meal_transactions",
    "medication_administrations",
    "medications",
    "meeting_documents",
    "meeting_files",
    "meeting_permissions",
    "meeting_publications",
    "meeting_search_index",
    "meetings",
    "memberships",
    "message_recipients",
    "messages",
    "meters",
    "minutes",
    "motions",
    "move_orders",
    "notifications",
    "nurse_visits",
    "objectives",
    "order_line_items",
    "orders",
    "organizations",
    "pages",
    "part_locations",
    "parts",
    "pay_periods",
    "paychecks",
    "payments",
    "payroll_runs",
    "periods",
    "permissions",
    "person_addresses",
    "person_contacts",
    "personal_notes",
    "persons",
    "plan_alignments",
    "plan_assignments",
    "plan_filters",
    "plan_search_index",
    "plans",
    "pm_plans",
    "pm_work_generators",
    "policies",
    "policy_approvals",
    "policy_comments",
    "policy_files",
    "policy_legal_refs",
    "policy_publications",
    "policy_search_index",
    "policy_versions",
    "policy_workflow_steps",
    "policy_workflows",
    "post_attachments",
    "posts",
    "project_tasks",
    "projects",
    "proposal_documents",
    "proposal_reviews",
    "proposal_standard_map",
    "proposals",
    "publications",
    "report_cards",
    "requirements",
    "resolutions",
    "retention_rules",
    "review_requests",
    "review_rounds",
    "reviewers",
    "reviews",
    "role_permissions",
    "roles",
    "rooms",
    "round_decisions",
    "scan_requests",
    "scan_results",
    "schools",
    "scorecard_kpis",
    "scorecards",
    "section504_plans",
    "section_meetings",
    "section_room_assignments",
    "sis_import_jobs",
    "space_reservations",
    "spaces",
    "special_education_cases",
    "staff",
    "standardized_tests",
    "standards",
    "state_reporting_snapshots",
    "states",
    "student_guardians",
    "student_program_enrollments",
    "student_school_enrollments",
    "student_section_enrollments",
    "student_transportation_assignments",
    "students",
    "subjects",
    "subscriptions",
    "tags",
    "teacher_section_assignments",
    "test_administrations",
    "test_results",
    "ticket_scans",
    "ticket_types",
    "tickets",
    "transcript_lines",
    "unit_standard_map",
    "user_accounts",
    "users",
    "vendors",
    "votes",
    "waivers",
    "warranties",
    "webhooks",
    "work_order_parts",
    "work_order_tasks",
    "work_order_time_logs",
    "work_orders",
}

DISTRICT_ALIASES = {"dcg"}  # add more as needed

# RouteKey -> planned agent plans
# (Used by OrchestrationAPI / higher-level router to compute planned_agents.)
#
ACTION_PLAN: List[str] = ["refiner", "data_query", "synthesis"]
READ_PLAN: List[str]   = ["refiner", "critic", "synthesis"]  # optional (if you want a lighter non-action path)
ANALYSIS_PLAN: List[str] = ["refiner", "historian", "critic", "synthesis"]

def planned_agents_for_route_key(route_key: str) -> List[str]:
    """
    Canonical mapping from a route_key (e.g. 'action') to a planned agent list.
    Keep this here so anything that sets execution_state['route_key']
    has a single source of truth for downstream planning.
    """
    k = (route_key or "").strip().lower()
    if k == "action":
        return ACTION_PLAN
    # choose one:
    return ANALYSIS_PLAN
    # or, if you prefer a lighter non-action path:
    # return READ_PLAN


def should_route_to_data_query(user_text: str) -> bool:
    """
    Heuristic to decide if a user request should bypass refiner/critic/synthesis
    and go directly to data_query.
    """
    t = (user_text or "").lower()
    tokens = set(_WORD_RE.findall(t))

    # Exact table mentions are a strong signal
    if DB_TABLES.intersection(tokens):
        return True

    # District alias + school entity
    if tokens.intersection(DISTRICT_ALIASES) and tokens.intersection(SCHOOL_ENTITIES):
        return True

    # Common retrieval verbs + school entity
    # e.g. "list dcg teachers", "show students", "find courses", etc.
    if ACTION_HINTS.search(t) and tokens.intersection(SCHOOL_ENTITIES):
        return True

    return False


def should_run_historian(query: str) -> bool:
    q = (query or "").strip()

    # If this is clearly a DB query, historian should never run
    # (keeps action path fast + avoids irrelevant analysis agents).
    if should_route_to_data_query(q):
        return False

    # Very short queries never need historian
    if len(q) < 40:
        return False

    # Explicit historical intent
    if HISTORY_TRIGGERS.search(q):
        return True

    # Explicit doc usage
    ql = q.lower()
    if "notes" in ql or "docs" in ql:
        return True

    return False


class RoutingFunction(ABC):
    """
    Abstract base class for all routing functions.

    A routing function is a callable object that:
    1. Inspects the current AgentContext
    2. Returns the *name of the next graph node* to execute

    This abstraction allows different routing strategies to be plugged
    into LangGraph conditional edges without coupling graph execution
    logic to business-specific rules.
    """

    @abstractmethod
    def __call__(self, context: AgentContext) -> str:
        """
        Determine the next node based on execution context.

        Parameters
        ----------
        context : AgentContext
            The current execution context, containing:
            - execution_state (success flags, retries, pipeline stage, etc.)
            - agent_outputs
            - successful_agents / failed_agents

        Returns
        -------
        str
            The name of the next node to execute in the graph
        """
        raise NotImplementedError

    @abstractmethod
    def get_possible_targets(self) -> List[str]:
        """
        Return all possible node names this router may emit.

        This is primarily used for:
        - Graph validation
        - Static visualization
        - Detecting unreachable nodes
        """
        raise NotImplementedError


class DBQueryRouter(RoutingFunction):
    """
    Route-lock router that decides whether to short-circuit to data_query.

    If it chooses data_query, it writes:
      execution_state["route"] = "<data_query_target>"
      execution_state["route_locked"] = True

    This prevents later routing stages from overriding the decision.
    """

    def __init__(self, data_query_target: str, default_target: str) -> None:
        self.data_query_target = data_query_target
        self.default_target = default_target

    def __call__(self, context: AgentContext) -> str:
        # If already locked, honor it and do not recompute
        if context.execution_state.get("route_locked"):
            # Ensure route_key is always present if someone locked earlier
            context.execution_state.setdefault(
                "route_key",
                "action"
                if context.execution_state.get("route") == self.data_query_target
                else "informational",
            )
            return context.execution_state.get("route", self.data_query_target)

        # ✅ Exact, canonical source of the incoming user request:
        query = (context.query or "").strip()

        if should_route_to_data_query(query):
            context.execution_state["route"] = self.data_query_target
            context.execution_state["route_locked"] = True
            # Canonical switch key for LangGraph add_conditional_edges(...)
            context.execution_state["route_key"] = "action"
            # Breadcrumb for debugging (shows why we routed)
            context.execution_state["route_reason"] = "db_query_heuristic"
            return self.data_query_target

        context.execution_state["route"] = self.default_target
        context.execution_state["route_locked"] = False
        context.execution_state["route_key"] = "informational"
        context.execution_state["route_reason"] = "default"
        return self.default_target

    def get_possible_targets(self) -> List[str]:
        return [self.data_query_target, self.default_target]


class ConditionalRouter(RoutingFunction):
    """
    Router that selects the next node based on ordered condition checks.

    Conditions are evaluated *in order*, and the first condition that
    returns True determines the routing target.

    This is the most generic form of conditional routing.
    """

    def __init__(
        self,
        conditions: List[tuple[Callable[[AgentContext], bool], str]],
        default: str,
    ) -> None:
        """
        Initialize the conditional router.

        Parameters
        ----------
        conditions : List[tuple[Callable, str]]
            Ordered list of:
            - predicate functions that accept AgentContext
            - corresponding target node names
        default : str
            Fallback node when no condition matches
        """
        self.conditions = conditions
        self.default = default

    def __call__(self, context: AgentContext) -> str:
        """
        Evaluate each condition in order and return the first matching target.

        If no conditions match, the default target is returned.
        """
        for condition_func, target_node in self.conditions:
            if condition_func(context):
                return target_node

        return self.default

    def get_possible_targets(self) -> List[str]:
        """
        Return all possible targets, including the default.

        Duplicates are removed to keep the list deterministic.
        """
        targets = [target for _, target in self.conditions]
        targets.append(self.default)
        return list(set(targets))


class SuccessFailureRouter(RoutingFunction):
    """
    Router that branches based on whether the last agent execution succeeded.

    This router assumes the execution engine records a boolean
    `last_agent_success` flag in `context.execution_state`.
    """

    def __init__(self, success_target: str, failure_target: str) -> None:
        """
        Parameters
        ----------
        success_target : str
            Node to route to when the last agent succeeded
        failure_target : str
            Node to route to when the last agent failed
        """
        self.success_target = success_target
        self.failure_target = failure_target

    def __call__(self, context: AgentContext) -> str:
        """
        Inspect execution state and route accordingly.

        Defaults to success if the flag is missing, allowing
        optimistic execution for agents that do not report status.
        """
        if context.execution_state.get("last_agent_success", True):
            return self.success_target

        return self.failure_target

    def get_possible_targets(self) -> List[str]:
        """Return both success and failure targets."""
        return [self.success_target, self.failure_target]


class OutputBasedRouter(RoutingFunction):
    """
    Router that inspects agent output text to determine routing.

    Useful for:
    - LLM-based intent detection
    - Keyword-based branching
    - Simple semantic routing without embeddings
    """

    def __init__(self, output_patterns: Dict[str, str], default: str) -> None:
        """
        Parameters
        ----------
        output_patterns : Dict[str, str]
            Mapping of substring patterns (lowercased) to target nodes
        default : str
            Target node if no patterns match
        """
        self.output_patterns = output_patterns
        self.default = default

    def __call__(self, context: AgentContext) -> str:
        """
        Route based on the most recent agent's output content.

        The router:
        1. Finds the last agent that produced output
        2. Performs case-insensitive substring matching
        3. Returns the first matching target
        """
        if context.agent_outputs:
            last_agent = list(context.agent_outputs.keys())[-1]
            last_output = context.agent_outputs[last_agent]

            for pattern, target in self.output_patterns.items():
                if pattern.lower() in last_output.lower():
                    return target

        return self.default

    def get_possible_targets(self) -> List[str]:
        """Return all pattern targets plus the default."""
        targets = list(self.output_patterns.values())
        targets.append(self.default)
        return list(set(targets))


# ---------------------------------------------------------------------------
# Simple routing factory helpers
# ---------------------------------------------------------------------------

def always_continue_to(target: str) -> RoutingFunction:
    """
    Create a router that always routes to the same node.

    Useful for:
    - Terminal edges
    - Explicit graph transitions
    - Placeholder routing during graph construction
    """

    class AlwaysRouter(RoutingFunction):
        def __call__(self, context: AgentContext) -> str:
            return target

        def get_possible_targets(self) -> List[str]:
            return [target]

    return AlwaysRouter()


def route_on_query_type(patterns: Dict[str, str], default: str) -> RoutingFunction:
    """
    Create an output-based router specialized for query classification.
    """
    return OutputBasedRouter(patterns, default)


def route_on_success_failure(
    success_target: str, failure_target: str
) -> RoutingFunction:
    """
    Create a router that branches based on execution success.
    """
    return SuccessFailureRouter(success_target, failure_target)


class FailureHandlingRouter(RoutingFunction):
    """
    Router implementing retry logic and an optional circuit breaker.

    This router supports:
    - Automatic retries
    - Failure counting
    - Circuit breaker behavior to prevent infinite loops
    """

    def __init__(
        self,
        success_target: str,
        failure_target: str,
        retry_target: Optional[str] = None,
        max_failures: int = 3,
        enable_circuit_breaker: bool = True,
    ) -> None:
        """
        Parameters
        ----------
        success_target : str
            Node to route to on success
        failure_target : str
            Node to route to when retries are exhausted
        retry_target : str, optional
            Node used for retry attempts (defaults to failure_target)
        max_failures : int
            Maximum number of failures before circuit opens
        enable_circuit_breaker : bool
            Whether to permanently short-circuit after repeated failures
        """
        self.success_target = success_target
        self.failure_target = failure_target
        self.retry_target = retry_target or failure_target
        self.max_failures = max_failures
        self.enable_circuit_breaker = enable_circuit_breaker

        # Internal state (per-router instance)
        self.failure_count = 0
        self.circuit_open = False

    def __call__(self, context: AgentContext) -> str:
        """
        Route based on execution outcome and failure history.

        This method mutates execution_state to track retry counts.
        """
        last_agent_success = context.execution_state.get("last_agent_success", True)

        if last_agent_success:
            # Reset all failure-related state on success
            self.failure_count = 0
            self.circuit_open = False
            return self.success_target

        # Failure path
        self.failure_count += 1

        # Circuit breaker check
        if self.enable_circuit_breaker and self.failure_count >= self.max_failures:
            self.circuit_open = True
            return self.failure_target

        # Retry handling
        current_retry_count = context.execution_state.get("retry_count", 0)
        if current_retry_count < self.max_failures and not self.circuit_open:
            context.execution_state["retry_count"] = current_retry_count + 1
            return self.retry_target

        return self.failure_target

    def get_possible_targets(self) -> List[str]:
        """Return all nodes this router may emit."""
        targets = [self.success_target, self.failure_target]
        if self.retry_target not in targets:
            targets.append(self.retry_target)
        return targets

    def reset_failure_state(self) -> None:
        """
        Reset internal failure tracking.

        Intended for reuse across independent graph executions.
        """
        self.failure_count = 0
        self.circuit_open = False


class AgentDependencyRouter(RoutingFunction):
    """
    Router that waits for dependent agents to complete.

    This router supports fan-in style workflows where downstream
    nodes must wait until prerequisite agents have succeeded.
    """

    def __init__(
        self,
        dependency_map: Dict[str, List[str]],
        success_target: str,
        wait_target: str,
        failure_target: str,
    ) -> None:
        """
        Parameters
        ----------
        dependency_map : Dict[str, List[str]]
            Mapping of target nodes to required agent dependencies
        success_target : str
            Node to route to when all dependencies succeed
        wait_target : str
            Node to route to while dependencies are pending
        failure_target : str
            Node to route to if any dependency fails
        """
        self.dependency_map = dependency_map
        self.success_target = success_target
        self.wait_target = wait_target
        self.failure_target = failure_target

    def __call__(self, context: AgentContext) -> str:
        """
        Route based on dependency completion state.
        """
        dependencies = self.dependency_map.get(self.success_target, [])

        for dependency in dependencies:
            if dependency not in context.successful_agents:
                if dependency in context.failed_agents:
                    return self.failure_target
                return self.wait_target

        return self.success_target

    def get_possible_targets(self) -> List[str]:
        return [self.success_target, self.wait_target, self.failure_target]


class PipelineStageRouter(RoutingFunction):
    """
    Router for linear or phased pipeline execution.

    Uses a `pipeline_stage` value stored in execution_state
    to determine which node to execute next.
    """

    def __init__(self, stage_map: Dict[str, str], default_target: str) -> None:
        """
        Parameters
        ----------
        stage_map : Dict[str, str]
            Mapping of stage names to target nodes
        default_target : str
            Fallback target when stage is unknown
        """
        self.stage_map = stage_map
        self.default_target = default_target

    def __call__(self, context: AgentContext) -> str:
        """
        Route based on the current pipeline stage.
        """
        current_stage = context.execution_state.get("pipeline_stage", "initial")
        return self.stage_map.get(current_stage, self.default_target)

    def get_possible_targets(self) -> List[str]:
        targets = list(self.stage_map.values())
        if self.default_target not in targets:
            targets.append(self.default_target)
        return targets


# ---------------------------------------------------------------------------
# Extended routing factory helpers
# ---------------------------------------------------------------------------

def route_with_failure_handling(
    success_target: str,
    failure_target: str,
    retry_target: Optional[str] = None,
    max_failures: int = 3,
) -> RoutingFunction:
    """
    Factory for FailureHandlingRouter.
    """
    return FailureHandlingRouter(
        success_target=success_target,
        failure_target=failure_target,
        retry_target=retry_target,
        max_failures=max_failures,
    )


def route_with_dependencies(
    target_dependencies: Dict[str, List[str]],
    success_target: str,
    wait_target: str = "wait",
    failure_target: str = "error",
) -> RoutingFunction:
    """
    Factory for AgentDependencyRouter.
    """
    return AgentDependencyRouter(
        dependency_map=target_dependencies,
        success_target=success_target,
        wait_target=wait_target,
        failure_target=failure_target,
    )


def route_by_pipeline_stage(
    stage_routing: Dict[str, str], default_target: str = "end"
) -> RoutingFunction:
    """
    Factory for PipelineStageRouter.
    """
    return PipelineStageRouter(stage_map=stage_routing, default_target=default_target)
