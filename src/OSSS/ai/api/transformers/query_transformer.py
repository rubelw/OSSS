# OSSS/ai/api/transformers/query_transformer.py

from __future__ import annotations

from typing import Any, Dict, List, Optional

from OSSS.ai.api.schemas.query_response import (
    QueryResponse,
    AnswerPayload,
    SourceItem,
    ClassifierSummary,
    RefinerSummary,
    QueryMeta,
)


def _safe_get(d: Optional[Dict[str, Any]], key: str, default: Any = None) -> Any:
    if not isinstance(d, dict):
        return default
    return d.get(key, default)


def _build_sources_from_public_sources(public_sources: Optional[List[Dict[str, Any]]]) -> List[SourceItem]:
    """
    Accept sources already in public-ish shape (e.g. answer.sources coming from upstream),
    and coerce into SourceItem objects.
    """
    if not public_sources:
        return []

    sources: List[SourceItem] = []
    for s in public_sources:
        if not isinstance(s, dict):
            continue

        display_name = s.get("display_name") or s.get("filename") or s.get("source_key") or "Document"
        sources.append(
            SourceItem(
                type=s.get("type") or "document",
                display_name=display_name,
                filename=s.get("filename"),
                source_key=s.get("source_key"),
                score=s.get("score"),
                metadata=s.get("metadata") or {},
            )
        )
    return sources


def _build_sources_from_rag_hits(rag_hits: Optional[List[Dict[str, Any]]]) -> List[SourceItem]:
    """
    Accept internal rag_hits shape (index/search pipeline) and convert to SourceItem objects.
    """
    if not rag_hits:
        return []

    sources: List[SourceItem] = []
    for hit in rag_hits:
        if not isinstance(hit, dict):
            continue

        filename = hit.get("filename")
        src = hit.get("source") or hit.get("source_key")

        # Prefer a clean display_name, fall back to filename or source
        display_name = hit.get("display_name") or filename or src or "Document"

        sources.append(
            SourceItem(
                type=hit.get("type") or "document",
                display_name=display_name,
                filename=filename,
                source_key=src,
                score=hit.get("score"),
                metadata={
                    "chunk_index": hit.get("chunk_index") or _safe_get(hit.get("metadata"), "chunk_index"),
                    "id": hit.get("id") or _safe_get(hit.get("metadata"), "id"),
                    # Add page numbers here if you propagate them into rag_hits
                },
            )
        )
    return sources


def _pick_answer_text_markdown(payload: Dict[str, Any]) -> str:
    """
    Choose the public answer.text_markdown.

    Priority:
      1) pending_action prompt (awaiting == True)
      2) agent_outputs.final (string)
      3) agent_outputs.refiner (string)
      4) payload["answer"]["text_markdown"] (if answer is dict)
      5) payload["answer"] (if answer is string)
      6) payload["refiner"]["refined_query"] / ["original_query"] (if present)
      7) execution_state["raw_user_text"] / ["original_query"] / ["query"]
    """
    execution_state = _safe_get(payload, "execution_state", {})
    if not isinstance(execution_state, dict):
        execution_state = {}

    # 1) pending_action prompt wins (this is the "first turn still not prompting" fix)
    pending_action = execution_state.get("pending_action")
    if isinstance(pending_action, dict) and bool(pending_action.get("awaiting")):
        for k in (
            "prompt_text",
            "prompt",
            "pending_prompt",
            "pending_question",
            "question",
            "message",
            "text",
        ):
            v = pending_action.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()

        # Last resort generic yes/no prompt
        if str(pending_action.get("type") or "").strip().lower() == "confirm_yes_no":
            return "Please reply **yes** or **no** to continue."

    # 2/3) agent outputs
    agent_outputs = execution_state.get("agent_outputs")
    agent_outputs = agent_outputs if isinstance(agent_outputs, dict) else {}

    v = agent_outputs.get("final")
    if isinstance(v, str) and v.strip():
        return v.strip()

    v = agent_outputs.get("refiner")
    if isinstance(v, str) and v.strip():
        return v.strip()

    # 4/5) payload answer
    ans = payload.get("answer")
    if isinstance(ans, dict):
        v = ans.get("text_markdown")
        if isinstance(v, str) and v.strip():
            return v.strip()
    elif isinstance(ans, str) and ans.strip():
        return ans.strip()

    # 6) refiner dict (sometimes bubbled up top-level)
    ref = payload.get("refiner")
    if isinstance(ref, dict):
        for k in ("refined_query", "original_query"):
            v = ref.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()

    # 7) exec_state fallbacks
    for k in ("raw_user_text", "original_query", "query"):
        v = execution_state.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()

    return ""


def _pick_used_rag(payload: Dict[str, Any], execution_state: Dict[str, Any]) -> bool:
    """
    Decide answer.used_rag in a robust way.
    """
    # If payload.answer is a dict with used_rag, respect it
    ans = payload.get("answer")
    if isinstance(ans, dict):
        v = ans.get("used_rag")
        if isinstance(v, bool):
            return v

    # internal execution_state hints
    for k in ("used_rag", "rag_enabled"):
        v = execution_state.get(k)
        if isinstance(v, bool):
            return v

    rag_hits = execution_state.get("rag_hits")
    if isinstance(rag_hits, list) and len(rag_hits) > 0:
        return True

    rag_meta = execution_state.get("rag_meta")
    if isinstance(rag_meta, dict):
        v = rag_meta.get("used_rag")
        if isinstance(v, bool):
            return v
        hits = rag_meta.get("hits") or rag_meta.get("results")
        if isinstance(hits, list) and len(hits) > 0:
            return True

    return False


