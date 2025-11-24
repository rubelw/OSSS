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
sys.path.append("/workspace/src/MetaGPT")

from MetaGPT.roles_registry import ROLE_REGISTRY  # noqa: F401
from MetaGPT.roles.registration import RegistrationRole  # noqa: F401

from OSSS.ai.intent_classifier import classify_intent
from OSSS.ai.intents import Intent
from OSSS.ai.agents import AgentContext, get_agent
from OSSS.ai.additional_index import top_k, INDEX_KINDS
from OSSS.ai.session_store import RagSession, touch_session

# 👇 Force-load student registration agents so @register_agent runs
import OSSS.ai.agents.student.registration  # noqa: F401

YEAR_PATTERN = re.compile(r"(20[2-9][0-9])[-/](?:20[2-9][0-9]|[0-9]{2})")

logger = logging.getLogger("OSSS.ai.router_agent")

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
        TUTOR_MAX_TOKENS: int = 8192
        DEFAULT_MODEL: str = "llama3.2-vision"

    settings = _Settings()  # type: ignore


# Intent aliases: map classifier labels to agent-owned canonical names
INTENT_ALIASES: dict[str, str] = {
    "enrollment": "register_new_student",
    "new_student_registration": "register_new_student",
    # add more synonyms as you create more agents
}

def _looks_like_school_year(text: str) -> bool:
    """
    Detect simple school-year style answers like:
      - '2024-25'
      - '2025-26'
      - '2025/26'
    Not a full validator, just enough to route the turn back to registration.
    """
    if not text:
        return False

    q = text.strip()
    # normalize fancy dashes to '-'
    q = q.replace("–", "-").replace("—", "-")
    return bool(YEAR_PATTERN.search(q))

class RAGRequest(BaseModel):
    """
    Framework-agnostic representation of a RAG + agent-call request.

    This is the same payload your FastAPI endpoint is receiving, but now
    you can reuse it anywhere (tests, CLI, etc.).
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
    agent_session_id: Optional[str] = None
    intent: Optional[str] = None
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    subagent_session_id: Optional[str] = None


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

    text = text.replace(
        "DCG (Dallas Center-Grimes Community School District)",
        "DCG (Dallas Center-Grimes Community School District)",
    )

    return text


def _agent_result_to_trace_leaf(result: Any) -> dict:
    """
    Convert an AgentResult-like object into a serializable trace node.

    Only uses getattr so it works with any AgentResult implementation
    that follows your conventions (answer_text, status, intent, children, etc.).
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
    Build a hierarchical trace rooted at the logical orchestrator "rag_router",
    with the provided AgentResult-like object (or synthetic node) as its child.

    Shape:
    {
      "agent": "rag_router",
      "status": "ok" | "error" | None,
      "intent": "<effective_intent>",
      "children": [ { ... leaf/chain ... } ]
    }
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


