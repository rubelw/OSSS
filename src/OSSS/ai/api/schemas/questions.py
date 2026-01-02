from __future__ import annotations

import uuid
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


class QuestionCreate(BaseModel):
    query: str = Field(..., description="User question text")
    topic_id: Optional[uuid.UUID] = None
    similar_to: Optional[uuid.UUID] = None
    correlation_id: Optional[str] = None
    execution_id: Optional[str] = None
    nodes_executed: Optional[List[str]] = None
    execution_metadata: Optional[Dict[str, Any]] = None


class QuestionPatch(BaseModel):
    query: Optional[str] = None
    topic_id: Optional[uuid.UUID] = None
    similar_to: Optional[uuid.UUID] = None
    correlation_id: Optional[str] = None
    execution_id: Optional[str] = None
    nodes_executed: Optional[List[str]] = None
    execution_metadata: Optional[Dict[str, Any]] = None


class QuestionOut(BaseModel):
    id: uuid.UUID
    query: str
    topic_id: Optional[uuid.UUID] = None
    similar_to: Optional[uuid.UUID] = None
    correlation_id: Optional[str] = None
    execution_id: Optional[str] = None
    nodes_executed: Optional[List[str]] = None
    execution_metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None  # ISO string; adjust if you prefer datetime

    @classmethod
    def from_orm_obj(cls, obj) -> "QuestionOut":
        # avoid needing Pydantic v2 orm_mode wiring
        return cls(
            id=obj.id,
            query=obj.query,
            topic_id=getattr(obj, "topic_id", None),
            similar_to=getattr(obj, "similar_to", None),
            correlation_id=getattr(obj, "correlation_id", None),
            execution_id=getattr(obj, "execution_id", None),
            nodes_executed=getattr(obj, "nodes_executed", None),
            execution_metadata=getattr(obj, "execution_metadata", None),
            created_at=obj.created_at.isoformat() if getattr(obj, "created_at", None) else None,
        )
