# src/OSSS/ai/additional_index.py
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

HERE = os.path.dirname(__file__)
# Repo root = one level above src (…/workspace), not …/workspace/src
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

# Supported index kinds
INDEX_KINDS: Tuple[str, ...] = ("main", "tutor", "agent")

# Default paths for each index, overridable via environment variables:
#   OSSS_ADDITIONAL_INDEX_MAIN_PATH
#   OSSS_ADDITIONAL_INDEX_TUTOR_PATH
#   OSSS_ADDITIONAL_INDEX_AGENT_PATH
DEFAULT_INDEX_PATHS: Dict[str, str] = {
    kind: os.environ.get(
        f"OSSS_ADDITIONAL_INDEX_{kind.upper()}_PATH",
        os.path.join(REPO_ROOT, "vector_indexes", kind, "embeddings.jsonl"),
    )
    for kind in INDEX_KINDS
}


@dataclass
class IndexedChunk:
    id: str
    text: str
    source: str
    filename: str
    chunk_index: int
    embedding: np.ndarray
    # optional metadata from the indexer
    page_index: Optional[int] = None
    page_chunk_index: Optional[int] = None
    image_paths: Optional[List[str]] = None


# Per-index in-memory caches
_DOCS: Dict[str, List[IndexedChunk]] = {kind: [] for kind in INDEX_KINDS}
_INDEX_PATH: Dict[str, str] = DEFAULT_INDEX_PATHS.copy()
_LOADED: Dict[str, bool] = {kind: False for kind in INDEX_KINDS}


def _normalize_index_name(index: str) -> str:
    """Ensure index name is one of the supported kinds."""
    if index not in INDEX_KINDS:
        raise ValueError(
            f"Unknown index '{index}'. Expected one of: {', '.join(INDEX_KINDS)}"
        )
    return index


def _load_index(index: str, path: Optional[str] = None) -> List[IndexedChunk]:
    """Load the JSONL index for a given index name from disk into memory."""
    index = _normalize_index_name(index)
    index_path = path or _INDEX_PATH[index]

    print(f"[additional_index:{index}] REPO_ROOT={REPO_ROOT} index_path={index_path}")

    if not os.path.exists(index_path):
        print(f"[additional_index:{index}] No embeddings file found at {index_path}")
        return []

    docs: List[IndexedChunk] = []
    with open(index_path, "r", encoding="utf-8") as f:
        for line_idx, line in enumerate(f, start=1):
            if not line.strip():
                continue
            obj = json.loads(line)

            emb_list = obj.get("embedding")
            if not emb_list:
                # Skip malformed records
                continue
            emb = np.array(emb_list, dtype="float32")

            text = obj.get("text", "")
            source = obj.get("source", "")
            filename = obj.get("filename", "")
            chunk_index = int(obj.get("chunk_index", 0))

            # optional metadata
            page_index = obj.get("page_index")
            if page_index is not None:
                try:
                    page_index = int(page_index)
                except (TypeError, ValueError):
                    page_index = None

            page_chunk_index = obj.get("page_chunk_index")
            if page_chunk_index is not None:
                try:
                    page_chunk_index = int(page_chunk_index)
                except (TypeError, ValueError):
                    page_chunk_index = None

            image_paths = obj.get("image_paths") or []
            if not isinstance(image_paths, list):
                # Normalize to list[str]
                image_paths = [str(image_paths)]

            docs.append(
                IndexedChunk(
                    id=obj.get("id", f"{index}-chunk-{line_idx}"),
                    text=text,
                    source=source,
                    filename=filename,
                    chunk_index=chunk_index,
                    embedding=emb,
                    page_index=page_index,
                    page_chunk_index=page_chunk_index,
                    image_paths=image_paths,
                )
            )
    print(f"[additional_index:{index}] Loaded {len(docs)} chunks from {index_path}")
    return docs


def get_docs(index: str = "main") -> List[IndexedChunk]:
    """
    Return currently loaded chunks for the given index (lazy-load on first access).

    :param index: which index to use ("main", "tutor", or "agent").
                  Defaults to "main" for backwards compatibility.
    """
    index = _normalize_index_name(index)
    global _DOCS, _LOADED
    if not _LOADED[index]:
        _DOCS[index] = _load_index(index)
        _LOADED[index] = True
    return _DOCS[index]


def force_reload(index: str = "main", path: Optional[str] = None) -> int:
    """
    Force a reload of the index from disk.
    Returns the number of chunks loaded.

    :param index: which index to reload ("main", "tutor", or "agent").
    :param path:  optional explicit path to the index file for this index.
                  If provided, it updates the stored path for future loads.
    """
    index = _normalize_index_name(index)
    global _DOCS, _LOADED, _INDEX_PATH

    if path is not None:
        _INDEX_PATH[index] = path

    _DOCS[index] = _load_index(index, path=path)
    _LOADED[index] = True
    return len(_DOCS[index])


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two 1D vectors."""
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def top_k(
    query_embedding: np.ndarray,
    k: int = 8,
    index: str = "main",
) -> list[tuple[float, IndexedChunk]]:
    """
    Return top-k most similar chunks to the query embedding for the given index.

    :param query_embedding: numpy array representing the query embedding.
    :param k:               number of results to return.
    :param index:           which index to query ("main", "tutor", or "agent").
    """
    index = _normalize_index_name(index)
    docs = get_docs(index=index)
    scored: list[tuple[float, IndexedChunk]] = []
    for chunk in docs:
        sim = _cosine(query_embedding, chunk.embedding)
        scored.append((sim, chunk))

    scored.sort(key=lambda t: t[0], reverse=True)
    return scored[:k]
