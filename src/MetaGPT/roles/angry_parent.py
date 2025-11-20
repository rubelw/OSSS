from __future__ import annotations

import os
from typing import List, Dict, Any

from metagpt.roles import Role
from metagpt.logs import logger

from .rag.jsonl_retriever import JsonlRagRetriever
from .llm.ollama_client import OllamaChatClient


class AngryParentRole(Role):
    name: str = "angry_parent"

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

        # Local Ollama config (override via env if you want)
        base_url = os.getenv("OLLAMA_BASE_URL", "http://host.containers.internal:11434")
        model = os.getenv("OLLAMA_MODEL", "llama3.2")

        logger.info(
            "AngryParentRole initializing with Ollama base_url=%s model=%s",
            base_url,
            model,
        )

        self.llm = OllamaChatClient(
            base_url=base_url,
            model=model,
        )

        # Path to your RAG JSONL index
        index_path = os.getenv(
            "RAG_INDEX_PATH",
            "/vector_indexes/main/embeddings.jsonl",
        )
        self.retriever = JsonlRagRetriever(index_path=index_path)

    async def run(self, *args: Any, **kwargs: Any) -> str:
        """
        Entry point used by metagpt_server /run.
        We take the incoming 'query', retrieve local context, and call Ollama with a grounded prompt.
        """
        logger.info("AngryParentRole.run starting...")

        # Get query from kwargs or first positional arg
        query = kwargs.get("query") or (args[0] if args else "")
        if not query:
            # Fallback prompt if nothing was passed
            query = (
                "You are an uncaring, destructive parent.\n\n"
                "Below is a description of the student's current grades.\n"
                "Write a single, clear question you would ask the student to "
                "understand how they feel about their grades."
            )

        # 1) RAG retrieve from your local JSONL index
        chunks = await self.retriever.retrieve(query, k=8)
        logger.info("AngryParentRole.run retrieved %d chunks from RAG", len(chunks))

        context = "\n\n".join(
            f"[score={c.score:.3f} file={c.filename}]\n{c.text}"
            for c in chunks
        )

        # 2) Build grounded prompt for Ollama
        system_content = (
            "You are a uncaring, destructive parent for a student in the "
            "Dallas Center-Grimes (DCG) Community School District.\n"
            "Use ONLY the information in the CONTEXT below when referring to "
            "specific grades, classes, or school details.\n"
            "If the answer is not clearly supported by the context, you may still "
            "write a supportive question, but do NOT invent specific grades or facts.\n\n"
            f"CONTEXT:\n{context}"
        )

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": query},
        ]

        # 3) Call local Ollama via /v1/chat/completions
        answer = await self.llm.chat(messages)
        logger.info("AngryParentRole.run finished; answer length=%d", len(answer or ""))

        return answer
