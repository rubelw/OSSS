from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, Literal

Tone = Literal[
    "neutral",
    "informative",
    "analytical",
    "critical",
    "supportive",
    "persuasive",
    "cautious",
]

Action = Literal[
    "read",
    "create",
    "add",
    "update",
    "edit",
    "delete",
    "troubleshoot",
    "review",
    "explain",
    "route",
]

# ✅ Action normalization
ACTION_NORMALIZATION = {
    "add": "create",
    "edit": "update",
}

def normalize_action(action: str) -> str:
    return ACTION_NORMALIZATION.get(action, action)


class AgentOutputEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: str = Field(..., description="What the agent is trying to achieve")
    tone: Tone = Field(..., description="Overall tone")
    sub_tone: Optional[str] = Field(None, description="More specific nuance of tone")
    action: Action = Field(..., description="The kind of work performed")
    content: str = Field(..., description="The actual agent output text")

    # ✅ Normalize BEFORE validation finishes
    @field_validator("action", mode="before")
    @classmethod
    def _normalize_action(cls, v: str) -> str:
        return normalize_action(v)

