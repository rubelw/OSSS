# src/OSSS/ai/rag_router.py
from __future__ import annotations

from typing import Optional, List
import logging

import httpx
import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from OSSS.ai.additional_index import top_k, INDEX_KINDS
from OSSS.ai.intent_classifier import classify_intent
from OSSS.ai.intents import Intent

logger = logging.getLogger("OSSS.ai.rag_router")

# Try to reuse the same ChatMessage model from your gateway
try:
    from OSSS.api.routers.ai_gateway import ChatMessage, redact_pii  # type: ignore
except Exception:
    # Fallback minimal definitions (won't be used if import above works)
    class ChatMessage(BaseModel):
        role: str
        content: str

    def redact_pii(text: str) -> str:
        return text


# Try to reuse your real settings; if not, fall back like the gateway does
try:
    from OSSS.config import settings as _settings  # type: ignore
    settings = _settings
except Exception:  # fallback, same as in your ai_gateway
    class _Settings:
        VLLM_ENDPOINT: str = "http://host.containers.internal:11434"
        TUTOR_TEMPERATURE: float = 0.2
        # Allow up to 2048 tokens by default
        TUTOR_MAX_TOKENS: int = 2048
        DEFAULT_MODEL: str = "llama3.2-vision"

    settings = _Settings()  # type: ignore


router = APIRouter(
    prefix="/ai",
    tags=["ai-rag"],
)


# ---- auth guard: reuse your real auth if available ----
try:
    from OSSS.auth.deps import require_user  # or require_auth / require_admin in your repo

    def _auth_guard(user=Depends(require_user)):
        return user

except Exception:
    # dev fallback: no auth
    def _auth_guard():
        return None


class RAGRequest(BaseModel):
    model: Optional[str] = "llama3.2-vision"
    messages: List[ChatMessage] = Field(
        default=[
            ChatMessage(role="system", content="You are a helpful assistant."),
            ChatMessage(role="user", content="who is dcg's superintendent?"),
        ],
        description="Conversation messages for the model",
    )
    # Default to 2048 if the client doesn't specify
    max_tokens: Optional[int] = 2048
    temperature: Optional[float] = 0.1
    debug: Optional[bool] = False
    # NEW: which additional index to query ("main", "tutor", or "agent")
    index: Optional[str] = "main"


def _normalize_dcg_expansion(text: str) -> str:
    """
    Force 'DCG' to only mean Dallas Center-Grimes Community School District
    in the final answer. Fixes common wrong expansions from the model.
    """
    if not isinstance(text, str):
        return text

    wrong_phrases = [
        "Des Moines Christian School",
        "Des Moines Christian Schools",
        "Des Moines Christian",
        "Des Moines Community School District",
        "Des Moines Community Schools",
        "Des Moines Community School",
    ]

    for wrong in wrong_phrases:
        if wrong in text:
            text = text.replace(
                wrong,
                "Dallas Center-Grimes Community School District",
            )

    # Optional: make the expansion nice when it's used with DCG
    text = text.replace(
        "DCG (Dallas Center-Grimes Community School District)",
        "DCG (Dallas Center-Grimes Community School District)",
    )

    return text


