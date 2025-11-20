# src/MetaGPT/roles/accountability_partner.py
from __future__ import annotations

import os
from typing import List, Dict, Any

from metagpt.roles import Role
from metagpt.logs import logger

from .rag.jsonl_retriever import JsonlRagRetriever
from .llm.ollama_client import OllamaChatClient


class AccountabilityPartnerRole(Role):
    """
    Accountability Partner role.

    This role helps students or adults stay on track with:
      - Goals
      - Daily habits
      - Planning and follow-through
      - Motivation with a supportive tone
      - Breaking tasks into steps
    """

    name: str = "accountability_partner"

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

        # Load Ollama config
        base_url = os.getenv("OLLAMA_BASE_URL", "http://host.containers.internal:11434")
        model = os.getenv("OLLAMA_MODEL", "llama3.2")

        logger.info(
            "AccountabilityPartnerRole initializing with Ollama base_url=%s model=%s",
            base_url,
            model,
        )

        self.llm = OllamaChatClient(
            base_url=base_url,
            model=model,
        )

        # RAG index location
        index_path = os.getenv(
            "RAG_INDEX_PATH",
            "/vector_indexes/main/embeddings.jsonl",
        )
        self.retriever = JsonlRagRetriever(index_path=index_path)

    async def run(self, *args: Any, **kwargs: Any) -> str:
        """
        Entry point used by metagpt_server /run.
        Build a grounded accountability partner response.
        """
        logger.info("AccountabilityPartnerRole.run starting...")

        query = kwargs.get("query") or (args[0] if args else "")
        if not query:
            # Fallback message
            query = (
                "Help me plan, stay motivated, and follow through on daily habits and goals."
            )

        # 1) Retrieve relevant RAG context
        chunks = await self.retriever.retrieve(query, k=8)
        logger.info(
            "AccountabilityPartnerRole.run retrieved %d chunks from RAG", len(chunks)
        )

        context = "\n\n".join(
            f"[score={c.score:.3f} file={c.filename}]\n{c.text}"
            for c in chunks
        )

        # 2) Build system prompt
        system_content = (
            "You are a supportive, structured accountability partner.\n"
            "Your tone is encouraging, practical, and judgment-free.\n"
            "Help the user break tasks into clear steps, build routines, "
            "and identify realistic next actions.\n\n"
            "Use ONLY the CONTEXT below when referring to specific dates, tasks, "
            "documents, or commitments.\n\n"
            f"CONTEXT:\n{context}"
        )

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": query},
        ]

        # 3) Call local Ollama
        answer = await self.llm.chat(messages)

        logger.info(
            "AccountabilityPartnerRole.run finished; answer length=%d",
            len(answer or ""),
        )

        return answer

