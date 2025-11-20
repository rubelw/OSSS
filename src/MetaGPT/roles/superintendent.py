
from typing import List, Dict, Any

from metagpt.roles import Role
from .rag.jsonl_retriever import JsonlRagRetriever
from .llm.ollama_client import OllamaChatClient

from metagpt.logs import logger

class SuperintendentRole(Role):
    name: str = "superintendent"

    async def _act(self) -> None:
        logger.info("SuperintendentRole is acting...")
        return
