# src/MetaGPT/roles/accountability_partner.py

from typing import List, Dict, Any

from metagpt.roles import Role
from .rag.jsonl_retriever import JsonlRagRetriever
from .llm.ollama_client import OllamaChatClient

from metagpt.logs import logger

class AccountabilityPartnerRole(Role):
    name: str = "accountability_partner"

    async def _act(self) -> None:
        logger.info("AccountabilityPartnerRole is acting...")
        return
