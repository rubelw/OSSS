from __future__ import annotations

from typing import Optional, Any, Dict, List
import httpx
import logging
import json
import re
from pydantic import BaseModel

from OSSS.ai.intents import Intent

logger = logging.getLogger("OSSS.ai.intent_classifier")

# --- SAFE SETTINGS IMPORT (same pattern as rag_router) -----------------
try:
    from OSSS.config import settings as _settings  # type: ignore

    settings = _settings
except Exception:
    # Fallback for local/dev or tests
    class _Settings:
        VLLM_ENDPOINT: str = "http://host.containers.internal:11434"
        INTENT_MODEL: str = "llama3.2-vision"

    settings = _Settings()  # type: ignore


class IntentResult(BaseModel):
    intent: Intent
    confidence: Optional[float] = None
    raw: Optional[dict] = None

    # CRUD-style action classification
    # action ∈ {"read", "create", "update", "delete"} (or None if unknown)
    action: Optional[str] = None
    action_confidence: Optional[float] = None

    # Urgency classification for routing / triage
    # urgency ∈ {"low", "medium", "high"} (or None if unknown)
    urgency: Optional[str] = None
    urgency_confidence: Optional[float] = None

    # Tone classification
    tone_major: Optional[str] = None
    tone_major_confidence: Optional[float] = None
    tone_minor: Optional[str] = None
    tone_minor_confidence: Optional[float] = None

    # Raw LLM/heuristic output string (for UI / debug)
    # NOTE: raw_model_content is kept for back-compat; raw_model_output is the new
    # unified field that the router exposes as `intent_raw_model_output`.
    raw_model_content: Optional[str] = None
    raw_model_output: Optional[str] = None

    # Optional: where this result came from ("heuristic", "llm", "fallback")
    source: Optional[str] = None


# ---------------------------------------------------------------------------
# Heuristic rule model + table (scalable for many patterns)
# ---------------------------------------------------------------------------

class IntentHeuristicRule(BaseModel):
    """
    A simple, config-like rule for matching text to an intent without
    calling the LLM.

    - If any `contains_any` keyword is found (case-insensitive), the rule matches.
    - If `regex` is provided and matches, the rule matches.
    - If either condition matches, the rule fires.
    """
    name: str

    # matching
    contains_any: List[str] = []
    regex: Optional[str] = None

    # what intent/action to return
    intent: str
    action: Optional[str] = "read"
    urgency: Optional[str] = "low"
    tone_major: Optional[str] = "informal_casual"
    tone_minor: Optional[str] = "friendly"

    # optional extra metadata if you ever want to propagate it later
    metadata: Dict[str, Any] = {}


