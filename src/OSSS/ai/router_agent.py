# src/OSSS/ai/router_agent.py
from __future__ import annotations

from typing import Optional, List, Any
import logging
import json

import httpx
import numpy as np
from pydantic import BaseModel, Field
import re

import sys

# ----------------------------------------------------------------------
# MetaGPT Integration (optional)
# ----------------------------------------------------------------------
# NOTE: This path manipulation is here so that the MetaGPT library
# (and its roles registry) can be discovered when running in your
# containerized dev environment.
# If you later package this differently, consider replacing this with
# a proper PYTHONPATH or poetry/uv install instead of sys.path hacks.
sys.path.append("/workspace/src/MetaGPT")

from MetaGPT.roles_registry import ROLE_REGISTRY  # noqa: F401
from MetaGPT.roles.registration import RegistrationRole  # noqa: F401

from OSSS.ai.intent_classifier import classify_intent
from OSSS.ai.intents import Intent
from OSSS.ai.agents import AgentContext, get_agent
from OSSS.ai.additional_index import top_k, INDEX_KINDS
from OSSS.ai.session_store import RagSession, touch_session

# 👇 Force-load student registration agents so @register_agent runs
# This ensures that the registration agent is registered with the
# global agent registry as soon as this module is imported.
import OSSS.ai.agents.student.registration_agent  # noqa: F401

# Pattern used to detect user replies that *look like* school years.
# E.g. "2025-26", "2025/26", "2030-31", etc.
YEAR_PATTERN = re.compile(r"(20[2-9][0-9])[-/](?:20[2-9][0-9]|[0-9]{2})")

logger = logging.getLogger("OSSS.ai.router_agent")


# ----------------------------------------------------------------------
# ChatMessage + redact_pii: prefer real gateway definitions
# ----------------------------------------------------------------------
# We try to reuse ChatMessage (and redact_pii) from the public API layer
# so that the same schema is shared between gateway and internal router.
try:
    from OSSS.api.routers.ai_gateway import ChatMessage, redact_pii  # type: ignore
except Exception:
    # Fallback definitions for dev/test environments or when the gateway
    # module is not available.
    class ChatMessage(BaseModel):
        role: str
        content: str

    def redact_pii(text: str) -> str:
        return text


# ----------------------------------------------------------------------
# Settings: prefer real OSSS.config.settings, fall back otherwise
# ----------------------------------------------------------------------
try:
    from OSSS.config import settings as _settings  # type: ignore

    settings = _settings
except Exception:  # fallback, same as in your ai_gateway
    class _Settings:
        VLLM_ENDPOINT: str = "http://host.containers.internal:11434"
        TUTOR_TEMPERATURE: float = 0.2
        TUTOR_MAX_TOKENS: int = 8192
        DEFAULT_MODEL: str = "llama3.2-vision"

    settings = _Settings()  # type: ignore


# ----------------------------------------------------------------------
# Intent alias mapping
# ----------------------------------------------------------------------
# The intent classifier may emit *labels* that are not exactly the same
# as the agent’s canonical intent_name. This mapping allows us to:
#   - Keep classifier labels natural/loose (e.g. "enrollment")
#   - Map to a concrete agent (e.g. "register_new_student")
INTENT_ALIASES: dict[str, str] = {
    "enrollment": "register_new_student",
    "new_student_registration": "register_new_student",
    # Add more synonyms as you create new agents
}


def _looks_like_school_year(text: str) -> bool:
    """
    Heuristic: detect user messages that *look like* a school-year value.

    Examples that should match:
        - "2024-25"
        - "2025-26"
        - "2025/26"

    Why we care:
      - When the user is mid-registration flow, they might reply
        with just "2025-26" as a bare answer.
      - That should be routed to the registration agent, even if the
        classifier decides it's "general".

    NOTE: This is intentionally not a strict validator; it's just a
    lightweight heuristic used for routing.
    """
    if not text:
        return False

    q = text.strip()
    # Normalize "fancy" Unicode dashes to a simple single hyphen.
    q = q.replace("–", "-").replace("—", "-")
    return bool(YEAR_PATTERN.search(q))


