# OSSS/ai/api/schemas/query_response.py

from __future__ import annotations

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class SourceItem(BaseModel):
    """
    A single citation / source for the answer.
    This is what your UI can show as 'Sources'.
    """

    type: str = Field(
        "document",
        description="Type of source, e.g. 'document', 'url', 'note', etc.",
    )
    display_name: str = Field(
        ...,
        description="User-friendly display name (e.g., 'Policy 404 Employee Conduct and Appearance').",
    )
    filename: Optional[str] = Field(
        None,
        description="Underlying filename if applicable.",
    )
    source_key: Optional[str] = Field(
        None,
        description="Internal path or identifier for the source (e.g., S3 key, vector index source).",
    )
    score: Optional[float] = Field(
        None,
        description="Relevance score from RAG or search, if available.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extra metadata, safe to show to users (page numbers, section titles, etc.).",
    )


class AnswerPayload(BaseModel):
    """
    Canonical user-facing answer.
    """

    text_markdown: str = Field(
        ...,
        description="Final answer text in markdown.",
    )
    used_rag: bool = Field(
        False,
        description="Whether retrieval-augmented generation was used.",
    )
    sources: List[SourceItem] = Field(
        default_factory=list,
        description="List of key sources used to produce the answer.",
    )


class ClassifierSummary(BaseModel):
    """
    Small, stable classifier view for clients.
    (Full classifier payload can go into debug if needed.)
    """

    intent: Optional[str] = Field(
        None,
        description="High-level intent label (e.g., 'informational', 'action', 'update').",
    )
    topic: Optional[str] = Field(
        None,
        description="Primary topic label (e.g., 'policies').",
    )
    domain: Optional[str] = Field(
        None,
        description="Domain label (e.g., 'student_services', 'data_systems').",
    )
    confidence: Optional[float] = Field(
        None,
        description="Overall confidence score for the intent/topic/domain classification.",
    )


class RefinerSummary(BaseModel):
    """
    Refiner output in a compact, query-centric form.
    """

    original_query: str = Field(
        ...,
        description="Original user question text.",
    )
    refined_query: str = Field(
        ...,
        description="Refined, clarified query text.",
    )
    processing_mode: str = Field(
        ...,
        description="How the refiner ran: 'lightweight', 'structured', or 'traditional'.",
    )
    cheap_confidence: Optional[float] = Field(
        None,
        description="Confidence score from cheap/lightweight refiner path (0.0–1.0).",
    )
    entities: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured entities extracted from the query.",
    )
    date_filters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured date filters extracted from the query.",
    )
    flags: Dict[str, Any] = Field(
        default_factory=dict,
        description="Misc boolean flags or indicators derived from the query.",
    )


class QueryMeta(BaseModel):
    """
    Stable, small metadata set useful to clients.
    Anything more detailed should go into debug.
    """

    workflow_id: str
    conversation_id: Optional[str] = None
    execution_id: Optional[str] = None
    correlation_id: Optional[str] = None
    agents: List[str] = Field(default_factory=list)
    successful_agents: List[str] = Field(default_factory=list)
    failed_agents: List[str] = Field(default_factory=list)
    used_rag: bool = False
    top_k: Optional[int] = None
    graph_pattern: Optional[str] = None
    orchestrator_type: Optional[str] = None


class QueryResponse(BaseModel):
    """
    OSSS /api/query stable public response schema.
    """

    schema_version: str = Field(
        "v1",
        description="Version of the public response schema.",
    )
    workflow_id: str
    conversation_id: Optional[str] = None
    question: str
    answer: AnswerPayload
    classifier: Optional[ClassifierSummary] = None
    refiner: Optional[RefinerSummary] = None
    meta: QueryMeta
    debug: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional debug payload; NOT guaranteed stable. For dev / advanced clients.",
    )
