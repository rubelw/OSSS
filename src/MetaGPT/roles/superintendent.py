# src/MetaGPT/roles/superintendent.py
from __future__ import annotations

import os
from typing import List, Dict, Any

from metagpt.roles import Role
from metagpt.logs import logger

from .rag.jsonl_retriever import JsonlRagRetriever
from .llm.ollama_client import OllamaChatClient


class SuperintendentRole(Role):
    """
    MetaGPT role for the district superintendent voice.

    This role can help with:
      - District-wide communications to families and staff
      - Strategic updates (budget, facilities, enrollment, long-range planning)
      - Explanations of major initiatives and board-approved plans
    """

    name: str = "superintendent"

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

        # Local Ollama config (override via env)
        base_url = os.getenv("OLLAMA_BASE_URL", "http://host.containers.internal:11434")
        # In your env you'll typically set OLLAMA_MODEL=llama3.2-vision:latest
        model = os.getenv("OLLAMA_MODEL", "llama3.2")

        logger.info(
            "SuperintendentRole initializing with Ollama base_url=%s model=%s",
            base_url,
            model,
        )

        self.llm = OllamaChatClient(
            base_url=base_url,
            model=model,
        )

        # Path to your RAG JSONL index (same pattern as other roles)
        index_path = os.getenv(
            "RAG_INDEX_PATH",
            "/vector_indexes/main/embeddings.jsonl",
        )
        self.retriever = JsonlRagRetriever(index_path=index_path)

    async def run(self, *args: Any, **kwargs: Any) -> str:
        """
        Entry point used by metagpt_server /run.

        We take the incoming 'query', retrieve local context, and call Ollama
        with a grounded superintendent persona prompt.
        """
        logger.info("SuperintendentRole.run starting...")

        # Get query from kwargs or first positional arg
        query = kwargs.get("query") or (args[0] if args else "")
        if not query:
            # Fallback prompt if nothing was passed
            query = (
                "You are the Superintendent of the Dallas Center-Grimes (DCG) "
                "Community School District.\n\n"
                "Draft a clear, district-wide message to families that explains a "
                "major initiative or change, and how it supports students."
            )

        # 1) RAG retrieve from your local JSONL index
        chunks = await self.retriever.retrieve(query, k=8)
        logger.info("SuperintendentRole.run retrieved %d chunks from RAG", len(chunks))

        context = "\n\n".join(
            f"[score={c.score:.3f} file={c.filename}]\n{c.text}"
            for c in chunks
        )

        # 2) Build grounded prompt for Ollama
        system_content = (
            "You are the Superintendent of the Dallas Center-Grimes (DCG) "
            "Community School District.\n"
            "Use ONLY the information in the CONTEXT below when referring to "
            "specific dates, schools, dollar amounts, policies, or board actions.\n"
            "Your tone should be steady, student-centered, transparent, and focused "
            "on long-term vision and partnership with families and staff.\n\n"
            f"CONTEXT:\n{context}"
        )

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": query},
        ]

        # 3) Call local Ollama
        answer = await self.llm.chat(messages)
        logger.info("SuperintendentRole.run finished; answer length=%d", len(answer or ""))

        return answer
