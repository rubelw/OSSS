from __future__ import annotations
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field

class TutorConfig(BaseModel):
    tutor_id: str
    display_name: str
    system_prompt: str
    llm_model: str = "llama3.2:3b"
    embed_model: str = "nomic-embed-text"
    rag_enabled: bool = True
    rag_index_dir: str = "data/chroma/{tutor_id}"
    max_tokens: int = 512
    temperature: float = 0.2
    tags: List[str] = []

class ChatTurn(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatTurn]] = None
    use_rag: Optional[bool] = None  # default: inherit from tutor config
    max_tokens: Optional[int] = None

class ChatResponse(BaseModel):
    tutor_id: str
    answer: str
    sources: List[Dict[str, Any]] = []
