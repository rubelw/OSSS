# src/OSSS/ai/agent_routing_config.py
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Pattern, List, Optional

from OSSS.ai.intents import Intent  # noqa: F401  # (kept for future use)


@dataclass(frozen=True)
class IntentAlias:
    from_label: str
    to_label: str


@dataclass(frozen=True)
class HeuristicRule:
    """
    Simple lexical / regex heuristic that can 'force' an intent for a query.

    A rule matches if EITHER:
      - pattern is not None and pattern.search(query) succeeds, OR
      - contains_any is not None and any of those substrings are found in the
        lowercased query.
    """
    intent: str
    pattern: Optional[Pattern[str]] = None
    contains_any: Optional[List[str]] = None
    description: str = ""


# --- Aliases ---------------------------------------------------------
# --- Aliases ---------------------------------------------------------
INTENT_ALIASES: list[IntentAlias] = [
    # Existing aliases
    IntentAlias("langchain", "langchain_agent"),
    IntentAlias("general_llm", "langchain_agent"),
    IntentAlias("enrollment", "register_new_student"),
    IntentAlias("new_student_registration", "register_new_student"),

    # Map classifier labels related to student counts/listing to query_data
    IntentAlias("student_counts", "query_data"),
    #IntentAlias("students", "query_data"),
    IntentAlias("student_info", "langchain_agent"),

IntentAlias("list_students", "query_data"),
    IntentAlias("scorecards", "query_data"),
    IntentAlias("live_scoring_query", "query_data"),
    IntentAlias("show_materials_list", "query_data"),
]

# ---------------------------------------------------------------------
# AUTO-GENERATED show_<table> and <table>_query ALIASES
# ---------------------------------------------------------------------
TABLES = [
    "academic_terms", "accommodations", "activities", "addresses", "agenda_item_approvals",
    "agenda_item_files", "agenda_items", "agenda_workflow_steps", "agenda_workflows",
    "alembic_version", "alignments", "ap_vendors", "approvals", "asset_parts", "assets",
    "assignment_categories", "assignments", "attendance", "attendance_codes",
    "attendance_daily_summary", "attendance_events", "audit_logs", "behavior_codes",
    "behavior_interventions", "bell_schedules", "buildings", "bus_routes", "bus_stop_times",
    "bus_stops", "calendar_days", "calendars", "channels", "class_ranks", "comm_search_index",
    "committees", "compliance_records", "consents", "consequence_types", "consequences",
    "contacts", "course_prerequisites", "course_sections", "courses", "curricula",
    "curriculum_units", "curriculum_versions", "data_quality_issues", "data_sharing_agreements",
    "deduction_codes", "deliveries", "department_position_index", "departments",
    "document_activity", "document_links", "document_notifications", "document_permissions",
    "document_search_index", "document_versions", "documents", "earning_codes",
    "education_associations", "ell_plans", "embeds", "emergency_contacts",
    "employee_deductions", "employee_earnings", "entity_tags", "evaluation_assignments",
    "evaluation_cycles", "evaluation_files", "evaluation_questions", "evaluation_reports",
    "evaluation_responses", "evaluation_sections", "evaluation_signoffs",
    "evaluation_templates", "events", "export_runs", "external_ids", "facilities",
    "family_portal_access", "feature_flags", "fees", "files", "final_grades",
    "fiscal_periods", "fiscal_years", "floors", "folders", "frameworks",
    "gl_account_balances", "gl_account_segments", "gl_accounts", "gl_segment_values",
    "gl_segments", "goals", "google_accounts", "governing_bodies", "gpa_calculations",
    "grade_levels", "grade_scale_bands", "grade_scales", "gradebook_entries",
    "grading_periods", "guardians", "health_profiles", "hr_employees",
    "hr_position_assignments", "hr_positions", "iep_plans", "immunization_records",
    "immunizations", "incident_participants", "incidents", "initiatives", "invoices",
    "journal_batches", "journal_entries", "journal_entry_lines", "kpi_datapoints", "kpis",
    "leases", "library_checkouts", "library_fines", "library_holds", "library_items",
    "maintenance_requests", "meal_accounts", "meal_eligibility_statuses",
    "meal_transactions", "medication_administrations", "medications", "meeting_documents",
    "meeting_files", "meeting_permissions", "meeting_publications",
    "meeting_search_index", "meetings", "memberships", "message_recipients",
    "messages", "meters", "minutes", "motions", "move_orders", "notifications",
    "nurse_visits", "objectives", "order_line_items", "orders", "organizations",
    "pages", "part_locations", "parts", "pay_periods", "paychecks", "payments",
    "payroll_runs", "periods", "permissions", "person_addresses", "person_contacts",
    "personal_notes", "persons", "plan_alignments", "plan_assignments", "plan_filters",
    "plan_search_index", "plans", "pm_plans", "pm_work_generators", "policies",
    "policy_approvals", "policy_comments", "policy_files", "policy_legal_refs",
    "policy_publications", "policy_search_index", "policy_versions",
    "policy_workflow_steps", "policy_workflows", "post_attachments", "posts",
    "project_tasks", "projects", "proposal_documents", "proposal_reviews",
    "proposal_standard_map", "proposals", "publications", "report_cards",
    "requirements", "resolutions", "retention_rules", "review_requests",
    "review_rounds", "reviewers", "reviews", "role_permissions", "roles", "rooms",
    "round_decisions", "scan_requests", "scan_results", "schools", "scorecard_kpis",
    "scorecards", "section504_plans", "section_meetings", "section_room_assignments",
    "sis_import_jobs", "space_reservations", "spaces", "special_education_cases",
    "staff", "standardized_tests", "standards", "state_reporting_snapshots", "states",
    "student_guardians", "student_program_enrollments", "student_school_enrollments",
    "student_section_enrollments", "student_transportation_assignments", "subjects",
    "subscriptions", "tags", "teacher_section_assignments", "test_administrations",
    "test_results", "ticket_scans", "ticket_types", "tickets", "transcript_lines",
    "unit_standard_map", "user_accounts", "users", "vendors", "votes", "waivers",
    "warranties", "webhooks", "work_order_parts", "work_order_tasks",
    "work_order_time_logs", "work_orders",
]

