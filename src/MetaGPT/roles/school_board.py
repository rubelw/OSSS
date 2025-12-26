# src/MetaGPT/roles/school_board.py
from __future__ import annotations

import os
from typing import List, Dict, Any

from metagpt.roles import Role
from metagpt.logs import logger

from .rag.jsonl_retriever import JsonlRagRetriever
from .llm.ollama_client import OllamaChatClient


class SchoolBoardRole(Role):
    """
    MetaGPT role for a Dallas Center-Grimes (DCG) school board voice.

    This role can help with:
      - Board resolutions and motions
      - Meeting summaries and previews
      - Public-facing explanations of board decisions
      - Policy communication to the community
    """

    name: str = "school_board"

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

        # Local Ollama config (override via env if you want)
        base_url = os.getenv("OLLAMA_BASE_URL", "http://host.containers.internal:11434")
        # In your env you’ll probably set OLLAMA_MODEL=llama3.1:latest
        model = os.getenv("OLLAMA_MODEL", "llama3.2")

        logger.info(
            "SchoolBoardRole initializing with Ollama base_url=%s model=%s",
            base_url,
            model,
        )

        self.llm = OllamaChatClient(
            base_url=base_url,
            model=model,
        )

        # Path to your RAG JSONL index (same pattern as your other roles)
        index_path = os.getenv(
            "RAG_INDEX_PATH",
            "/vector_indexes/main/embeddings.jsonl",
        )
        self.retriever = JsonlRagRetriever(index_path=index_path)

    async def run(self, *args: Any, **kwargs: Any) -> str:
        """
        Entry point used by metagpt_server /run.

        We take the incoming 'query', retrieve local context (board packets,
        minutes, etc.), and call Ollama with a grounded school board persona.
        """
        logger.info("SchoolBoardRole.run starting...")

        # Get query from kwargs or first positional arg
        query = kwargs.get("query") or (args[0] if args else "")
        if not query:
            # Fallback if nothing was passed
            query = (
                "You are speaking as a member of the Dallas Center-Grimes (DCG) "
                "Community School District Board of Education.\n\n"
                "Write a short, clear explanation of a recent board decision that "
                "families might care about."
            )

        # 1) RAG retrieve from your local JSONL index
        chunks = await self.retriever.retrieve(query, k=8)
        logger.info("SchoolBoardRole.run retrieved %d chunks from RAG", len(chunks))

        context = "\n\n".join(
            f"[score={c.score:.3f} file={c.filename}]\n{c.text}"
            for c in chunks
        )

        # 2) Build grounded prompt for Ollama
        system_content = (
            "You are speaking as the Dallas Center-Grimes (DCG) Community School "
            "District Board of Education.\n"
            "Use ONLY the information in the CONTEXT below when referring to specific "
            "dates, policies, motions, votes, or dollar amounts.\n"
            "Your tone should be calm, transparent, and focused on students and the "
            "community. Explain board actions in plain language.\n\n"
            f"CONTEXT:\n{context}"
        )

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": query},
        ]

        # 3) Call local Ollama
        answer = await self.llm.chat(messages)
        logger.info("SchoolBoardRole.run finished; answer length=%d", len(answer or ""))

        return answer
