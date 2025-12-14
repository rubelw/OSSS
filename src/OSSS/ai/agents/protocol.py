# OSSS/ai/agents/protocol.py
from __future__ import annotations
from typing import Protocol, Optional, Any, Dict

class AgentProtocol(Protocol):
    name: str
    async def run(self, message: str, session_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        ...