# ======================================================================
# IntentResolution
# ======================================================================
class IntentResolution(BaseModel):
    """
    Structured summary of how the router decided on an intent.

    Fields
    ------
    intent : str
        Final effective intent label (after aliases and heuristics).
        This is what is used to choose an agent or decide RAG fallback.

    action : str | None
        Optional action label (e.g., "read", "search", "summarize").
        Produced by the classifier, may be used for future fine-grained
        routing or instrumentation.

    action_confidence : float | None
        Confidence score from the classifier, if available.

    within_registration_flow : bool
        Indicates whether we consider this turn part of an ongoing
        registration workflow. Influences how base_label is chosen.

    classified_label : str | None
        Raw label from the classifier (before aliasing).

    forced_intent : str | None
        If set, this indicates that heuristics overrode the classifier
        and manual intent, e.g. "register_new_student" based on keywords.

    session_intent : str | None
        Sticky intent stored on the RagSession (e.g. registration intent).

    manual_label : str | None
        Optional explicit override from the client (rag.intent), if set.
    """

    intent: str
    action: str | None = None
    action_confidence: float | None = None
    within_registration_flow: bool = False
    classified_label: str | None = None
    forced_intent: str | None = None
    session_intent: str | None = None
    manual_label: str | None = None


# ======================================================================
# IntentResolver
# ======================================================================
class IntentResolver:
    """
    Responsible for all **intent resolution logic** for a given turn.

    Responsibilities
    ----------------
    - Apply simple heuristics for registration-related queries
      (e.g., “register new student”, bare school-year replies).
    - Call the classifier (`classify_intent`) and normalize its label.
    - Incorporate prior session intent (sticky flows).
    - Combine:
        * manual client-provided intent
        * forced heuristics
        * classifier label
        * prior session intent
      into a single final `intent` label.

    This class is intentionally separated so you can unit-test intent
    resolution in isolation from HTTP, RAG retrieval, or agent dispatch.
    """

    async def resolve(
        self,
        rag: "RAGRequest",
        session: RagSession,
        query: str,
    ) -> IntentResolution:
        """
        Compute the effective intent for the given turn.

        Parameters
        ----------
        rag : RAGRequest
            The full RAG request payload (includes optional intent override).
        session : RagSession
            Session object that may store sticky intent info.
        query : str
            The user's latest natural-language message.

        Returns
        -------
        IntentResolution
            Detailed breakdown of the chosen intent and contributing signals.
        """
        ql = (query or "").lower()

        # ------------------------------------------------------------------
        # 1) Manual override from client (if provided)
        # ------------------------------------------------------------------
        manual_label = rag.intent

        # ------------------------------------------------------------------
        # 2) Heuristics for registration-related queries
        # ------------------------------------------------------------------
        forced_intent: str | None = None
        if "register" in ql and "new student" in ql:
            # Highly specific pattern: treat as explicit registration
            forced_intent = "register_new_student"
            logger.info(
                "RouterAgent: forcing intent to %s based on query text=%r",
                forced_intent,
                query[:200],
            )
        elif _looks_like_school_year(query):
            # Bare school-year answer, likely mid-registration
            forced_intent = "register_new_student"
            logger.info(
                "RouterAgent: treating bare school-year answer as registration; query=%r",
                query[:200],
            )

        # ------------------------------------------------------------------
        # 3) Session-intent stickiness
        # ------------------------------------------------------------------
        session_intent = getattr(session, "intent", None)

        # ------------------------------------------------------------------
        # 4) Classifier call (best-effort)
        # ------------------------------------------------------------------
        classified: str | Intent | None = "general"
        action: str | None = "read"
        action_confidence: float | None = None

        try:
            intent_result = await classify_intent(query)
            classified = intent_result.intent
            action = getattr(intent_result, "action", None) or "read"
            action_confidence = getattr(intent_result, "action_confidence", None)
            logger.info(
                "Classified intent=%s action=%s action_confidence=%s",
                getattr(classified, "value", classified),
                action,
                action_confidence,
            )
        except Exception as e:
            # If classifier fails, we still try to route using heuristics
            logger.error("Error classifying intent: %s", e)

        # Normalize classifier label into a simple string
        if isinstance(classified, Intent):
            classified_label: str | None = classified.value
        elif isinstance(classified, str):
            classified_label = classified
        else:
            classified_label = None

        # ------------------------------------------------------------------
        # 5) Registration-flow stickiness logic
        # ------------------------------------------------------------------
        within_registration_flow = False

        if session_intent == "register_new_student":
            # If the session already "belongs" to registration, keep it there
            within_registration_flow = True
        elif rag.subagent_session_id and (
            classified_label in (None, "general", "enrollment", "register_new_student")
            or session_intent in (None, "register_new_student")
        ):
            # We have a registration sub-session; unless the classifier
            # strongly says otherwise, treat as part of the same flow.
            within_registration_flow = True
        elif _looks_like_school_year(query):
            # Bare school-year reply is almost certainly registration
            within_registration_flow = True

        # ------------------------------------------------------------------
        # 6) Base label priority: which source wins?
        # ------------------------------------------------------------------
        if within_registration_flow:
            # If we’re in a registration flow, prefer that strongly
            base_label = "register_new_student"
        else:
            # Otherwise pick from the following, in order:
            # manual > forced > classifier > session > "general"
            base_label = (
                manual_label
                or forced_intent
                or classified_label
                or session_intent
                or "general"
            )

        # ------------------------------------------------------------------
        # 7) Apply alias mapping (classifier label → agent intent_name)
        # ------------------------------------------------------------------
        intent_label = INTENT_ALIASES.get(base_label, base_label)

        logger.info(
            "Effective intent for this turn: %r (manual=%r, forced=%r, "
            "session_intent=%r, classified=%r, aliased_from=%r)",
            intent_label,
            manual_label,
            forced_intent,
            session_intent,
            classified_label,
            base_label,
        )

        return IntentResolution(
            intent=intent_label,
            action=action,
            action_confidence=action_confidence,
            within_registration_flow=within_registration_flow,
            classified_label=classified_label,
            forced_intent=forced_intent,
            session_intent=session_intent,
            manual_label=manual_label,
        )


