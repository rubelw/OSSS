# src/MetaGPT/roles/teacher.py
from metagpt.roles import Role
from .rag.jsonl_retriever import JsonlRagRetriever
from .llm.ollama_client import OllamaChatClient

from metagpt.logs import logger

class TeacherRole(Role):
    name: str = "teacher"

    async def _act(self) -> None:
        logger.info("TeacherRole is acting...")
        return
