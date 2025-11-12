from __future__ import annotations
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field

class TutorConfig(BaseModel):
    tutor_id: str
    display_name: str
    system_prompt: str
    llm_model: str = "llama3.1:latest"
    embed_model: str = "all-minilm"
    rag_enabled: bool = True
    rag_index_dir: str = "data/chroma/{tutor_id}"
    max_tokens: int = 512
    temperature: float = 0.2
    tags: List[str] = []

class ChatTurn(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str = Field("How to add 1 + 1", example="How to add 1 + 1")
    history: Optional[List[ChatTurn]] = Field(
        default_factory=lambda: [{"role": "user", "content": "We are doing addition."}],
        example=[{"role": "user", "content": "We are doing addition."}]
    )
    use_rag: Optional[bool] = Field(False, example=False)
    max_tokens: Optional[int] = Field(128, example=128)

    class Config:
        json_schema_extra = {
            "example": {
                "message": "How to add 1 + 1",
                "history": [{"role": "user", "content": "We are doing addition."}],
                "use_rag": False,
                "max_tokens": 128,
            }
        }

class ChatResponse(BaseModel):
    tutor_id: str
    answer: str
    sources: List[Dict[str, Any]] = []
