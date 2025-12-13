# src/OSSS/ai/agent_routing_config.py
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Pattern, List, Optional

from OSSS.ai.intents import Intent  # noqa: F401  # (kept for future use)


# ============================================================================
# Models
# ============================================================================

@dataclass(frozen=True)
class IntentAlias:
    from_label: str
    to_label: str



# ============================================================================
# Aliases
#   Normalize many possible classifier / UI labels into canonical intents.
#   Canonical intents should match what your agent registry expects.
# ============================================================================

INTENT_ALIASES: list[IntentAlias] = [
    # Generic / historical aliases
    IntentAlias("langchain", "langchain_agent"),
    IntentAlias("general_llm", "langchain_agent"),
    IntentAlias("enrollment", "register_new_student"),
    IntentAlias("new_student_registration", "register_new_student"),

    # Student list / counts → query_data
    IntentAlias("student_counts", "student_info"),
    IntentAlias("list_students", "query_data"),
    IntentAlias("scorecards", "query_data"),
    IntentAlias("live_scoring_query", "query_data"),
    IntentAlias("show_materials_list", "query_data"),

    # --- Staff aliases (NEW) -----------------------------------------
    # Whatever the classifier/client calls it, route to the canonical staff intent.
    IntentAlias("staff", "staff_info"),
    IntentAlias("staff_info", "staff_info"),
    IntentAlias("staff_directory", "staff_info"),
    IntentAlias("employee_directory", "staff_info"),
    IntentAlias("teacher_directory", "staff_info"),
    IntentAlias("teachers", "staff_info"),
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
    "student_section_enrollments", "student_transportation_assignments", "subjects",
    "subscriptions", "tags", "teacher_section_assignments", "test_administrations",
    "test_results", "ticket_scans", "ticket_types", "tickets", "transcript_lines",
    "unit_standard_map", "user_accounts", "users", "vendors", "votes", "waivers",
    "warranties", "webhooks", "work_order_parts", "work_order_tasks",
    "work_order_time_logs", "work_orders",
]


AUTO_ALIASES: list[IntentAlias] = []
for table in TABLES:
    AUTO_ALIASES.append(IntentAlias(f"show_{table}", "query_data"))
    AUTO_ALIASES.append(IntentAlias(f"{table}_query", "query_data"))

INTENT_ALIASES: list[IntentAlias] = [] + AUTO_ALIASES


def build_alias_map() -> dict[str, str]:
    # last one wins if duplicates exist
    out: dict[str, str] = {}
    for a in INTENT_ALIASES:
        out[a.from_label.strip().lower()] = a.to_label.strip().lower()
    return out


# Common list/show verbs we see in prompts
_LIST_VERB = r"(list|show|get|give me|display|print|dump|return|fetch)"

INTENT_ALIAS_MAP: dict[str, str] = build_alias_map()

def canonicalize_intent(label: str | None) -> str | None:
    if not isinstance(label, str):
        return None
    key = label.strip().lower()
    return INTENT_ALIAS_MAP.get(key, key)




