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
    "warranties", "webhooks", "work_order_parts",
    "work_orders",
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
