from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import numpy as np
from metagpt.logs import logger


@dataclass
class RagChunk:
    text: str
    source: str
    filename: str
    score: float = 0.0
    meta: Optional[dict] = None


class JsonlRagRetriever:
    """
    Simple JSONL-based RAG retriever.

    Expects a file where each line is a JSON object like:

      {
        "text": "...",
        "embedding": [...],
        "source": "foo.pdf",
        "filename": "foo.pdf",
        "chunk_index": 0,
        "page_index": 0,
        "page_chunk_index": 0
      }

    We load all valid embeddings of the *same* dimension and skip any
    malformed or mismatched ones.
    """

    def __init__(
        self,
        index_path: str,
        embed_url: str = "http://host.containers.internal:11434/api/embeddings",
        embed_model: str = "nomic-embed-text",
    ):
        self.index_path = Path(index_path)
        self.embed_url = embed_url
        self.embed_model = embed_model

        self.embeddings: List[np.ndarray] = []
        self.chunks: List[RagChunk] = []
        self._matrix: Optional[np.ndarray] = None
        self._dim: Optional[int] = None

        if not self.index_path.exists():
            logger.warning(
                "JsonlRagRetriever: index file does not exist at %s; RAG will return no chunks",
                self.index_path,
            )
            return

        logger.info("JsonlRagRetriever: loading index from %s", self.index_path)
        self._load_index()

    def _load_index(self) -> None:
        dim: Optional[int] = None
        good = 0
        skipped_no_text = 0
        skipped_no_embedding = 0
        skipped_bad_dim = 0
        skipped_bad_json = 0

        with self.index_path.open("r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue

                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    skipped_bad_json += 1
                    logger.debug(
                        "JsonlRagRetriever: skipping bad JSON on line %d of %s",
                        line_idx,
                        self.index_path,
                    )
                    continue

                text = obj.get("text") or ""
                if not text:
                    skipped_no_text += 1
                    continue

                emb = obj.get("embedding")
                if not emb:
                    skipped_no_embedding += 1
                    continue

                arr = np.asarray(emb, dtype="float32")
                if arr.ndim != 1:
                    skipped_bad_dim += 1
                    logger.debug(
                        "JsonlRagRetriever: skipping non-1D embedding on line %d",
                        line_idx,
                    )
                    continue

                if dim is None:
                    dim = arr.shape[0]
                elif arr.shape[0] != dim:
                    skipped_bad_dim += 1
                    logger.warning(
                        "JsonlRagRetriever: skipping embedding with dim=%d "
                        "!= expected dim=%d at line %d",
                        arr.shape[0],
                        dim,
                        line_idx,
                    )
                    continue

                self.embeddings.append(arr)
                self.chunks.append(
                    RagChunk(
                        text=text,
                        source=obj.get("source") or "",
                        filename=obj.get("filename") or f"chunk_{line_idx}",
                        score=0.0,
                        meta={
                            "chunk_index": obj.get("chunk_index"),
                            "page_index": obj.get("page_index"),
                            "page_chunk_index": obj.get("page_chunk_index"),
                        },
                    )
                )
                good += 1

        self._dim = dim

        if not self.embeddings:
            logger.warning(
                "JsonlRagRetriever: no valid embeddings loaded from %s "
                "(good=%d, bad_json=%d, no_text=%d, no_emb=%d, bad_dim=%d)",
                self.index_path,
                good,
                skipped_bad_json,
                skipped_no_text,
                skipped_no_embedding,
                skipped_bad_dim,
            )
            self._matrix = None
            return

        logger.info(
            "JsonlRagRetriever: loaded %d embeddings (dim=%d) from %s "
            "(bad_json=%d, no_text=%d, no_emb=%d, bad_dim=%d)",
            good,
            dim or -1,
            self.index_path,
            skipped_bad_json,
            skipped_no_text,
            skipped_no_embedding,
            skipped_bad_dim,
        )

        # [N, D] matrix normalized for cosine similarity
        mat = np.stack(self.embeddings, axis=0)
        norms = np.linalg.norm(mat, axis=1, keepdims=True) + 1e-8
        self._matrix = mat / norms

    async def embed_query(self, query_emb: np.ndarray) -> np.ndarray:
        """
        In your current MetaGPT wiring, you're already using nomic-embed-text
        elsewhere. If you want this retriever to do its own embedding calls,
        you can implement that here (similar to your OSSS rag_router).
        For now, this method is a placeholder if you later want to call the
        retriever with raw text instead of a precomputed embedding.
        """
        raise NotImplementedError(
            "embed_query not implemented; call retrieve_with_vector instead "
            "or extend this class to hit Ollama /api/embeddings."
        )

    async def retrieve(self, query: str, k: int = 8) -> List[RagChunk]:
        """
        Simple keyword-based retrieval as a fallback when we don't have
        a query vector path wired in. This keeps your app from exploding
        while you experiment with embeddings.
        """
        # If no index, just return empty
        if self._matrix is None or not self.chunks:
            logger.warning(
                "JsonlRagRetriever.retrieve: no embeddings loaded; returning empty list"
            )
            return []

        # For now, use a dumb keyword score until you wire a real embedding call
        q = (query or "").lower().split()
        if not q:
            return []

        scored: List[RagChunk] = []
        for chunk in self.chunks:
            text = chunk.text.lower()
            score = float(sum(1 for token in q if token in text))
            if score > 0:
                scored.append(
                    RagChunk(
                        text=chunk.text,
                        source=chunk.source,
                        filename=chunk.filename,
                        score=score,
                        meta=chunk.meta,
                    )
                )

        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:k]