# ======================================================================
# AgentDispatcher
# ======================================================================
class AgentDispatcher:
    """
    Handles delegation of a turn to a **specialized agent**, if one exists.

    Responsibilities
    ----------------
    - Look up an agent by intent via `get_agent(intent_label)`.
    - Fallback to registration agent if the registry entry is missing.
    - Construct a fully-populated AgentContext.
    - Call `agent.run(ctx)` and convert its AgentResult into the
      standard `/ai/chat/rag` HTTP response shape.
    - Attach an `agent_trace` structure for debugging/observability.

    Returns
    -------
    dict | None
        - A JSON-serializable dict when an agent successfully handles the turn.
        - None if no agent exists for that intent (caller should use RAG fallback).
    """

    async def dispatch(
        self,
        *,
        intent_label: str,
        query: str,
        rag: "RAGRequest",
        session: RagSession,
        session_files: list[str],
        action: str | None,
        action_confidence: float | None,
    ) -> dict | None:
        """
        Dispatch a single turn to a specialized agent, if available.

        Parameters
        ----------
        intent_label : str
            Final intent label from IntentResolver.
        query : str
            Most recent user message.
        rag : RAGRequest
            Full RAG request, including model, messages, etc.
        session : RagSession
            Shared session object for this conversation.
        session_files : list[str]
            Names of files uploaded for this session (for context).
        action : str | None
            Optional action label from classifier.
        action_confidence : float | None
            Confidence score from classifier.

        Returns
        -------
        dict | None
            Fully-formed response dict if an agent handled the turn,
            otherwise None.
        """
        agent_session_id = session.id
        agent_id: Optional[str] = rag.agent_id
        agent_name: Optional[str] = rag.agent_name

        # ------------------------------------------------------------------
        # 1) Look up agent from registry
        # ------------------------------------------------------------------
        agent = get_agent(intent_label)

        # Hard fallback for registration if wiring ever breaks
        if agent is None and intent_label == "register_new_student":
            try:
                from OSSS.ai.agents.student.registration import RegisterNewStudentAgent

                logger.info(
                    "No registry agent found for intent=%s; "
                    "falling back to direct RegisterNewStudentAgent()",
                    intent_label,
                )
                agent = RegisterNewStudentAgent()
            except Exception as e:
                logger.exception(
                    "Failed to import/instantiate RegisterNewStudentAgent for "
                    "intent=%s: %s",
                    intent_label,
                    e,
                )

        if agent is None:
            # No agent for this intent; the caller (RouterAgent) should
            # proceed with the generic RAG fallback path.
            return None

        logger.info("Dispatching to agent for intent=%s", intent_label)

        # ------------------------------------------------------------------
        # 2) Build AgentContext for the sub-agent
        # ------------------------------------------------------------------
        ctx = AgentContext(
            query=query,
            session_id=agent_session_id,  # logical / current session id
            agent_id=agent_id,
            agent_name=agent_name,
            intent=intent_label,
            action=action,
            action_confidence=action_confidence,
            main_session_id=agent_session_id,            # top-level RAG session id
            subagent_session_id=rag.subagent_session_id, # sub-flow continuation id
            metadata={"session_files": session_files},
            retrieved_chunks=[],
        )

        # ------------------------------------------------------------------
        # 3) Call agent.run and handle errors
        # ------------------------------------------------------------------
        try:
            agent_result = await agent.run(ctx)
        except Exception as e:
            logger.exception(
                "Agent '%s' failed; falling back to error payload", intent_label
            )
            # Build a clear, user-safe error payload
            error_response = {
                "answer": {
                    "message": {
                        "role": "assistant",
                        "content": (
                            "There was an error while handling your request with the specialized "
                            "agent. Please try again later or rephrase your question."
                        ),
                    },
                    "status": "error",
                },
                "retrieved_chunks": [],
                "index": getattr(rag, "index", "main"),
                "intent": intent_label,
                "error": "agent_error",
                "details": str(e),
                "agent_session_id": agent_session_id,
                "session_files": session_files,
                "agent_id": agent_id,
                "agent_name": agent_name,
                "action": action,
                "action_confidence": action_confidence,
                "agent_trace": _build_agent_trace(
                    {
                        "agent": getattr(agent, "__class__", type(agent)).__name__,
                        "status": "error",
                        "intent": intent_label,
                        "children": [],
                    },
                    intent_label=intent_label,
                ),
            }
            logger.info(
                "[RAG] response (agent error): %s",
                json.dumps(error_response, ensure_ascii=False)[:4000],
            )
            return error_response

        # ------------------------------------------------------------------
        # 4) Convert AgentResult into HTTP response shape
        # ------------------------------------------------------------------
        agent_trace = _build_agent_trace(agent_result, intent_label=intent_label)

        user_response: dict[str, Any] = {
            "answer": {
                "message": {
                    "role": "assistant",
                    "content": getattr(agent_result, "answer_text", ""),
                },
                "status": getattr(agent_result, "status", "ok"),
            },
            "retrieved_chunks": getattr(agent_result, "extra_chunks", []),
            "index": getattr(agent_result, "index", getattr(rag, "index", "main")),
            "intent": getattr(agent_result, "intent", intent_label),
            "agent_session_id": agent_session_id,
            "subagent_session_id": getattr(agent_result, "agent_session_id", None),
            "session_files": session_files,
            "agent_id": getattr(agent_result, "agent_id", agent_id),
            "agent_name": getattr(agent_result, "agent_name", agent_name),
            "action": action,
            "action_confidence": action_confidence,
            "agent_trace": agent_trace,
        }

        # Optional: surface agent_debug_information for UI / logs
        try:
            data_field = getattr(agent_result, "data", None)
            if isinstance(data_field, dict):
                debug_info = data_field.get("agent_debug_information")
                if debug_info is not None:
                    user_response["agent_debug_information"] = debug_info
        except Exception:
            logger.exception(
                "Failed to extract agent_debug_information from AgentResult"
            )

        logger.info(
            "[RAG] response (agent=%s): %s",
            intent_label,
            json.dumps(user_response, ensure_ascii=False)[:4000],
        )
        return user_response


