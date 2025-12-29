from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal, Union, Dict, Any

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
    "write",
    "update",
    "delete",
    # Optional: if you want to align with data_query-style events later:
    # "query",
]


class AgentOutputEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: str = Field(..., description="What the agent is trying to achieve")
    tone: Tone = Field(..., description="Overall tone")
    sub_tone: Optional[str] = Field(None, description="More specific nuance of tone")
    action: Action = Field(..., description="The kind of work performed")

    # 🔧 Allow either plain text OR structured payloads
    content: Union[str, Dict[str, Any]] = Field(
        ...,
        description=(
            "The actual agent output: either plain text or a small structured "
            "payload (e.g. {'intent': 'data_query', 'topic': 'consents'})."
        ),
    )
