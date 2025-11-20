
from typing import List, Dict, Any

from metagpt.roles import Role
from .rag.jsonl_retriever import JsonlRagRetriever
from .llm.ollama_client import OllamaChatClient

from metagpt.logs import logger

class SchoolBoardRole(Role):
    name: str = "school_board"

    async def _act(self) -> None:
        logger.info("SchoolBoardRole is acting...")
        return