# ======================================================================
# RagEngine
# ======================================================================
class RagEngine:
    """
    Encapsulates **generic RAG fallback** behavior:

      - Call embeddings endpoint to embed the query.
      - Use `top_k` to retrieve ranked chunks from the local index.
      - Build a DCG-aware system prompt with strict "no guessing" rules.
      - Call chat completion endpoint (LLM).
      - Perform auto-continue for long lists (same pattern as prior code).
      - Normalize "DCG" expansions and redact PII.
      - Emit a response payload in the same shape as agent results.

    This class intentionally isolates RAG mechanics from RouterAgent so
    you can swap/upgrade RAG behavior without changing intent logic.
    """

    def __init__(self, *, embed_url: str, chat_url: str) -> None:
        self.embed_url = embed_url
        self.chat_url = chat_url

    async def answer(
        self,
        *,
        rag: "RAGRequest",
        session: RagSession,
        query: str,
        intent_label: str,
        session_files: list[str],
        action: str | None,
        action_confidence: float | None,
    ) -> dict:
        """
        Run the **full RAG flow** for a query that has no specialized agent.

        Parameters
        ----------
        rag : RAGRequest
            RAG payload including model, messages, etc.
        session : RagSession
            Logical session, used mainly for id and logging.
        query : str
            Last user message content.
        intent_label : str
            Effective intent, even if we are in generic RAG mode.
        session_files : list[str]
            Names of any uploaded files associated with this session.
        action : str | None
            Optional classifier action.
        action_confidence : float | None
            Optional classifier confidence.

        Returns
        -------
        dict
            JSON-serializable structure to return from /ai/chat/rag.
        """
        agent_session_id = session.id
        agent_id: Optional[str] = rag.agent_id
        agent_name: Optional[str] = rag.agent_name

        # ------------------------------------------------------------------
        # 1) Get embeddings for the user's query
        # ------------------------------------------------------------------
        async with httpx.AsyncClient(timeout=10.0) as client:
            embed_req = {"model": "nomic-embed-text", "prompt": query}
            er = await client.post(self.embed_url, json=embed_req)
            if er.status_code >= 400:
                raise RuntimeError(
                    f"Embedding endpoint error {er.status_code}: {er.text}"
                )

            ej = er.json()
            # Support multiple common embedding response shapes
            if isinstance(ej, dict) and "data" in ej:
                vec = ej["data"][0]["embedding"]
            elif isinstance(ej, dict) and "embedding" in ej:
                vec = ej["embedding"]
            elif isinstance(ej, dict) and "embeddings" in ej:
                vec = ej["embeddings"][0]
            else:
                raise RuntimeError(f"Unexpected embedding response schema: {ej!r}")

            query_emb = np.array(vec, dtype="float32")

        # ------------------------------------------------------------------
        # 2) Perform retrieval against the chosen index
        # ------------------------------------------------------------------
        requested_index = (rag.index or "main").strip()
        if requested_index not in INDEX_KINDS:
            logger.warning(
                "Unknown index '%s', falling back to 'main'. Valid values: %s",
                requested_index,
                ", ".join(INDEX_KINDS),
            )
            requested_index = "main"

        neighbors = top_k(query_emb, k=12, index=requested_index)

        if not neighbors:
            context = "No relevant local context found in the DCG PDFs."
        else:
            parts = []
            for score, chunk in neighbors:
                image_paths = getattr(chunk, "image_paths", None) or []
                meta = f"[score={score:.3f} | file={chunk.filename} | idx={chunk.chunk_index}]"
                if image_paths:
                    meta += f" | images={len(image_paths)} attached"
                parts.append(f"{meta}\n{chunk.text}")
            context = "\n\n".join(parts)

        # ------------------------------------------------------------------
        # 3) Build DCG-aware system prompt
        # ------------------------------------------------------------------
        system_text = (
            "In this conversation, the acronym 'DCG' ALWAYS means 'Dallas Center-Grimes Community "
            "School District' and never anything else. It does NOT mean Des Moines Christian or any "
            "other organization. If you expand 'DCG', expand it only as 'Dallas Center-Grimes "
            "Community School District'.\n"
            'If the answer is not explicitly in the context, reply exactly:\n'
            '"I\'m not sure from the local directory."\n'
            "Do NOT guess. Do NOT use outside web knowledge.\n\n"
            f"CONTEXT:\n{context}\n\n"
            "Answer clearly. If you mention a staff role (like Superintendent), give the name and role."
        )

        messages = [
            {"role": "system", "content": system_text},
            *[m.model_dump() for m in rag.messages],
        ]

        chat_req = {
            "model": rag.model,
            "messages": messages,
            "temperature": rag.temperature,
            "max_tokens": rag.max_tokens,
            "stream": False,
        }

        # ------------------------------------------------------------------
        # 4) Call chat completion + auto-continue for long lists
        # ------------------------------------------------------------------
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(self.chat_url, json=chat_req)
            if r.status_code >= 400:
                raise RuntimeError(
                    f"Chat completion endpoint error {r.status_code}: {r.text}"
                )

            data = r.json()

            # Auto-continue logic: if finish_reason == "length", keep asking
            try:
                choices = data.get("choices") or []
                first = choices[0] if choices else {}
                finish_reason = first.get("finish_reason")
                msg = first.get("message") or {}
                content = msg.get("content", "") or ""

                full_content = content
                continue_count = 0
                max_continues = 20

                while finish_reason == "length" and continue_count < max_continues:
                    continue_count += 1

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

                    r2 = await client.post(self.chat_url, json=chat_req)
                    if r2.status_code >= 400:
                        logger.warning(
                            "Auto-continue aborted: upstream error %s", r2.status_code
                        )
                        break

                    data2 = r2.json()
                    choices2 = data2.get("choices") or []
                    first2 = choices2[0] if choices2 else {}
                    finish_reason = first2.get("finish_reason")
                    msg2 = first2.get("message") or {}
                    content = msg2.get("content", "") or ""

                    full_content += content
                    data = data2

                if data.get("choices"):
                    data["choices"][0].setdefault("message", {})
                    data["choices"][0]["message"]["content"] = full_content

            except Exception as e:
                logger.warning("auto-continue failed: %s", e)

            # ------------------------------------------------------------------
            # 5) Basic logging of completion metadata
            # ------------------------------------------------------------------
            try:
                choices = data.get("choices") or []
                first = choices[0] if choices else {}
                finish_reason = first.get("finish_reason")
                usage = data.get("usage") or {}
                msg = first.get("message") or {}
                content = msg.get("content", "")

                logger.info(
                    "[RAG] finish_reason=%s prompt_tokens=%s completion_tokens=%s content_len=%s",
                    finish_reason,
                    usage.get("prompt_tokens"),
                    usage.get("completion_tokens"),
                    len(content),
                )
            except Exception as e:
                logger.warning("debug inspection failed: %s", e)

            # ------------------------------------------------------------------
            # 6) Post-process model output (DCG normalization + PII redaction)
            # ------------------------------------------------------------------
            for choice in data.get("choices", []):
                msg = choice.get("message") or {}
                if isinstance(msg.get("content"), str):
                    content = msg["content"]
                    content = _normalize_dcg_expansion(content)
                    content = redact_pii(content)
                    msg["content"] = content

            # ------------------------------------------------------------------
            # 7) Build retrieved_chunks for UI “Sources” panel
            # ------------------------------------------------------------------
            debug_neighbors = []
            for score, chunk in neighbors:
                debug_neighbors.append(
                    {
                        "score": float(score),
                        "filename": getattr(chunk, "filename", None),
                        "chunk_index": getattr(chunk, "chunk_index", None),
                        "text_preview": chunk.text[:800],
                        "image_paths": getattr(chunk, "image_paths", None),
                        "page_index": getattr(chunk, "page_index", None),
                        "page_chunk_index": getattr(chunk, "page_chunk_index", None),
                        "source": getattr(chunk, "source", None),
                        "pdf_index_path": getattr(chunk, "pdf_index_path", None),
                    }
                )

            # Build a synthetic leaf for agent_trace (RAG fallback)
            rag_fallback_leaf = {
                "agent": "rag_fallback",
                "status": "ok",
                "intent": intent_label,
                "children": [],
            }
            agent_trace = _build_agent_trace(
                rag_fallback_leaf, intent_label=intent_label
            )

            response_payload = {
                "answer": data,
                "retrieved_chunks": debug_neighbors,
                "index": requested_index,
                "intent": intent_label,
                "agent_session_id": agent_session_id,
                "session_files": session_files,
                "agent_id": agent_id,
                "agent_name": agent_name,
                "action": action,
                "action_confidence": action_confidence,
                "agent_trace": agent_trace,
            }

            logger.info(
                "[RAG] response (rag_fallback): %s",
                json.dumps(response_payload, ensure_ascii=False)[:4000],
            )

            return response_payload