# Append the aliases
for table in TABLES:
    INTENT_ALIASES.append(IntentAlias(f"show_{table}", "query_data"))
    INTENT_ALIASES.append(IntentAlias(f"{table}_query", "query_data"))


def build_alias_map() -> dict[str, str]:
    return {a.from_label: a.to_label for a in INTENT_ALIASES}


# --- Heuristics ------------------------------------------------------
HEURISTIC_RULES: list[HeuristicRule] = [
    HeuristicRule(
        intent="register_new_student",
        pattern=re.compile(r"\bregister\b.*\bnew student\b", re.IGNORECASE),
        description="Explicit 'register new student' phrasing",
    ),
    HeuristicRule(
        intent="register_new_student",
        pattern=re.compile(r"(20[2-9][0-9])[-/](?:20[2-9][0-9]|[0-9]{2})"),
        description="Bare school-year style answer",
    ),

    # Queries that clearly want a list of students → query_data
    HeuristicRule(
        intent="query_data",
        pattern=re.compile(
            r"\b(list|show|get|give me|display)\b.*\b(student|students)\b",
            re.IGNORECASE,
        ),
        description="Listing / showing all students (e.g. 'list all student names')",
    ),

    # Queries that clearly want a materials list → query_data
    # (If this is too broad later, you can remove plain 'materials' and keep just
    #  'materials list' / 'supply list'.)
    HeuristicRule(
        intent="query_data",
        contains_any=["materials list", "supply list", "materials"],
        description="Listing / showing all materials (e.g. 'show me the materials list')",
    ),
]


def first_matching_intent(query: str) -> str | None:
    """
    Return the first heuristic intent that matches the query, if any.
    """
    if not query:
        return None

    q_lower = query.lower()

    for rule in HEURISTIC_RULES:
        matched = False

        # Regex match
        if rule.pattern is not None and rule.pattern.search(query):
            matched = True

        # contains_any match
        if rule.contains_any:
            if any(sub.lower() in q_lower for sub in rule.contains_any):
                matched = True

        if matched:
            return rule.intent

    return None
