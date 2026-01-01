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


def _build_sources_from_rag_hits(rag_hits: Optional[List[Dict[str, Any]]]) -> List[SourceItem]:
    if not rag_hits:
        return []

    sources: List[SourceItem] = []
    for hit in rag_hits:
        filename = hit.get("filename")
        src = hit.get("source")
        # Prefer a clean display_name, fall back to filename or source
        display_name = filename or src or "Document"

        sources.append(
            SourceItem(
                type="document",
                display_name=display_name,
                filename=filename,
                source_key=src,
                score=hit.get("score"),
                metadata={
                    "chunk_index": hit.get("chunk_index"),
                    "id": hit.get("id"),
                    # You can add page numbers here if you propagate them into rag_hits
                },
            )
        )
    return sources


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

    # Optionally normalize domain/topic for humans – you can map "data_systems" if you want
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
    Transform a raw LangGraph orchestration payload (like the one you pasted)
    into the stable QueryResponse schema for /api/query.

    This is the single choke point where you:
    - pick the canonical 'answer'
    - extract a small classifier summary
    - pull refiner info into a sane shape
    - optionally pack everything else into `debug`
    """

    # 1) Canonical IDs / question
    workflow_id = payload.get("workflow_id") or payload.get("execution_id") or ""
    conversation_id = payload.get("conversation_id")
    correlation_id = payload.get("correlation_id")

    question = (
        payload.get("original_query")
        or payload.get("user_question")
        or _safe_get(payload, "config", {}).get("raw_query")
        or ""
    )

    # 2) Canonical answer: prefer structured final, then top-level "answer"
    execution_state = _safe_get(payload, "execution_state", {})
    structured_outputs = _safe_get(execution_state, "structured_outputs", {})
    final_structured = _safe_get(structured_outputs, "final", {})

    final_answer = final_structured.get("final_answer") or payload.get("answer") or ""

    answer = AnswerPayload(
        text_markdown=final_answer,
        used_rag=bool(final_structured.get("used_rag") or execution_state.get("rag_enabled")),
        sources=_build_sources_from_rag_hits(execution_state.get("rag_hits")),
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
            # Keep things that are useful when debugging but not needed by normal clients
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