# ======================================================================
# RouterAgent
# ======================================================================
class RouterAgent:
    """
    The **top-level orchestrator** for OSSS's AI routing pipeline.

    Responsibilities
    ----------------
    - Normalize model/temperature/max_tokens from the incoming RAG payload.
    - Extract the latest user message.
    - Use IntentResolver to decide:
        * final intent label
        * action
        * confidence
        * registration-flow status
    - Persist intent + query into RagSession via touch_session.
    - Attempt to dispatch to a specialized Agent via AgentDispatcher.
    - If no agent handles the turn, fall back to RagEngine.answer().

    This is “the brain” of /ai/chat/rag that ties everything together.
    """

    def __init__(self) -> None:
        base = getattr(
            settings, "VLLM_ENDPOINT", "http://host.containers.internal:11434"
        ).rstrip("/")
        embed_url = f"{base}/api/embeddings"
        chat_url = f"{base}/v1/chat/completions"

        self.intent_resolver = IntentResolver()
        self.agent_dispatcher = AgentDispatcher()
        self.rag_engine = RagEngine(embed_url=embed_url, chat_url=chat_url)

    async def run(
        self,
        rag: RAGRequest,
        session: RagSession,
        session_files: list[str],
    ) -> dict:
        """
        Orchestrate a full turn through intent resolution + agents + RAG.

        Parameters
        ----------
        rag : RAGRequest
            Framework-agnostic request payload (model, messages, etc.).
        session : RagSession
            Conversation/session object, including session id and metadata.
        session_files : list[str]
            Names of per-session uploaded files.

        Returns
        -------
        dict
            JSON-serializable payload to return from /ai/chat/rag.
        """
        agent_session_id = session.id

        # ------------------------------------------------------------------
        # 1) Normalize model / temperature / max_tokens
        # ------------------------------------------------------------------
        model = (
            rag.model or getattr(settings, "DEFAULT_MODEL", "llama3.2-vision")
        ).strip()
        if model == "llama3.2-vision":
            # Example: you could do model name remapping here if needed
            model = "llama3.2-vision"

        temperature = (
            rag.temperature
            if rag.temperature is not None
            else getattr(settings, "TUTOR_TEMPERATURE", 0.1)
        )

        requested_max = (
            rag.max_tokens
            if rag.max_tokens is not None
            else getattr(settings, "TUTOR_MAX_TOKENS", 8192)
        )
        try:
            requested_max_int = int(requested_max)
        except (TypeError, ValueError):
            requested_max_int = 2048

        # Hard clamp to avoid runaway token requests
        max_tokens = max(1, min(requested_max_int, 8192))

        # Mutate RAGRequest with resolved parameters
        rag.model = model
        rag.temperature = temperature
        rag.max_tokens = max_tokens

        # ------------------------------------------------------------------
        # 2) Extract the last user message content
        # ------------------------------------------------------------------
        user_messages = [m for m in rag.messages if m.role == "user"]
        if not user_messages:
            raise ValueError("No user message found")
        query = user_messages[-1].content

        # ------------------------------------------------------------------
        # 3) Resolve intent (classifier + heuristics + session stickiness)
        # ------------------------------------------------------------------
        resolution = await self.intent_resolver.resolve(
            rag=rag,
            session=session,
            query=query,
        )

        intent_label = resolution.intent
        action = resolution.action
        action_confidence = resolution.action_confidence

        # ------------------------------------------------------------------
        # 4) Persist session metadata (sticky intent, last query, etc.)
        # ------------------------------------------------------------------
        touch_session(
            agent_session_id,
            intent=intent_label,
            query=query,
        )

        # ------------------------------------------------------------------
        # 5) Attempt specialized agent path
        # ------------------------------------------------------------------
        agent_response = await self.agent_dispatcher.dispatch(
            intent_label=intent_label,
            query=query,
            rag=rag,
            session=session,
            session_files=session_files,
            action=action,
            action_confidence=action_confidence,
        )

        if agent_response is not None:
            return agent_response

        # ------------------------------------------------------------------
        # 6) No agent for this intent → generic RAG fallback
        # ------------------------------------------------------------------
        return await self.rag_engine.answer(
            rag=rag,
            session=session,
            query=query,
            intent_label=intent_label,
            session_files=session_files,
            action=action,
            action_confidence=action_confidence,
        )