@router.post("/chat/rag")
async def chat_rag(
    payload: RAGRequest,
    _: dict | None = Depends(_auth_guard),
):
    """
    Retrieval-Augmented Chat using the additional_llm_data index (embeddings.jsonl).

    1) Embed user query with nomic-embed-text
    2) Classify intent from the latest user message
    3) Retrieve top-k chunks from embeddings.jsonl (k / threshold depend on intent)
    4) Prepend those as grounded system context
    5) Call Ollama /v1/chat/completions with that context
    """

    base = getattr(settings, "VLLM_ENDPOINT", "http://host.containers.internal:11434").rstrip("/")
    embed_url = f"{base}/api/embeddings"
    chat_url = f"{base}/v1/chat/completions"

    # ---- model / params ----
    model = (payload.model or getattr(settings, "DEFAULT_MODEL", "llama3.2-vision")).strip()
    debug = bool(getattr(payload, "debug", False))

    if model == "llama3.2-vision":
        model = "llama3.2-vision"

    temperature = (
        payload.temperature
        if payload.temperature is not None
        else getattr(settings, "TUTOR_TEMPERATURE", 0.1)
    )

    # Respect caller's max_tokens but cap at 2048, with sane defaults
    requested_max = (
        payload.max_tokens
        if payload.max_tokens is not None
        else getattr(settings, "TUTOR_MAX_TOKENS", 2048)
    )
    try:
        requested_max_int = int(requested_max)
    except (TypeError, ValueError):
        requested_max_int = 2048
    max_tokens = max(1, min(requested_max_int, 2048))

    # ---- 1) last user message ----
    user_messages = [m for m in payload.messages if m.role == "user"]
    if not user_messages:
        raise HTTPException(status_code=400, detail="No user message found")
    query = user_messages[-1].content

    # ---- 1b) classify intent from the latest user query ----
    intent_result = None
    try:
        intent_result = await classify_intent(query)
        intent = intent_result.intent
        intent_value = getattr(intent, "value", str(intent))
        logger.info(
            "[/ai/chat/rag] intent=%s confidence=%s",
            intent_value,
            getattr(intent_result, "confidence", None),
        )
    except Exception as e:
        # If classifier fails for any reason, fall back to "general"
        logger.error("[/ai/chat/rag] classify_intent error: %r", e)
        intent = getattr(Intent, "GENERAL", "general")
        intent_value = getattr(intent, "value", str(intent))

    # ---- 2) embed query ----
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Ollama /api/embeddings expects {"model": "...", "prompt": "..."}
        embed_req = {"model": "nomic-embed-text", "prompt": query}
        er = await client.post(embed_url, json=embed_req)
        if er.status_code >= 400:
            raise HTTPException(status_code=er.status_code, detail=er.text)

        ej = er.json()
        logger.debug("[/ai/chat/rag] embed_raw: %s", ej)

        # Handle multiple possible schemas:
        # 1) OpenAI-style: {"data":[{"embedding":[...]}]}
        # 2) Ollama-style: {"embedding":[...]}
        # 3) Some servers: {"embeddings":[[...], [...]]}
        if isinstance(ej, dict) and "data" in ej:
            vec = ej["data"][0]["embedding"]
        elif isinstance(ej, dict) and "embedding" in ej:
            vec = ej["embedding"]
        elif isinstance(ej, dict) and "embeddings" in ej:
            vec = ej["embeddings"][0]
        else:
            # Surface the full response so you can see what's going on
            raise HTTPException(
                status_code=500,
                detail={"error": "Unexpected embedding response schema", "response": ej},
            )

        query_emb = np.array(vec, dtype="float32")

    # ---- 3) top-k neighbors (intent-aware) ----
    # Choose which additional index to query: main / tutor / agent
    requested_index = (payload.index or "main").strip()
    if requested_index not in INDEX_KINDS:
        logger.warning(
            "[/ai/chat/rag] WARNING: unknown index '%s', falling back to 'main'. "
            "Valid values: %s",
            requested_index,
            ", ".join(INDEX_KINDS),
        )
        requested_index = "main"

    # Default retrieval config
    k = 32
    score_threshold = 0.80
    top_n = 2

    # Use the string value so we're decoupled from exact Enum implementation
    iv = intent_value

    # Example: widen retrieval for staff-directory style queries
    if iv == "staff_directory":
        k = 64
        score_threshold = 0.60
        top_n = 32
    # Example: numeric / counts-related queries
    elif iv in ("student_counts", "transfers"):
        k = 32
        score_threshold = 0.70
        top_n = 16
    # Example: superintendent goals might live in goal PDFs/slide decks, keep a bit looser
    elif iv == "superintendent_goals":
        k = 24
        score_threshold = 0.70
        top_n = 12
    elif iv == "enrollment":
        # registration questions may hit no docs → widen window
        k = 16
        score_threshold = 0.40
        top_n = 4
    elif iv == "school_calendar":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
        # or even: filtered_neighbors = []
    elif iv == "schedule_meeting":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
        # or even: filtered_neighbors = []
    elif iv == "bullying_concern":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
        # or even: filtered_neighbors = []
    elif iv == "student_portal":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
        # or even: filtered_neighbors = []
    elif iv == "student_dress_code":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
        # or even: filtered_neighbors = []
    elif iv == "school_hours":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
        # or even: filtered_neighbors = []
    elif iv == "food_allergy_policy":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
        # or even: filtered_neighbors = []
    elif iv == "visitor_safety":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
        # or even: filtered_neighbors = []
    elif iv == "student_transition_support":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
        # or even: filtered_neighbors = []
    elif iv == "volunteering":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
        # or even: filtered_neighbors = []
    elif iv == "board_feedback":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
        # or even: filtered_neighbors = []
    elif iv == "board_meeting_access":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
        # or even: filtered_neighbors = []
    elif iv == "board_records":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
        # or even: filtered_neighbors = []
    elif iv == "grade_appeal":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
        # or even: filtered_neighbors = []
    elif iv == "dei_initiatives":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
        # or even: filtered_neighbors = []
    elif iv == "multilingual_communication":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
        # or even: filtered_neighbors = []
    elif iv == "bond_levy_spending":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
        # or even: filtered_neighbors = []
    elif iv == "family_learning_support":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
        # or even: filtered_neighbors = []
    elif iv == "school_feedback":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
        # or even: filtered_neighbors = []
    elif iv == "school_contact":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
        # or even: filtered_neighbors = []
    elif iv == "transportation_contact":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
        # or even: filtered_neighbors = []
    elif iv == "homework_expectations":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
        # or even: filtered_neighbors = []
    elif iv == "emergency_drills":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
        # or even: filtered_neighbors = []
    elif iv == "graduation_requirements":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
        # or even: filtered_neighbors = []
    elif iv == "operational_risks":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
        # or even: filtered_neighbors = []
    elif iv == "curriculum_governance":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
        # or even: filtered_neighbors = []
    elif iv == "program_equity":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
        # or even: filtered_neighbors = []
    elif iv == "curriculum_timeline":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
        # or even: filtered_neighbors = []
    elif iv == "essa_accountability":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
        # or even: filtered_neighbors = []
    elif iv == "new_teacher_support":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
        # or even: filtered_neighbors = []
    elif iv == "professional_learning_priorities":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "staff_culture_development":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_support_team":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "resource_prioritization":
        # Calendar questions might hit a specific calendar PDF or not be in RAG at all.
        # You can either search widely, or skip RAG and tell the LLM to direct them to the calendar.
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "instructional_technology_integration":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "building_practice_improvement":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "academic_progress_monitoring":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "data_dashboard_usage":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "leadership_reflection":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "communication_strategy":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "family_concerns":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "district_leadership":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "instructional_practice":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "contact_information":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "staff_recruit":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_behavior_interventions":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_fundraising":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "parent_involvement":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_infrastructure":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "special_education":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_assessment":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "after_school_programs":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "diversity_inclusion_policy":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "health_services":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_security":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "parent_communication":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_discipline":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "college_preparation":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "social_emotional_learning":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "technology_access":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_improvement_plan":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_feedback":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "community_partnerships":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "alumni_relations":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "miscarriage_policy":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "early_childhood_education":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_mentorship":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "cultural_events":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_lunch_program":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "homeroom_structure":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_enrichment":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_inclusion":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_illness_policy":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "volunteer_opportunities":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "collaborative_teaching":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_retention":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_evacuation_plans":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "intervention_strategies":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_awards":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "dropout_prevention":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "teacher_evaluation":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "special_events":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "curriculum_integration":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "field_trips":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_attendance":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_spirit":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "classroom_management":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_health_records":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "parent_involvement_events":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "teacher_training":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_uniform_policy":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_cultural_committees":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_business_partnerships":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_community_outreach":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "equal_access_to_opportunities":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "counselor_support":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "diversity_equity_policy":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_recognition_programs":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "teacher_mentoring":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "peer_tutoring":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_closures":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "district_budget":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "parent_surveys":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_portfolios":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "activity_fee_policy":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_photography":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_policies":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_graduation_plan":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "math_support_program":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "reading_support_program":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_budget_oversight":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_travel_policy":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "extrahelp_tutoring":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "enrichment_programs":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_compliance":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "parent_teacher_association":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_career_services":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_scholarship_opportunities":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_support_services":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_conflict_resolution":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "dropout_intervention":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_assignment_tracking":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "support_for_special_populations":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_voice":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "grading_policy":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "facility_repairs":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "afterschool_clubs":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "peer_relationships":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "early_intervention":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_mascot":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_leadership":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "parental_rights":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "alumni_engagement":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "bullying_training":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_funding":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_disaster_preparedness":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_health_screenings":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "accessibility_in_education":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "inclusion_policy":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_community_events":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "internal_communication":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "extracurricular_funding":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_orientation":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_culture_initiatives":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_retention_strategies":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "family_school_partnerships":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "campus_cleanliness":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "professional_development_evaluation":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_behavior_monitoring":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "diversity_and_inclusion_training":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_broadcasts":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "food_nutrition_programs":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_climate_surveys":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "athletic_funding":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "teacher_feedback_mechanisms":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "gifted_education":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "campus_recreation":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "peer_mediation":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "alumni_network":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_financial_aid":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "parental_involvement_training":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_partnerships":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_building_maintenance":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_engagement_measurements":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "community_outreach_programs":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_transportation_support":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "recruitment_and_retention_for_support_staff":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_leadership_development":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_business_partnerships":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_medical_accommodations":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "parent_teacher_conferences":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "extra_credit_opportunities":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "teacher_assistant_support":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "financial_aid_training":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_mobility":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_promotions":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_arts_programs":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "alumni_engagement_events":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_community_service":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_closure_protocols":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_psychological_support":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "parent_support_groups":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "conflict_of_interest_policies":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "interschool_collaboration":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_event_scheduling":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "teacher_contract_negotiations":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "summer_learning_programs":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_mobility_and_transition":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "staff_wellness":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "technology_support_for_teachers":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "community_feedback_on_school_policy":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "peer_support_networks":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_enrollment_forecasting":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_activity_registration":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_computer_lab_access":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_website_access":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "online_courses":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_report_cards":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "teacher_facilitator":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_mental_health_support":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "teacher_collaboration":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_policies_oversight":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_closure_notifications":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "parent_school_communication":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_tutoring_services":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "international_student_support":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "math_intervention_program":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "reading_intervention_program":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "extra_credit_opportunities":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_retention_strategies":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "staff_training_opportunities":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_inspection_reports":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_homework_help":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_field_trip_permission":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_participation_fees":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_disaster_recovery":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_behavior_rewards":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_bullying_policy":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "parent_feedback_surveys":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_mental_health_evaluation":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "college_readiness_programs":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_extracurricular_registration":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_school_id":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_uniform_policy":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "transportation_routes":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_reporting_system":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "academic_intervention_teams":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_reading_programs":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "parent_portal_setup":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_behavior_contracts":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_counseling_services":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_financial_aid_opportunities":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_community_partnerships":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_bus_route_planning":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "campus_security_updates":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "parent_participation_in_school_events":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_drop_out_prevention":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_performance_reports":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "special_education_programs":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_nurse_services":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_career_exploration":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_partnership_with_local_businesses":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_school_mascot":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "parent_communication_platform":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "after_school_study_sessions":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_financial_assistance_requests":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "specialized_school_services":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_aid_requests":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_gardening_programs":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_sports_teams":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_property_insurance":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_budget_allocations":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_computer_accessibility":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "parent_teacher_conferences":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_discipline_policy":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_graduation_ceremonies":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "after_school_extra_credit_opportunities":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_transportation_services":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "diversity_and_inclusion_training":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "after_school_homework_club":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_feedback_forms":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_compliance_with_regulations":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_parking_policy":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_security_training":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_assessment_results":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "parental_consent_for_medical_treatment":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "after_school_club_meetings":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_graduation_credentials":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_nutrition_program":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_evacuations_plan":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_transportation_policies":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_virtual_learning_support":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "afterschool_tutoring_programs":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_admission_fees":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_peer_mentoring":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_workstudy_opportunities":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "parent_feedback_for_school_policies":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "parent_teacher_association_meetings":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "student_volunteer_opportunities":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_athletic_events":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_talent_shows":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_debate_teams":
        k = 32
        score_threshold = 0.4
        top_n = 4
    elif iv == "school_uniforms":
        k = 32
        score_threshold = 0.4
        top_n = 4










    logger.info(
        "[/ai/chat/rag] retrieval_config intent=%s k=%s score_threshold=%.2f top_n=%s",
        iv,
        k,
        score_threshold,
        top_n,
    )

    # Broader retrieval so the model can see more staff-directory chunks etc.
    neighbors = top_k(query_emb, k=k, index=requested_index)

    filtered_neighbors = [
        (score, chunk) for (score, chunk) in neighbors if score >= score_threshold
    ][:top_n]

    # Detailed debug of retrieval
    logger.info(
        "[/ai/chat/rag] retrieved_neighbors_count=%s index=%s",
        len(neighbors),
        requested_index,
    )
    logger.info(
        "[/ai/chat/rag] using_filtered_neighbors=%s threshold=%.2f top_n=%s",
        len(filtered_neighbors),
        score_threshold,
        top_n,
    )
    for i, (score, chunk) in enumerate(filtered_neighbors[:3]):
        logger.debug(
            "[/ai/chat/rag] hit#%s score=%.4f file=%s idx=%s snippet=%r",
            i,
            score,
            getattr(chunk, "filename", "?"),
            getattr(chunk, "chunk_index", "?"),
            chunk.text[:200],
        )

    if not filtered_neighbors:
        context = "No relevant local context found in the DCG PDFs."
    else:
        parts = []
        for score, chunk in filtered_neighbors:
            # image metadata in the context (for the model, optional)
            image_paths = getattr(chunk, "image_paths", None) or []
            meta = f"[score={score:.3f} | file={chunk.filename} | idx={chunk.chunk_index}]"
            if image_paths:
                meta += f" | images={len(image_paths)} attached"
            parts.append(f"{meta}\n{chunk.text}")
        context = "\n\n".join(parts)

    # DEBUG: log what we retrieved so you can verify it’s using the right index
    logger.info(
        "[/ai/chat/rag] retrieved_chunks(filtered)=%s",
        len(filtered_neighbors),
    )
    if filtered_neighbors:
        first_score, first_chunk = filtered_neighbors[0]
        logger.debug(
            "[/ai/chat/rag] first_chunk_snippet index=%s score=%.3f file=%s idx=%s %r",
            requested_index,
            first_score,
            getattr(first_chunk, "filename", "?"),
            getattr(first_chunk, "chunk_index", "?"),
            first_chunk.text[:300],
        )

    # ---- 4) build grounded system prompt (with safety rules) ----
    system_text = (
        "In this conversation, the acronym 'DCG' ALWAYS means 'Dallas Center-Grimes Community "
        "School District' and never anything else. It does NOT mean Des Moines Christian or any "
        "other organization. If you expand 'DCG', expand it only as 'Dallas Center-Grimes "
        "Community School District'.\n\n"
        "Safety and content rules:\n"
        "- Keep all responses appropriate for a K–12 school community (students, families, staff).\n"
        "- Do NOT use profanity, slurs, or hateful/harassing language. If the user uses such "
        "language, respond in a calm, neutral, and professional tone without repeating it.\n"
        "- Do NOT provide sexual content, descriptions of nudity, or sexually explicit material.\n"
        "- Do NOT engage in flirting or romantic roleplay.\n"
        "- If a request involves sexual content, nudity, or other inappropriate material, "
        "politely refuse and redirect to age-appropriate, educational information instead.\n"
        "- Do NOT provide detailed self-harm instructions, weapons instructions, or illegal activity guidance.\n\n"
        "Use ONLY the information in the CONTEXT below when answering questions about staff, "
        "roles, titles, or district details.\n\n"
        f"CONTEXT:\n{context}\n\n"
        "Answer clearly. If you mention a staff role (like Superintendent), give the name and role when present."
    )

    messages = [
        {"role": "system", "content": system_text},
        *[m.model_dump() for m in payload.messages],
    ]

    chat_req = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        # ---- first completion call ----
        r = await client.post(chat_url, json=chat_req)

        logger.info(
            "[/ai/chat/rag] upstream_v1 status=%s bytes=%s",
            r.status_code,
            len(r.content),
        )

        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)

        data = r.json()

        # ---- AUTO-CONTINUE LOOP: if finish_reason == 'length', keep going ----
        try:
            choices = data.get("choices") or []
            first = choices[0] if choices else {}
            finish_reason = first.get("finish_reason")
            msg = first.get("message") or {}
            content = msg.get("content", "") or ""

            full_content = content
            continue_count = 0
            max_continues = 5  # safety guard; bump if you want even more

            while finish_reason == "length" and continue_count < max_continues:
                continue_count += 1
                logger.info(
                    "[/ai/chat/rag] auto-continue pass=%s current_len=%s",
                    continue_count,
                    len(full_content),
                )

                # Extend the conversation with the previous assistant text and a "continue" request
                messages.append({"role": "assistant", "content": content})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Continue the previous list from where you left off. "
                            "Do NOT repeat any previous names; only add new ones based on the same CONTEXT."
                        ),
                    }
                )
                chat_req["messages"] = messages

                r2 = await client.post(chat_url, json=chat_req)
                logger.info(
                    "[/ai/chat/rag] upstream_v1 (continue) status=%s bytes=%s",
                    r2.status_code,
                    len(r2.content),
                )
                if r2.status_code >= 400:
                    logger.error(
                        "[/ai/chat/rag] auto-continue aborted: upstream error %s",
                        r2.status_code,
                    )
                    break

                data2 = r2.json()
                choices2 = data2.get("choices") or []
                first2 = choices2[0] if choices2 else {}
                finish_reason = first2.get("finish_reason")
                msg2 = first2.get("message") or {}
                content = msg2.get("content", "") or ""

                full_content += content
                data = data2  # keep latest metadata for usage / finish_reason logs

            # Ensure final `data` carries the stitched-together content
            if data.get("choices"):
                data["choices"][0].setdefault("message", {})
                data["choices"][0]["message"]["content"] = full_content

        except Exception as e:
            logger.exception("[/ai/chat/rag] auto-continue failed: %r", e)

        # ---- quick debug on final model behavior ----
        try:
            choices = data.get("choices") or []
            first = choices[0] if choices else {}
            finish_reason = first.get("finish_reason")
            usage = data.get("usage") or {}
            msg = first.get("message") or {}
            content = msg.get("content", "")

            logger.info(
                "[/ai/chat/rag] finish_reason=%s prompt_tokens=%s completion_tokens=%s content_len=%s",
                finish_reason,
                usage.get("prompt_tokens"),
                usage.get("completion_tokens"),
                len(content or ""),
            )
            logger.debug("[/ai/chat/rag] content tail: %r", (content or "")[-200:])
        except Exception as e:
            logger.exception("[/ai/chat/rag] debug inspection failed: %r", e)

        # normalize DCG expansion + redact outbound if needed
        for choice in data.get("choices", []):
            msg = choice.get("message") or {}
            if isinstance(msg.get("content"), str):
                content = msg["content"]
                # 1) fix any wrong DCG expansions
                content = _normalize_dcg_expansion(content)
                # 2) apply your existing PII redaction
                content = redact_pii(content)
                msg["content"] = content

        # ---- build retrieved_chunks payload from filtered_neighbors ----
        retrieved_chunks = []
        for score, chunk in filtered_neighbors:
            retrieved_chunks.append(
                {
                    "score": float(score),
                    "filename": getattr(chunk, "filename", None),
                    "chunk_index": getattr(chunk, "chunk_index", None),
                    "text_preview": chunk.text[:800],
                    "image_paths": getattr(chunk, "image_paths", None),
                    "page_index": getattr(chunk, "page_index", None),
                    "page_chunk_index": getattr(chunk, "page_chunk_index", None),
                }
            )

        # ---- final payload: always answer + retrieved_chunks + intent ----
        base_response = {
            "answer": data,
            "retrieved_chunks": retrieved_chunks,
            "index": requested_index,
            "intent": intent_value,
        }

        if intent_result is not None:
            base_response["intent_confidence"] = getattr(intent_result, "confidence", None)

        if debug:
            return base_response

        # (non-debug currently returns the same – but this lets you diverge later if you want)
        return base_response