HEURISTIC_RULES: List[IntentHeuristicRule] = [
    # -------------------- Existing Rules --------------------
    IntentHeuristicRule(
        name="scorecards_query",
        contains_any=["scorecard", "scorecards"],
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="friendly",
        metadata={"mode": "scorecards"},
    ),
    IntentHeuristicRule(
        name="live_scoring_query",
        contains_any=["live scoring", "live score", "live scores", "live game"],
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="friendly",
        metadata={"mode": "live_scorings"},
    ),
    IntentHeuristicRule(
        name="immunization_records_query_rule",
        contains_any=["immunization records", "student immunizations", "student shots"],
        intent="query_data",
        action="read",
        metadata={"mode": "immunization_records"},
    ),
    IntentHeuristicRule(
        name="incident_participants_query_rule",
        contains_any=[
            "incident_participants",          # snake_case
            "incident participants",          # with space
            "show incident participants",     # full phrase you just tried
            "show incident_participants",
        ],
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="friendly",
        metadata={"mode": "incident_participants"},
    ),
    IntentHeuristicRule(
        name="person_addresses_query_rule",
        contains_any=[
            "person addresses",
            "person_addresses",
            "show person addresses",
            "show person_addresses",
        ],
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="friendly",
        metadata={"mode": "person_addresses"},
    ),
    IntentHeuristicRule(
        name="addresses_query_rule",
        contains_any=["addresses", "show addresses", "addresses query"],
        intent="query_data",
        action="read",
        metadata={"mode": "addresses"},
    ),
    IntentHeuristicRule(
        name="attendance_query_rule",
        contains_any=[
            "attendance",
            "attendances",
            "show attendance",
            "show attendances",
            "attendance events",
        ],
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="friendly",
        metadata={"mode": "attendances"},  # MUST MATCH handler.mode
    ),
    IntentHeuristicRule(
        name="work_order_time_logs_query_rule",
        contains_any=[
            "work order time logs",
            "work_order_time_logs",
            "work order logs",
            "time logs",
            "show work order time logs",
            "show time logs",
            "maintenance time logs",
            "wo logs",
        ],
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="friendly",
        metadata={"mode": "work_order_time_logs"}
    ),
    IntentHeuristicRule(
        name="work_order_tasks_query_rule",
        contains_any=[
            "work order tasks",
            "work_order_tasks",
            "wo tasks",
            "maintenance tasks",
            "task list",
            "work order task list",
            "show work order tasks",
            "show tasks for work orders",
        ],
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="friendly",
        metadata={"mode": "work_order_tasks"},
    ),
    IntentHeuristicRule(
        name="work_order_parts_query_rule",
        contains_any=[
            "work order parts",
            "work_order_parts",
            "wo parts",
            "parts used",
            "parts used on work orders",
            "maintenance parts",
            "show work order parts",
            "show parts used",
        ],
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="friendly",
        metadata={"mode": "work_order_parts"},
    ),
    IntentHeuristicRule(
        name="user_accounts_query_rule",
        contains_any=[
            "user accounts",
            "user_accounts",
            "show user accounts",
            "login accounts",
            "portal accounts",
            "osss accounts",
            "account list",
        ],
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="friendly",
        metadata={"mode": "user_accounts"},
    ),
    IntentHeuristicRule(
        name="ticket_types_query_rule",
        contains_any=[
            "ticket types",
            "ticket_types",
            "show ticket types",
            "list ticket types",
            "helpdesk ticket types",
            "support ticket types",
            "it ticket types",
        ],
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="friendly",
        metadata={"mode": "ticket_types"},
    ),
    IntentHeuristicRule(
        name="ticket_scans_query_rule",
        contains_any=[
            "ticket scans",
            "ticket_scans",
            "show ticket scans",
            "show ticket_scans",
            "scan logs",
            "ticket scan logs",
            "ticket check-ins",
            "ticket checkins",
            "gate scans",
            "entry scans",
        ],
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="friendly",
        metadata={"mode": "ticket_scans"},
    ),
    IntentHeuristicRule(
        name="tickets_query_rule",
        contains_any=[
            "tickets",
            "ticket list",
            "show tickets",
            "ticket inventory",
            "ticket sales",
            "event tickets",
            "tickets report",
        ],
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="friendly",
        metadata={"mode": "tickets"},
    ),
    IntentHeuristicRule(
        name="work_orders_query_rule",
        contains_any=[
            "work orders",
            "work_orders",
            "maintenance work orders",
            "maintenance tickets",
            "show work orders",
            "show maintenance work orders",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="friendly",
        metadata={"mode": "work_orders"},
    ),
    IntentHeuristicRule(
        name="webhooks_query_rule",
        contains_any=[
            "webhooks",
            "webhook list",
            "show webhooks",
            "outbound webhooks",
            "event webhooks",
            "callback webhooks",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="friendly",
        metadata={"mode": "webhooks"},
    ),
    IntentHeuristicRule(
        name="warranties_query_rule",
        contains_any=[
            "warranties",
            "warranty",
            "asset warranty",
            "equipment warranties",
            "show warranties",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="friendly",
        metadata={"mode": "warranties"},
    ),
    IntentHeuristicRule(
        name="waivers_query_rule",
        contains_any=[
            "waivers",
            "waiver",
            "student waivers",
            "fee waiver",
            "program waiver",
            "show waivers",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="friendly",
        metadata={"mode": "waivers"},
    ),
    IntentHeuristicRule(
        name="votes_query_rule",
        contains_any=[
            "votes",
            "vote records",
            "voting records",
            "ballot votes",
            "show votes",
            "list votes",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="friendly",
        metadata={"mode": "votes"},
    ),
    IntentHeuristicRule(
        name="vendors_query_rule",
        contains_any=[
            "vendors",
            "vendor list",
            "vendor records",
            "supplier",
            "suppliers",
            "approved vendors",
            "list vendors",
            "show vendors",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="friendly",
        metadata={"mode": "vendors"},
    ),
    IntentHeuristicRule(
        name="users_query_rule",
        contains_any=[
            "users",
            "user list",
            "list users",
            "show users",
            "system users",
            "application users",
            "auth users",
            "registered users",
            "login accounts",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="friendly",
        metadata={"mode": "users"},
    ),
    IntentHeuristicRule(
        name="transcript_lines_query_rule",
        contains_any=[
            "transcript lines",
            "transcript_lines",
            "show transcript lines",
            "show transcript_lines",
            "transcript line data",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="friendly",
        metadata={"mode": "transcript_lines"},
    ),
    IntentHeuristicRule(
        name="test_results_query_rule",
        contains_any=[
            "test results",
            "test_results",
            "show test results",
            "show test_results",
            "assessment results",
            "exam results",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="friendly",
        metadata={"mode": "test_results"},
    ),
    IntentHeuristicRule(
        name="test_administrations_query_rule",
        contains_any=[
            "test administrations",
            "test_administrations",
            "show test administrations",
            "show test_administrations",
            "assessment administrations",
            "testing sessions",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="friendly",
        metadata={"mode": "test_administrations"},
    ),
    IntentHeuristicRule(
        name="teacher_section_assignments_query_rule",
        contains_any=[
            "teacher section assignments",
            "teacher_section_assignments",
            "teacher assignment sections",
            "teacher-section assignments",
            "show teacher section assignments",
            "list teacher section assignments",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="helpful",
        metadata={"mode": "teacher_section_assignments"},
    ),
    IntentHeuristicRule(
        name="tags_query_rule",
        contains_any=[
            "tags",
            "list tags",
            "tag list",
            "show tags",
            "all tags",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="helpful",
        metadata={"mode": "tags"},
    ),
    IntentHeuristicRule(
        name="subscriptions_query_rule",
        contains_any=[
            "subscriptions",
            "list subscriptions",
            "subscription list",
            "show subscriptions",
            "all subscriptions",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="helpful",
        metadata={"mode": "subscriptions"},
    ),
    IntentHeuristicRule(
        name="subjects_query_rule",
        contains_any=[
            "subjects",
            "course subjects",
            "subject list",
            "list subjects",
            "show subjects",
            "all subjects",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="helpful",
        metadata={"mode": "subjects"},
    ),
    IntentHeuristicRule(
        name="student_transportation_assignments_query_rule",
        contains_any=[
            "student transportation assignments",
            "student_transportation_assignments",
            "transportation assignments",
            "bus assignments",
            "student bus assignments",
            "show transportation assignments",
            "show student transportation",
            "list transportation assignments",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="helpful",
        metadata={"mode": "student_transportation_assignments"},
    ),
    IntentHeuristicRule(
        name="student_section_enrollments_query_rule",
        contains_any=[
            "student section enrollments",
            "student_section_enrollments",
            "section enrollments",
            "student class enrollments",
            "student schedule enrollments",
            "class enrollments",
            "student enrollment list",
            "show student enrollments",
            "list student enrollments",
            "show section enrollments",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="helpful",
        metadata={"mode": "student_section_enrollments"},
    ),
    IntentHeuristicRule(
        name="student_school_enrollments_query_rule",
        contains_any=[
            "student school enrollments",
            "student_school_enrollments",
            "school enrollments",
            "student school enrollment list",
            "student enrollment by school",
            "student building enrollments",
            "school-level student enrollments",
            "show student school enrollments",
            "list student school enrollments",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="helpful",
        metadata={"mode": "student_school_enrollments"},
    ),
    IntentHeuristicRule(
        name="student_program_enrollments_query_rule",
        contains_any=[
            "student program enrollments",
            "student_program_enrollments",
            "program enrollments",
            "student program enrollment list",
            "student program roster",
            "program-level student enrollments",
            "show student program enrollments",
            "list student program enrollments",
            "student program participation",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="helpful",
        metadata={"mode": "student_program_enrollments"},
    ),
    IntentHeuristicRule(
        name="student_guardians_query_rule",
        contains_any=[
            "student_guardians",
            "student guardians",
            "guardian list",
            "student guardian list",
            "list student guardians",
            "show student guardians",
            "guardian info",
            "guardian information",
            "emergency contacts",
            "parent contacts",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="helpful",
        metadata={"mode": "student_guardians"},
    ),
    IntentHeuristicRule(
        name="states_query_rule",
        contains_any=[
            "states",
            "state list",
            "list of states",
            "us states",
            "state codes",
            "state abbreviations",
            "show states",
            "show state list",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="helpful",
        metadata={"mode": "states"},
    ),
    IntentHeuristicRule(
        name="state_reporting_snapshots_query_rule",
        contains_any=[
            "state reporting snapshots",
            "state reporting snapshot",
            "state reporting export",
            "state reporting submission",
            "state reporting file",
        ],
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="helpful",
        metadata={"mode": "state_reporting_snapshots"},
    ),
    IntentHeuristicRule(
        name="standards_query_rule_custom",
        contains_any=[
            "learning standards",
            "academic standards",
            "state standards",
            "iowa core standards",
            "ngss standards",
            "common core standards",
        ],
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="helpful",
        metadata={"mode": "standards"},
    ),
    IntentHeuristicRule(
        name="standardized_tests_query_rule",
        contains_any=[
            "standardized tests",
            "standardized_tests",
            "show standardized tests",
            "list standardized tests",
        ],
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="friendly",
        metadata={"mode": "standardized_tests"},
    ),
    IntentHeuristicRule(
        name="staff_query_rule",
        contains_any=[
            # generic table / API phrases
            "staff",
            "staff list",
            "staff directory",
            "show staff",
            "list staff",
            # common school-language ways to ask for this data
            "teacher list",
            "teachers list",
            "teacher directory",
            "employee directory",
            "district staff",
            "school staff",
            "who works at",
            "which teachers",
        ],
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="helpful",
        metadata={"mode": "staff"},
    ),

    IntentHeuristicRule(
        name="special_education_cases_query_rule",
        contains_any=[
            "special education cases",
            "special_education_cases",
            "special ed cases",
            "special education caseload",
            "sped cases",
            "iep cases",
            "special ed students",
            "special education students",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="helpful",
        metadata={"mode": "special_education_cases"},
    ),
    IntentHeuristicRule(
        name="spaces_query_rule",
        contains_any=[
            "spaces",
            "space list",
            "facility spaces",
            "rooms and spaces",
            "building spaces",
            "available spaces",
            "list spaces",
            "show spaces",
            "classroom spaces",
            "meeting spaces",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="helpful",
        metadata={"mode": "spaces"},
    ),
    IntentHeuristicRule(
        name="space_reservations_query_rule",
        contains_any=[
            "space reservations",
            "space_reservations",
            "facility reservations",
            "room reservations",
            "gym reservations",
            "auditorium reservations",
            "who has this space",
            "who has the gym reserved",
            "which spaces are reserved",
            "calendar of space reservations",
            "list space reservations",
            "show space reservations",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="helpful",
        metadata={"mode": "space_reservations"},
    ),
    IntentHeuristicRule(
        name="sis_import_jobs_query_rule",
        contains_any=[
            "sis import jobs",
            "sis_import_jobs",
            "SIS import history",
            "SIS sync jobs",
            "SIS sync runs",
            "import job status",
            "SIS imports",
            "student information system imports",
            "show sis import jobs",
            "list sis import jobs",
            "when did the last sis import run",
            "last sis import job",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="helpful",
        metadata={"mode": "sis_import_jobs"},
    ),
    IntentHeuristicRule(
        name="section_room_assignments_query_rule",
        contains_any=[
            "section room assignments",
            "section_room_assignments",
            "room assignments by section",
            "classroom assignments",
            "section classroom assignments",
            "classroom for this section",
            "what room is this section in",
            "which room is this section in",
            "schedule room assignments",
            "show section room assignments",
            "list section room assignments",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="helpful",
        metadata={"mode": "section_room_assignments"},
    ),
    IntentHeuristicRule(
        name="section_meetings_query_rule",
        contains_any=[
            "section meetings",
            "section_meetings",
            "class meeting times",
            "meeting times for this section",
            "when does this section meet",
            "what time does this class meet",
            "section meeting schedule",
            "class schedule meeting",
            "class meets at",
            "meeting schedule for section",
            "list section meetings",
            "show section meetings",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="helpful",
        metadata={"mode": "section_meetings"},
    ),
    IntentHeuristicRule(
        name="section504_plans_query_rule",
        contains_any=[
            "section504_plans",
            "section504 plans",
            "504 plans",
            "section 504 plans",
            "student 504 plan",
            "student 504 plans",
            "504 accommodations",
            "504 services",
            "which students have 504",
            "who has a 504 plan",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="helpful",
        metadata={"mode": "section504_plans"},
    ),
    IntentHeuristicRule(
        name="scorecard_kpis_query_rule",
        contains_any=[
            "scorecard kpis",
            "scorecard_kpis",
            "kpis on scorecards",
            "plan kpis",
            "plan kpi",
            "performance indicators",
            "scorecard metrics",
            "plan metrics",
            "kpi list",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="helpful",
        metadata={"mode": "scorecard_kpis"},
    ),
    IntentHeuristicRule(
        name="schools_query_rule",
        contains_any=[
            "schools",
            "school list",
            "list schools",
            "dcg schools",
            "district schools",
            "school buildings",
            "school directory",
            "which schools",
            "what schools do we have",
            "elementary schools",
            "middle schools",
            "high schools",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="helpful",
        metadata={"mode": "schools"},
    ),
    IntentHeuristicRule(
        name="scan_results_query_rule",
        contains_any=[
            "scan results",
            "scan_results",
            "security scan",
            "security scans",
            "scan findings",
            "scan output",
            "scanner results",
            "vulnerability scan results",
            "show scan results",
            "list scan results",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="helpful",
        metadata={"mode": "scan_results"},
    ),
    IntentHeuristicRule(
        name="scan_requests_query_rule",
        contains_any=[
            "scan requests",
            "scan_requests",
            "show scan requests",
            "list scan requests",
            "queued scans",
            "pending scans",
            "scheduled scans",
            "requested scans",
            "scan job queue",
            "scan request queue",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="helpful",
        metadata={"mode": "scan_requests"},
    ),
    IntentHeuristicRule(
        name="round_decisions_query_rule",
        contains_any=[
            "round decisions",
            "round_decisions",
            "review round decisions",
            "proposal round decisions",
            "decision rounds",
            "round decision list",
            "show round decisions",
            "list round decisions",
            "review decisions by round",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="helpful",
        metadata={"mode": "round_decisions"},
    ),
    IntentHeuristicRule(
        name="rooms_query_rule",
        contains_any=[
            "rooms",
            "room list",
            "school rooms",
            "classrooms",
            "classroom list",
            "what rooms",
            "which rooms",
            "building rooms",
            "list rooms",
            "show rooms",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="helpful",
        metadata={"mode": "rooms"},
    ),
    IntentHeuristicRule(
        name="roles_query_rule",
        contains_any=[
            "roles",
            "role list",
            "user roles",
            "system roles",
            "permission roles",
            "district roles",
            "teacher roles",
            "staff roles",
            "which roles",
            "show roles",
            "list roles",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="helpful",
        metadata={"mode": "roles"},
    ),
    IntentHeuristicRule(
        name="role_permissions_query_rule",
        contains_any=[
            "role permissions",
            "role_permissions",
            "permissions for role",
            "permissions by role",
            "what can this role do",
            "what can admins do",
            "what can teachers do",
            "role access",
            "role privileges",
            "list role permissions",
            "show role permissions",
        ],
        regex=None,
        intent="query_data",
        action="read",
        urgency="low",
        tone_major="informal_casual",
        tone_minor="helpful",
        metadata={"mode": "role_permissions"},
    ),








    # -------------------- AUTO-GENERATED RULES --------------------
]

TABLES = [
    "academic_terms", "accommodations", "activities", "agenda_item_approvals",
    "agenda_item_files", "agenda_items", "agenda_workflow_steps", "agenda_workflows",
    "alembic_version", "alignments", "ap_vendors", "approvals", "asset_parts", "assets",
    "assignment_categories", "assignments", "attendance_codes",
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
    "hr_position_assignments", "hr_positions", "iep_plans",
    "immunizations", "incidents", "initiatives", "invoices",
    "journal_batches", "journal_entries", "journal_entry_lines", "kpi_datapoints", "kpis",
    "leases", "library_checkouts", "library_fines", "library_holds", "library_items",
    "maintenance_requests", "meal_accounts", "meal_eligibility_statuses",
    "meal_transactions", "medication_administrations", "medications", "meeting_documents",
    "meeting_files", "meeting_permissions", "meeting_publications",
    "meeting_search_index", "meetings", "memberships", "message_recipients",
    "messages", "meters", "minutes", "motions", "move_orders", "notifications",
    "nurse_visits", "objectives", "order_line_items", "orders", "organizations",
    "pages", "part_locations", "parts", "pay_periods", "paychecks", "payments",
    "payroll_runs", "periods", "permissions", "person_contacts",
    "personal_notes", "persons", "plan_alignments", "plan_assignments", "plan_filters",
    "plan_search_index", "plans", "pm_plans", "pm_work_generators", "policies",
    "policy_approvals", "policy_comments", "policy_files", "policy_legal_refs",
    "policy_publications", "policy_search_index", "policy_versions",
    "policy_workflow_steps", "policy_workflows", "post_attachments", "posts",
    "project_tasks", "projects", "proposal_documents", "proposal_reviews",
    "proposal_standard_map", "proposals", "publications", "report_cards",
    "requirements", "resolutions", "retention_rules", "review_requests",
    "review_rounds", "reviewers", "reviews",







]

# Auto-extend HEURISTIC_RULES
for table in TABLES:
    HEURISTIC_RULES.append(
        IntentHeuristicRule(
            name=f"{table}_query_rule",
            contains_any=[
                table,
                f"show {table}",
                f"{table} query",
            ],
            intent="query_data",
            action="read",
            urgency="low",
            tone_major="informal_casual",
            tone_minor="friendly",
            metadata={"mode": table},
        )
    )



def _apply_heuristics(text: str) -> Optional[IntentResult]:
    """
    Try to match the user's text against a list of heuristic rules.
    Returns an IntentResult if a rule fires, otherwise None.

    Also populates raw_model_output with a JSON blob that includes the
    full heuristic_rule and the original text, e.g.:

    {
      "source": "heuristic",
      "heuristic_rule": { ... rule fields ... },
      "text": "...",
      "llm": null
    }
    """
    lowered = (text or "").lower()

    for rule in HEURISTIC_RULES:
        matched = False

        if rule.contains_any:
            if any(kw in lowered for kw in rule.contains_any):
                matched = True

        if rule.regex and re.search(rule.regex, lowered):
            matched = True

        if not matched:
            continue

        logger.info(
            "[intent_classifier] heuristic rule matched: %s -> intent=%s",
            rule.name,
            rule.intent,
        )

        # Map rule.intent string => Intent enum safely
        try:
            intent_enum = Intent(rule.intent)
        except Exception:
            logger.warning(
                "[intent_classifier] heuristic rule produced unknown intent %r; "
                "falling back to GENERAL",
                rule.intent,
            )
            intent_enum = (
                Intent.GENERAL if hasattr(Intent, "GENERAL") else Intent("general")
            )

        # Debug bundle that will be surfaced to the caller via intent_raw_model_output
        bundle = {
            "source": "heuristic",
            "heuristic_rule": rule.model_dump(),
            "text": text,
            "llm": None,
        }
        bundle_json = json.dumps(bundle, ensure_ascii=False)

        return IntentResult(
            intent=intent_enum,
            confidence=0.95,
            raw={"heuristic_rule": rule.model_dump(), "text": text},
            action=rule.action,
            action_confidence=0.95,
            urgency=rule.urgency,
            urgency_confidence=0.8,
            tone_major=rule.tone_major,
            tone_major_confidence=0.8,
            tone_minor=rule.tone_minor,
            tone_minor_confidence=0.8,
            # For heuristics, we make both fields the same JSON string, so existing
            # consumers of raw_model_content keep working AND the router can pass
            # raw_model_output down to agents as intent_raw_model_output.
            raw_model_content=bundle_json,
            raw_model_output=bundle_json,
            source="heuristic",
        )

    return None


async def classify_intent(text: str) -> IntentResult:
    """
    Call the local LLM (Ollama / vLLM) to classify the user's text into:
      1) a semantic intent (OSSS.ai.intents.Intent),
      2) a CRUD-style action: "read", "create", "update", or "delete",
      3) an urgency level: "low", "medium", or "high",
      4) a major tone category and a more specific minor tone label.

    Heuristic rules are applied first; if any rule matches, we skip the LLM.
    """
    base = getattr(
        settings, "VLLM_ENDPOINT", "http://host.containers.internal:11434"
    ).rstrip("/")
    chat_url = f"{base}/v1/chat/completions"
    model = getattr(settings, "INTENT_MODEL", "llama3.2-vision")

    logger.info(
        "[intent_classifier] classifying text=%r",
        text[:300] if isinstance(text, str) else text,
    )
    logger.debug(
        "[intent_classifier] endpoint=%s model=%s",
        chat_url,
        model,
    )

    # --- 1) Heuristic fast-path ---------------------------------------------
    heuristic_result = _apply_heuristics(text)
    if heuristic_result is not None:
        # heuristic_result already has raw_model_output populated
        return heuristic_result

    # --- 2) SYSTEM PROMPT (TRIPLE-QUOTED TO AVOID QUOTING BUGS) -------------
    system = """
You are an intent classifier for questions about Dallas Center-Grimes (DCG) schools.
You must respond with ONLY a single JSON object on one line, for example:
{"intent":"general","confidence":0.92,
 "action":"read","action_confidence":0.88,
 "urgency":"low","urgency_confidence":0.74,
 "tone_major":"informal_casual","tone_major_confidence":0.80,
 "tone_minor":"friendly","tone_minor_confidence":0.83}

... (prompt truncated for brevity in this excerpt; keep your full prompt here) ...
"""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": text},
    ]

    # ---- Call upstream LLM -------------------------------------------------
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                chat_url,
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": 0.0,
                    "stream": False,
                },
            )
            logger.info(
                "[intent_classifier] upstream_v1 status=%s bytes=%s",
                resp.status_code,
                len(resp.content),
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        logger.error(
            "[intent_classifier] HTTP error when calling %s: %s (falling back to general intent)",
            chat_url,
            e,
        )
        fallback_intent = (
            Intent.GENERAL if hasattr(Intent, "GENERAL") else Intent("general")
        )
        # Even on fallback, populate raw_model_output so downstream can see what happened
        bundle = {
            "source": "fallback",
            "heuristic_rule": None,
            "text": text,
            "llm": {
                "error": str(e),
                "endpoint": chat_url,
            },
        }
        bundle_json = json.dumps(bundle, ensure_ascii=False)
        return IntentResult(
            intent=fallback_intent,
            confidence=None,
            raw={"error": str(e)},
            action=None,
            action_confidence=None,
            urgency=None,
            urgency_confidence=None,
            tone_major=None,
            tone_major_confidence=None,
            tone_minor=None,
            tone_minor_confidence=None,
            raw_model_content=None,
            raw_model_output=bundle_json,
            source="fallback",
        )

    # ---- Extract raw content -----------------------------------------------
    content = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )
    logger.debug(
        "[intent_classifier] raw model content: %r",
        content[-500:] if isinstance(content, str) else content,
    )

    # ---- Try to parse the model output as JSON -----------------------------
    obj = None
    raw_intent = "general"
    confidence: Optional[float] = None
    raw_action: Optional[str] = None
    action_confidence: Optional[float] = None
    raw_urgency: Optional[str] = None
    urgency_confidence: Optional[float] = None
    raw_tone_major: Optional[str] = None
    tone_major_confidence: Optional[float] = None
    raw_tone_minor: Optional[str] = None
    tone_minor_confidence: Optional[float] = None

    if isinstance(content, str) and content.lstrip().startswith("{"):
        try:
            obj = json.loads(content)
            raw_intent = obj.get("intent", "general")
            confidence = obj.get("confidence")

            raw_action = obj.get("action")
            action_confidence = obj.get("action_confidence")

            raw_urgency = obj.get("urgency")
            urgency_confidence = obj.get("urgency_confidence")

            raw_tone_major = obj.get("tone_major")
            tone_major_confidence = obj.get("tone_major_confidence")

            raw_tone_minor = obj.get("tone_minor")
            tone_minor_confidence = obj.get("tone_minor_confidence")

            logger.info(
                "[intent_classifier] parsed JSON obj=%s raw_intent=%r confidence=%r "
                "raw_action=%r action_confidence=%r raw_urgency=%r urgency_confidence=%r "
                "raw_tone_major=%r tone_major_confidence=%r "
                "raw_tone_minor=%r tone_minor_confidence=%r",
                obj,
                raw_intent,
                confidence,
                raw_action,
                action_confidence,
                raw_urgency,
                urgency_confidence,
                raw_tone_major,
                tone_major_confidence,
                raw_tone_minor,
                tone_minor_confidence,
            )
        except Exception as e:
            logger.warning(
                "[intent_classifier] JSON parse failed for content prefix=%r error=%s "
                "(falling back to general intent/read action)",
                content[:120],
                e,
            )
            obj = None
            raw_intent = "general"
            confidence = None
            raw_action = None
            action_confidence = None
            raw_urgency = None
            urgency_confidence = None
            raw_tone_major = None
            tone_major_confidence = None
            raw_tone_minor = None
            tone_minor_confidence = None
    else:
        logger.info(
            "[intent_classifier] model returned non-JSON content, falling back to general intent/read action"
        )

    # ---- Map string -> Intent enum safely ----------------------------------
    try:
        intent = Intent(raw_intent)
    except Exception as e:
        logger.warning(
            "[intent_classifier] unknown intent %r, falling back to GENERAL: %s",
            raw_intent,
            e,
        )
        intent = (
            Intent.GENERAL if hasattr(Intent, "GENERAL") else Intent("general")
        )

    # Normalize action
    if isinstance(raw_action, str):
        action_norm = raw_action.lower().strip()
        if action_norm not in {"read", "create", "update", "delete"}:
            logger.warning(
                "[intent_classifier] unknown action %r, setting action=None", raw_action
            )
            action_norm = None
    else:
        action_norm = None

    # Normalize urgency
    if isinstance(raw_urgency, str):
        urgency_norm = raw_urgency.lower().strip()
        if urgency_norm not in {"low", "medium", "high"}:
            logger.warning(
                "[intent_classifier] unknown urgency %r, setting urgency=None",
                raw_urgency,
            )
            urgency_norm = None
    else:
        urgency_norm = None

    # Normalize tone_major
    valid_tone_major = {
        "formal_professional",
        "informal_casual",
        "emotional_attitude",
        "action_persuasive",
        "other",
    }
    if isinstance(raw_tone_major, str):
        tone_major_norm = raw_tone_major.lower().strip()
        if tone_major_norm not in valid_tone_major:
            logger.warning(
                "[intent_classifier] unknown tone_major %r, setting tone_major=None",
                raw_tone_major,
            )
            tone_major_norm = None
    else:
        tone_major_norm = None

    # Normalize tone_minor
    valid_tone_minor = {
        "formal",
        "objective",
        "authoritative",
        "respectful",
        "informal",
        "casual",
        "friendly",
        "enthusiastic",
        "humorous",
        "optimistic",
        "pessimistic",
        "serious",
        "empathetic_compassionate",
        "assertive",
        "sarcastic",
        "persuasive",
        "encouraging",
        "didactic",
        "curious",
        "candid",
        "apologetic",
        "dramatic",
        "concerned",
    }
    if isinstance(raw_tone_minor, str):
        tone_minor_norm = raw_tone_minor.lower().strip()
        if tone_minor_norm not in valid_tone_minor:
            logger.warning(
                "[intent_classifier] unknown tone_minor %r, setting tone_minor=None",
                raw_tone_minor,
            )
            tone_minor_norm = None
    else:
        tone_minor_norm = None

    logger.info(
        "[intent_classifier] final intent=%s confidence=%r "
        "action=%r action_confidence=%r "
        "urgency=%r urgency_confidence=%r "
        "tone_major=%r tone_major_confidence=%r "
        "tone_minor=%r tone_minor_confidence=%r",
        getattr(intent, "value", str(intent)),
        confidence,
        action_norm,
        action_confidence,
        urgency_norm,
        urgency_confidence,
        tone_major_norm,
        tone_major_confidence,
        tone_minor_norm,
        tone_minor_confidence,
    )

    # Bundle for raw_model_output (LLM path)
    bundle = {
        "source": "llm",
        "heuristic_rule": None,
        "text": text,
        "llm": obj,  # parsed JSON if available, else None
    }
    bundle_json = json.dumps(bundle, ensure_ascii=False)

    return IntentResult(
        intent=intent,
        confidence=confidence,
        raw=obj or data,
        action=action_norm,
        action_confidence=action_confidence,
        urgency=urgency_norm,
        urgency_confidence=urgency_confidence,
        tone_major=tone_major_norm,
        tone_major_confidence=tone_major_confidence,
        tone_minor=tone_minor_norm,
        tone_minor_confidence=tone_minor_confidence,
        # raw_model_content = verbatim model content; raw_model_output = our structured bundle
        raw_model_content=content,
        raw_model_output=bundle_json,
        source="llm",
    )
