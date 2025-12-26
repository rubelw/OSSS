from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal

Tone = Literal[
    "neutral", "informative", "analytical", "critical", "supportive", "persuasive", "cautious"
]

Action = Literal[
    "read", "write", "update", "delete"
]

class AgentOutputEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: str = Field(..., description="What the agent is trying to achieve")
    tone: Tone = Field(..., description="Overall tone")
    sub_tone: Optional[str] = Field(None, description="More specific nuance of tone")
    action: Action = Field(..., description="The kind of work performed")
    content: str = Field(..., description="The actual agent output text")