def _pick_sources(payload: Dict[str, Any], execution_state: Dict[str, Any]) -> List[SourceItem]:
    """
    Prefer already-normalized public sources (answer.sources) if present,
    otherwise fall back to internal execution_state rag_hits.
    """
    ans = payload.get("answer")
    if isinstance(ans, dict):
        public_sources = ans.get("sources")
        if isinstance(public_sources, list) and public_sources:
            return _build_sources_from_public_sources(public_sources)

    rag_hits = execution_state.get("rag_hits")
    if isinstance(rag_hits, list) and rag_hits:
        return _build_sources_from_rag_hits(rag_hits)

    rag_meta = execution_state.get("rag_meta")
    if isinstance(rag_meta, dict):
        hits = rag_meta.get("hits") or rag_meta.get("results")
        if isinstance(hits, list) and hits:
            return _build_sources_from_rag_hits(hits)

    return []


def _build_classifier_summary(payload: Dict[str, Any]) -> Optional[ClassifierSummary]:
    classifier = _safe_get(payload, "classifier")
    if not classifier:
        classifier = _safe_get(payload, "classifier_result")

    if not isinstance(classifier, dict):
        return None

    intent = classifier.get("intent")
    topic = classifier.get("topic")
    domain = classifier.get("domain")
    confidence = classifier.get("confidence")

    if not any([intent, topic, domain]):
        return None

    return ClassifierSummary(
        intent=intent,
        topic=topic,
        domain=domain,
        confidence=confidence,
    )


def _build_refiner_summary(execution_state: Dict[str, Any]) -> Optional[RefinerSummary]:
    refiner = _safe_get(execution_state, "refiner")
    if not isinstance(refiner, dict):
        return None

    original_query = refiner.get("original_query")
    refined_query = refiner.get("refined_query")

    if not isinstance(original_query, str) or not isinstance(refined_query, str):
        return None

    return RefinerSummary(
        original_query=original_query,
        refined_query=refined_query,
        processing_mode=refiner.get("processing_mode", "unknown"),
        cheap_confidence=refiner.get("cheap_confidence"),
        entities=refiner.get("entities") or {},
        date_filters=refiner.get("date_filters") or {},
        flags=refiner.get("flags") or {},
    )


def transform_orchestration_payload_to_query_response(
    payload: Dict[str, Any],
    include_debug: bool = False,
) -> QueryResponse:
    """
    Transform a raw LangGraph orchestration payload into the stable QueryResponse schema.

    This is the single choke point where you:
    - pick the canonical 'answer' (including wizard prompts via pending_action)
    - extract a small classifier summary
    - pull refiner info into a sane shape
    - optionally pack everything else into `debug`
    """

    # 1) Canonical IDs / question
    workflow_id = payload.get("workflow_id") or payload.get("execution_id") or ""
    conversation_id = payload.get("conversation_id")
    correlation_id = payload.get("correlation_id")

    # Prefer payload.question if present; otherwise fall back.
    question = (
        payload.get("question")
        or payload.get("original_query")
        or payload.get("user_question")
        or _safe_get(payload, "config", {}).get("raw_query")
        or ""
    )

    execution_state = _safe_get(payload, "execution_state", {})
    if not isinstance(execution_state, dict):
        execution_state = {}

    # 2) Canonical answer (✅ handles pending_action prompting)
    text_markdown = _pick_answer_text_markdown(payload)
    used_rag = _pick_used_rag(payload, execution_state)
    sources = _pick_sources(payload, execution_state)

    answer = AnswerPayload(
        text_markdown=text_markdown,
        used_rag=used_rag,
        sources=sources,
    )

    # 3) Classifier summary
    classifier_summary = _build_classifier_summary(payload)

    # 4) Refiner summary
    refiner_summary = _build_refiner_summary(execution_state)

    # 5) Meta (small, stable)
    agents_to_run = execution_state.get("agents_to_run") or execution_state.get("planned_agents") or []
    successful_agents = execution_state.get("successful_agents") or []
    failed_agents = execution_state.get("failed_agents") or []
    execution_id = execution_state.get("execution_id") or payload.get("execution_id")

    meta = QueryMeta(
        workflow_id=workflow_id,
        conversation_id=conversation_id,
        execution_id=execution_id,
        correlation_id=correlation_id,
        agents=list(agents_to_run),
        successful_agents=list(successful_agents),
        failed_agents=list(failed_agents),
        used_rag=answer.used_rag,
        top_k=_safe_get(execution_state, "execution_config", {}).get("top_k"),
        graph_pattern=execution_state.get("graph_pattern"),
        orchestrator_type=payload.get("orchestrator_type"),
    )

    # 6) Debug payload (optional, not schema-stable)
    debug_payload: Optional[Dict[str, Any]] = None
    if include_debug:
        debug_payload = {
            "raw_request_config": payload.get("raw_request_config"),
            "execution_state": execution_state,
            "rag_meta": execution_state.get("rag_meta"),
            "agent_output_index": execution_state.get("agent_output_index"),
            "agent_execution_status": payload.get("agent_execution_status"),
        }

    return QueryResponse(
        schema_version="v1",
        workflow_id=workflow_id,
        conversation_id=conversation_id,
        question=question,
        answer=answer,
        classifier=classifier_summary,
        refiner=refiner_summary,
        meta=meta,
        debug=debug_payload,
    )
