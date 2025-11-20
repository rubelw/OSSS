
from typing import List, Dict, Any

from metagpt.roles import Role
from .rag.jsonl_retriever import JsonlRagRetriever
from .llm.ollama_client import OllamaChatClient

from metagpt.logs import logger

class PrincipalRole(Role):
    """
    A MetaGPT role that behaves like a school principal.

    This role can handle:
      - Parent / staff communication
      - Announcements
      - Discipline situations
      - Scheduling / operations
    """

    # Pydantic-compatible override
    name: str = "principal"

    async def _act(self) -> None:
        logger.info("PrincipalRole is acting...")
        # You can inspect self.rc.history, environment, etc.
        # For now, keep it simple or just rely on default MetaGPT behavior.
        return
