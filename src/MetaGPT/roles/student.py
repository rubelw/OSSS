from __future__ import annotations

import os
from typing import List, Dict, Any

from metagpt.roles import Role
from metagpt.logs import logger

from .rag.jsonl_retriever import JsonlRagRetriever
from .llm.ollama_client import OllamaChatClient


class StudentRole(Role):
    name: str = "student"

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

        # Local Ollama config (override via env if needed)
        base_url = os.getenv("OLLAMA_BASE_URL", "http://host.containers.internal:11434")
        model = os.getenv("OLLAMA_MODEL", "llama3.2")

        logger.info(
            "StudentRole initializing with Ollama base_url=%s model=%s",
            base_url,
            model,
        )

        self.llm = OllamaChatClient(
            base_url=base_url,
            model=model,
        )

        # Path to your RAG JSONL index (same as ParentRole)
        index_path = os.getenv(
            "RAG_INDEX_PATH",
            "/vector_indexes/main/embeddings.jsonl",
        )
        self.retriever = JsonlRagRetriever(index_path=index_path)

    async def run(self, *args: Any, **kwargs: Any) -> str:
        """
        Entry point used by metagpt_server /run for the student.
        We take the incoming 'query' (usually the parent's question),
        retrieve local context, and answer as the student.
        """
        logger.info("StudentRole.run starting...")

        # Get query from kwargs or first positional arg
        query = kwargs.get("query") or (args[0] if args else "")
        if not query:
            # Fallback if nothing passed
            query = (
                "You are the student responding honestly and respectfully to your parent.\n\n"
                "Your parent asks you this question about your grades.\n"
                "Respond in a few sentences, being honest about how you feel and what you plan to do."
            )

        # 1) RAG retrieve from your local JSONL index
        chunks = await self.retriever.retrieve(query, k=8)
        logger.info("StudentRole.run retrieved %d chunks from RAG", len(chunks))

        context = "\n\n".join(
            f"[score={c.score:.3f} file={c.filename}]\n{c.text}"
            for c in chunks
        )

        # 2) Build grounded prompt for Ollama
        system_content = (
            "You are a student in the Dallas Center-Grimes (DCG) Community School District.\n"
            "You are responding honestly and respectfully to your parent.\n"
            "Use the CONTEXT below only for specific factual details (like classes or school info), "
            "but focus mainly on your feelings, challenges, and plans.\n"
            "Be honest, respectful, and concrete about what you can do next.\n\n"
            f"CONTEXT:\n{context}"
        )

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": query},
        ]

        # 3) Call local Ollama via /v1/chat/completions
        answer = await self.llm.chat(messages)
        logger.info("StudentRole.run finished; answer length=%d", len(answer or ""))

        return answer