# ======================================================================
# RAGRequest
# ======================================================================
class RAGRequest(BaseModel):
    """
    Framework-agnostic representation of a **RAG + agent** request.

    This decouples the router logic from FastAPI, so:
      - You can unit-test it directly.
      - You can invoke RouterAgent from CLI or other tasks.

    Fields mirror what the client sends to /ai/chat/rag.
    """

    model: Optional[str] = "llama3.2-vision"
    messages: List[ChatMessage] = Field(
        default_factory=lambda: [
            ChatMessage(
                role="system",
                content="You are a helpful assistant.",
            )
        ],
        description="Conversation messages for the model",
    )
    max_tokens: Optional[int] = 8192
    temperature: Optional[float] = 0.1
    debug: Optional[bool] = False
    index: Optional[str] = "main"

    # Agent-specific / orchestration metadata
    agent_session_id: Optional[str] = None
    intent: Optional[str] = None
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    subagent_session_id: Optional[str] = None


# ======================================================================
# Helper functions
# ======================================================================
def _normalize_dcg_expansion(text: str) -> str:
    """
    Force 'DCG' to always refer to 'Dallas Center-Grimes Community School District'
    in the final answer, even if the model hallucinates other expansions.

    This function:
      - Replaces known *incorrect* expansions (e.g., Des Moines Christian).
      - Leaves correct expansions unchanged.

    This is a temporary guardrail while models are not fully reliable.
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

    # Idempotent re-write of the correct expansion (no-op but explicit)
    text = text.replace(
        "DCG (Dallas Center-Grimes Community School District)",
        "DCG (Dallas Center-Grimes Community School District)",
    )

    return text


def _agent_result_to_trace_leaf(result: Any) -> dict:
    """
    Convert an AgentResult-like object into a serializable **trace node**.

    This is used to build a nested `agent_trace` structure for debugging:

        {
          "agent": "<agent_name>",
          "status": "<status>",
          "intent": "<intent>",
          "children": [ ... nested trace nodes ... ]
        }

    We rely only on getattr so that any AgentResult implementation
    that follows the usual conventions will work.
    """
    if result is None:
        return {}

    agent_name = getattr(result, "agent_name", None)
    agent_id = getattr(result, "agent_id", None)
    intent = getattr(result, "intent", None)

    agent_label = agent_name or agent_id or intent or "unknown_agent"

    children_raw = getattr(result, "children", None) or []
    children: list[dict] = []
    for child in children_raw:
        try:
            children.append(_agent_result_to_trace_leaf(child))
        except Exception:
            logger.exception("Failed to convert child AgentResult to trace node")

    return {
        "agent": agent_label,
        "status": getattr(result, "status", None),
        "intent": intent,
        "children": children,
    }


def _build_agent_trace(root_child: Any | None, intent_label: str | None) -> dict | None:
    """
    Build a hierarchical trace rooted at a logical "rag_router" node.

    Final shape:
        {
          "agent": "rag_router",
          "status": "ok" | "error" | None,
          "intent": "<effective_intent>",
          "children": [
            {
              "agent": "<child_agent>",
              "status": ...,
              "intent": ...,
              "children": [...]
            }
          ]
        }

    Parameters
    ----------
    root_child : Any | None
        Either:
          - An AgentResult-like object, or
          - A dict with 'agent', 'status', 'intent', 'children', or
          - None (in which case we return None).
    intent_label : str | None
        Effective intent for this turn (used as the root's intent).

    Returns
    -------
    dict | None
        The agent trace hierarchy, or None if there is no child.
    """
    if root_child is None:
        return None

    if isinstance(root_child, dict) and "agent" in root_child:
        leaf = root_child
    else:
        leaf = _agent_result_to_trace_leaf(root_child)

    status = leaf.get("status")
    effective_intent = intent_label or leaf.get("intent")

    return {
        "agent": "rag_router",
        "status": status,
        "intent": effective_intent,
        "children": [leaf],
    }
