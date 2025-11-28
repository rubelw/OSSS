from __future__ import annotations

from typing import Optional

import httpx
import logging
from pydantic import BaseModel

from OSSS.ai.intents import Intent

logger = logging.getLogger(__name__)

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
    # Major tone category ∈ {
    #   "formal_professional", "informal_casual",
    #   "emotional_attitude", "action_persuasive", "other"
    # }
    tone_major: Optional[str] = None
    tone_major_confidence: Optional[float] = None

    # Minor tone category (more specific tone label)
    # ∈ {
    #   "formal", "objective", "authoritative", "respectful",
    #   "informal", "casual", "friendly", "enthusiastic",
    #   "humorous", "optimistic", "pessimistic", "serious",
    #   "empathetic_compassionate", "assertive", "sarcastic",
    #   "persuasive", "encouraging", "didactic", "curious",
    #   "candid", "apologetic", "dramatic", "concerned"
    # }
    tone_minor: Optional[str] = None
    tone_minor_confidence: Optional[float] = None


async def classify_intent(text: str) -> IntentResult:
    """
    Call the local LLM (Ollama / vLLM) to classify the user's text into:
      1) a semantic intent (OSSS.ai.intents.Intent),
      2) a CRUD-style action: "read", "create", "update", or "delete",
      3) an urgency level: "low", "medium", or "high",
      4) a major tone category and a more specific minor tone label.

    Examples:
      - "Show me the school calendar"
          -> intent: school_calendar,
             action: "read",
             urgency: "low",
             tone_major: "informal_casual" or "formal_professional",
             tone_minor: "neutral-ish" like "formal" or "informal" depending on phrasing

      - "Register a new student"
          -> intent: register_new_student,
             action: "create",
             urgency: "medium",
             tone_major: "formal_professional" or "informal_casual",
             tone_minor: "formal", "professional", or "friendly"

      - "My child is being bullied on the bus and I'm very worried"
          -> intent: bullying_concern,
             action: "update" or "create",
             urgency: "high",
             tone_major: "emotional_attitude",
             tone_minor: "concerned", "serious", or "empathetic_compassionate"
    """
    base = getattr(settings, "VLLM_ENDPOINT", "http://host.containers.internal:11434").rstrip(
        "/"
    )
    chat_url = f"{base}/v1/chat/completions"
    model = getattr(settings, "INTENT_MODEL", "llama3.2-vision")

    # Log the incoming text (truncated) and config we’re about to use
    logger.info(
        "[intent_classifier] classifying text=%r",
        text[:300] if isinstance(text, str) else text,
    )
    logger.debug(
        "[intent_classifier] endpoint=%s model=%s",
        chat_url,
        model,
    )

    system = (
        "You are an intent classifier for questions about Dallas Center-Grimes (DCG) schools.\n"
        "You must respond with ONLY a single JSON object on one line, for example:\n"
        '{"intent":"general","confidence":0.92,'
        '"action":"read","action_confidence":0.88,'
        '"urgency":"low","urgency_confidence":0.74,'
        '"tone_major":"informal_casual","tone_major_confidence":0.80,'
        '"tone_minor":"friendly","tone_minor_confidence":0.83}\n'
        "\n"
        "The JSON must contain these keys:\n"
        '  - \"intent\": one of the valid OSSS.ai.intents.Intent values listed below\n'
        '  - \"confidence\": a float between 0 and 1 for how confident you are in the `intent`\n'
        '  - \"action\": one of: \"read\", \"create\", \"update\", \"delete\"\n'
        '    * use \"read\" when the user mainly wants to look up, retrieve, or understand information\n'
        '    * use \"create\" when the user wants to add or register something new (e.g., register a new student, create a plan)\n'
        '    * use \"update\" when the user wants to change existing information (e.g., change address, update schedule)\n'
        '    * use \"delete\" when the user wants to remove or cancel something (e.g., unenroll, remove from list)\n'
        '  - \"action_confidence\": a float between 0 and 1 for how confident you are in the `action`\n'
        '  - \"urgency\": one of: \"low\", \"medium\", \"high\"\n'
        "    * use \"low\" when the request is informational or routine and can be handled at the district's normal pace\n"
        "    * use \"medium\" when the request should be handled reasonably soon (e.g., within a few days) but is not an emergency\n"
        "    * use \"high\" when the message sounds urgent, time-critical, or related to safety/well-being (e.g., bullying, threats, medical issues, immediate transportation problems)\n"
        '  - \"urgency_confidence\": a float between 0 and 1 for how confident you are in the `urgency`\n'
        "\n"
        "Tone classification:\n"
        '  - \"tone_major\": one of the following major tone categories:\n'
        '       * \"formal_professional\"  (formal, objective, authoritative, respectful)\n'
        '       * \"informal_casual\"      (informal, casual, friendly, enthusiastic)\n'
        '       * \"emotional_attitude\"   (humorous, optimistic, pessimistic, serious, empathetic_compassionate, assertive, sarcastic)\n'
        '       * \"action_persuasive\"    (persuasive, encouraging, assertive, didactic)\n'
        '       * \"other\"                (curious, candid, apologetic, dramatic, concerned, or any tone that does not fit clearly above)\n'
        '  - \"tone_major_confidence\": float between 0 and 1 for how confident you are in the major tone\n'
        '  - \"tone_minor\": one specific minor tone label, chosen from:\n'
        '       \"formal\", \"objective\", \"authoritative\", \"respectful\",\n'
        '       \"informal\", \"casual\", \"friendly\", \"enthusiastic\",\n'
        '       \"humorous\", \"optimistic\", \"pessimistic\", \"serious\",\n'
        '       \"empathetic_compassionate\", \"assertive\", \"sarcastic\",\n'
        '       \"persuasive\", \"encouraging\", \"didactic\", \"curious\",\n'
        '       \"candid\", \"apologetic\", \"dramatic\", \"concerned\"\n'
        '  - \"tone_minor_confidence\": float between 0 and 1 for how confident you are in the minor tone\n'
        "\n"
        "Valid intents (enum OSSS.ai.intents.Intent): "
        "general, staff_directory, student_counts, transfers, superintendent_goals, board_policy, teacher, enrollment, school_calendar, schedule_meeting, bullying_concern, student_portal, "
        "student_dress_code, school_hours, food_allergy_policy, visitor_safety, student_transition_support, volunteering, board_feedback, board_meeting_access, board_records, grade_appeal, dei_initiatives, "
        "multilingual_communication, bond_levy_spending, family_learning_support, school_feedback, school_contact, transportation_contact, homework_expectations, emergency_drills, graduation_requirements, "
        "operational_risks, curriculum_governance, program_equity, curriculum_timeline, essa_accountability, new_teacher_support, professional_learning_priorities, staff_culture_development, student_support_team, "
        "resource_prioritization, instructional_technology_integration, building_practice_improvement, academic_progress_monitoring, data_dashboard_usage, leadership_reflection, communication_strategy, family_concerns, "
        "district_leadership, instructional_practice, contact_information, staff_recruit, student_behavior_interventions, school_fundraising, parent_involvement, school_infrastructure, special_education, student_assessment, "
        "after_school_programs, diversity_inclusion_policy, health_services, school_security, parent_communication, student_discipline, college_preparation, social_emotional_learning, technology_access, school_improvement_plan, "
        "student_feedback, community_partnerships, alumni_relations, miscarriage_policy, early_childhood_education, student_mentorship, cultural_events, school_lunch_program, homeroom_structure, student_enrichment, "
        "student_inclusion, school_illness_policy, volunteer_opportunities, collaborative_teaching, student_retention, school_evacuation_plans, intervention_strategies, school_awards, dropout_prevention, teacher_evaluation, "
        "special_events, curriculum_integration, field_trips, student_attendance, school_spirit, classroom_management, student_health_records, parent_involvement_events, teacher_training, school_uniform_policy, "
        "school_cultural_committees, school_business_partnerships, school_community_outreach, equal_access_to_opportunities, counselor_support, diversity_equity_policy, student_recognition_programs, teacher_mentoring, peer_tutoring, "
        "school_closures, district_budget, parent_surveys, student_portfolios, activity_fee_policy, school_photography, student_policies, student_graduation_plan, math_support_program, reading_support_program, "
        "school_budget_oversight, student_travel_policy, extrahelp_tutoring, enrichment_programs, school_compliance, parent_teacher_association, student_career_services, student_scholarship_opportunities, student_support_services, "
        "school_conflict_resolution, dropout_intervention, student_assignment_tracking, support_for_special_populations, student_voice, grading_policy, facility_repairs, afterschool_clubs, peer_relationships, early_intervention, "
        "school_mascot, student_leadership, parental_rights, alumni_engagement, bullying_training, school_funding, school_disaster_preparedness, student_health_screenings, accessibility_in_education, inclusion_policy, "
        "school_community_events, internal_communication, extracurricular_funding, student_orientation, school_culture_initiatives, student_retention_strategies, family_school_partnerships, campus_cleanliness, professional_development_evaluation, "
        "student_behavior_monitoring, diversity_and_inclusion_training, school_broadcasts, food_nutrition_programs, school_climate_surveys, athletic_funding, teacher_feedback_mechanisms, gifted_education, campus_recreation, peer_mediation, "
        "alumni_network, student_financial_aid, parental_involvement_training, school_partnerships, school_building_maintenance, school_engagement_measurements, community_outreach_programs, student_transportation_support, "
        "recruitment_and_retention_for_support_staff, school_leadership_development, student_medical_accommodations, extra_credit_opportunities, teacher_assistant_support, financial_aid_training, "
        "student_mobility, student_promotions, student_arts_programs, alumni_engagement_events, student_community_service, school_closure_protocols, school_psychological_support, parent_support_groups, conflict_of_interest_policies, "
        "interschool_collaboration, school_event_scheduling, teacher_contract_negotiations, summer_learning_programs, student_mobility_and_transition, staff_wellness, technology_support_for_teachers, community_feedback_on_school_policy, "
        "peer_support_networks, school_enrollment_forecasting, student_activity_registration, school_computer_lab_access, school_website_access, online_courses, student_report_cards, teacher_facilitator, student_mental_health_support, "
        "teacher_collaboration, school_policies_oversight, school_closure_notifications, parent_school_communication, student_tutoring_services, international_student_support, math_intervention_program, reading_intervention_program, "
        "staff_training_opportunities, school_inspection_reports, student_homework_help, student_field_trip_permission, student_participation_fees, school_disaster_recovery, student_behavior_rewards, "
        "school_bullying_policy, parent_feedback_surveys, student_mental_health_evaluation, college_readiness_programs, student_extracurricular_registration, student_school_id, transportation_routes, student_reporting_system, "
        "academic_intervention_teams, school_reading_programs, parent_portal_setup, student_behavior_contracts, student_counseling_services, student_financial_aid_opportunities, school_community_partnerships, school_bus_route_planning, "
        "campus_security_updates, parent_participation_in_school_events, student_drop_out_prevention, school_performance_reports, special_education_programs, school_nurse_services, student_career_exploration, school_partnership_with_local_businesses, "
        "school_school_mascot, parent_communication_platform, after_school_study_sessions, student_financial_assistance_requests, specialized_school_services, student_aid_requests, school_gardening_programs, school_sports_teams, "
        "school_property_insurance, school_budget_allocations, student_computer_accessibility, parent_teacher_conferences, student_discipline_policy, school_graduation_ceremonies, after_school_extra_credit_opportunities, student_transportation_services, "
        "after_school_homework_club, student_feedback_forms, school_compliance_with_regulations, student_parking_policy, school_security_training, student_assessment_results, parental_consent_for_medical_treatment, "
        "after_school_club_meetings, student_graduation_credentials, school_nutrition_program, school_evacuations_plan, school_transportation_policies, student_virtual_learning_support, school_closure_policies, "
        "afterschool_tutoring_programs, student_admission_fees, school_peer_mentoring, student_workstudy_opportunities, parent_feedback_for_school_policies, parent_teacher_association_meetings, "
        "student_volunteer_opportunities, register_new_student, school_athletic_events, school_talent_shows, school_debate_teams, school_uniforms."
    )

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
        fallback_intent = Intent.GENERAL if hasattr(Intent, "GENERAL") else Intent("general")
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

    # Only attempt JSON parse if it *looks* like JSON
    if isinstance(content, str) and content.lstrip().startswith("{"):
        try:
            import json

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
        # Model ignored instructions and returned prose
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
        intent = Intent.GENERAL if hasattr(Intent, "GENERAL") else Intent("general")

    # Normalize action to one of the allowed values if present
    if isinstance(raw_action, str):
        action_norm = raw_action.lower().strip()
        if action_norm not in {"read", "create", "update", "delete"}:
            logger.warning(
                "[intent_classifier] unknown action %r, setting action=None",
                raw_action,
            )
            action_norm = None
    else:
        action_norm = None

    # Normalize urgency to one of the allowed values if present
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

    # Normalize tone_major to allowed values
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

    # Normalize tone_minor to allowed values
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

    # Keep the parsed JSON (if any) or the full raw data around for debugging in callers
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
    )