class RouterAgent:
    """
    Top-level orchestrator for RAG + intent-based agents.

    This is framework-agnostic: you can call it from FastAPI, a CLI,
    tests, or any other environment.

    Inputs:
      - RAGRequest
      - RagSession (for sticky intent + audit)
      - session_files: list of filenames associated with this session

    Output: dict payload matching your existing /ai/chat/rag shape,
            plus an `agent_trace` describing the agent call chain.
    """

    def __init__(self) -> None:
        base = getattr(
            settings, "VLLM_ENDPOINT", "http://host.containers.internal:11434"
        ).rstrip("/")
        self.embed_url = f"{base}/api/embeddings"
        self.chat_url = f"{base}/v1/chat/completions"

    async def run(
        self,
        rag: RAGRequest,
        session: RagSession,
        session_files: list[str],
    ) -> dict:
        agent_session_id = session.id
        agent_id: Optional[str] = rag.agent_id
        agent_name: Optional[str] = rag.agent_name

        # ---- model / params ----
        model = (
            rag.model or getattr(settings, "DEFAULT_MODEL", "llama3.2-vision")
        ).strip()
        debug = bool(getattr(rag, "debug", False))

        if model == "llama3.2-vision":
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
        max_tokens = max(1, min(requested_max_int, 8192))

        # ---- 1) last user message ----
        user_messages = [m for m in rag.messages if m.role == "user"]
        if not user_messages:
            raise ValueError("No user message found")
        query = user_messages[-1].content

        ql = (query or "").lower()

        # Explicit override from client (if you ever send it)
        manual_label = rag.intent

        # Simple lexical heuristic: "register" + "new student"
        forced_intent: str | None = None
        if "register" in ql and "new student" in ql:
            forced_intent = "register_new_student"
            logger.info(
                "RouterAgent: forcing intent to %s based on query text=%r",
                forced_intent,
                query[:200],
            )
        elif _looks_like_school_year(query):
            forced_intent = "register_new_student"
            logger.info(
                "RouterAgent: treating bare school-year answer as registration; query=%r",
                query[:200],
            )

        # ---- Look at any prior session intent ---------------------------
        session_intent = getattr(session, "intent", None)

        # ---- Intent Classification (this turn) --------------------------
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
            logger.error("Error classifying intent: %s", e)

        # Normalize classified intent
        if isinstance(classified, Intent):
            classified_label: str | None = classified.value
        elif isinstance(classified, str):
            classified_label = classified
        else:
            classified_label = None

        # ---- Make intent "sticky" + apply aliases -----------------------
        # Priority:
        #   1. If we're clearly inside a registration flow, always route to
        #      the registration agent (so short replies like "2025-26"
        #      don't bounce to generic RAG).
        #   2. Otherwise, respect any explicit/manual/forced intent, then
        #      the classifier, and finally fall back to a "general" intent.
        within_registration_flow = False

        # Already in a registration flow for this logical session.
        if session_intent == "register_new_student":
            within_registration_flow = True

        # Frontend is sending back a subagent_session_id, which means we're
        # mid-conversation with some agent. If the classifier didn't give us
        # a *different* strong intent, keep routing to registration.
        elif rag.subagent_session_id and (
                classified_label in (None, "general", "enrollment", "register_new_student")
                or session_intent in (None, "register_new_student")
        ):
            within_registration_flow = True

        # Very short messages that look like "2025-26" etc., which are almost
        # always the "school year" answer while registering a student.
        elif _looks_like_school_year(query):
            within_registration_flow = True

        if within_registration_flow:
            intent_label = "register_new_student"
            base_label = "register_new_student"
        else:
            base_label = (
                    manual_label
                    or forced_intent
                    or classified_label
                    or session_intent
                    or "general"
            )
            intent_label = INTENT_ALIASES.get(base_label, base_label)

        logger.info(
            "Effective intent for this turn: %r (manual=%r, forced=%r, session_intent=%r, classified=%r, aliased_from=%r)",
            intent_label,
            manual_label,
            forced_intent,
            session_intent,
            classified_label,
            base_label,
        )

        # Update persistent session metadata (including last_access timestamp)
        touch_session(
            agent_session_id,
            intent=intent_label,
            query=query,
        )

        # -----------------------------------------------------------------
        #  Agent dispatch: if an agent is registered for this intent,
        #  delegate handling to it and return its response.
        # -----------------------------------------------------------------
        agent = get_agent(intent_label)

        # Hard fallback for registration if registry wiring is off
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

        if agent is not None:
            logger.info("Dispatching to agent for intent=%s", intent_label)

            ctx = AgentContext(
                query=query,
                session_id=agent_session_id,  # current / logical session
                agent_id=agent_id,
                agent_name=agent_name,
                intent=intent_label,
                action=action,
                action_confidence=action_confidence,
                main_session_id=agent_session_id,  # top-level RAG session
                subagent_session_id=rag.subagent_session_id,  # registration sub-session
                metadata={"session_files": session_files},
                retrieved_chunks=[],
            )

            try:
                agent_result = await agent.run(ctx)
            except Exception as e:
                logger.exception(
                    "Agent '%s' failed; falling back to error payload", intent_label
                )
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

            agent_trace = _build_agent_trace(agent_result, intent_label=intent_label)

            user_response = {
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
                "subagent_session_id": getattr(
                    agent_result, "agent_session_id", None
                ),
                "session_files": session_files,
                "agent_id": getattr(agent_result, "agent_id", agent_id),
                "agent_name": getattr(agent_result, "agent_name", agent_name),
                "action": action,
                "action_confidence": action_confidence,
                "agent_trace": agent_trace,
            }

            # 🔍 NEW: surface agent_debug_information out of the AgentResult.data
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

        # -----------------------------------------------------------------
        #  No agent: fall back to generic RAG flow
        # -----------------------------------------------------------------
        async with httpx.AsyncClient(timeout=10.0) as client:
            embed_req = {"model": "nomic-embed-text", "prompt": query}
            er = await client.post(self.embed_url, json=embed_req)
            if er.status_code >= 400:
                raise RuntimeError(
                    f"Embedding endpoint error {er.status_code}: {er.text}"
                )

            ej = er.json()
            if isinstance(ej, dict) and "data" in ej:
                vec = ej["data"][0]["embedding"]
            elif isinstance(ej, dict) and "embedding" in ej:
                vec = ej["embedding"]
            elif isinstance(ej, dict) and "embeddings" in ej:
                vec = ej["embeddings"][0]
            else:
                raise RuntimeError(
                    f"Unexpected embedding response schema: {ej!r}"
                )

            query_emb = np.array(vec, dtype="float32")

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
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(self.chat_url, json=chat_req)
            if r.status_code >= 400:
                raise RuntimeError(
                    f"Chat completion endpoint error {r.status_code}: {r.text}"
                )

            data = r.json()

            # auto-continue for long lists
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

            # basic debug logging
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

            for choice in data.get("choices", []):
                msg = choice.get("message") or {}
                if isinstance(msg.get("content"), str):
                    content = msg["content"]
                    content = _normalize_dcg_expansion(content)
                    content = redact_pii(content)
                    msg["content"] = content

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
