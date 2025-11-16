# src/OSSS/ai/additional_index.py
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

# Repo root = src/OSSS/.. (adjust if you mount differently in Docker)
HERE = os.path.dirname(__file__)
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

DEFAULT_INDEX_PATH = os.environ.get(
    "OSSS_ADDITIONAL_INDEX_PATH",
    os.path.join(REPO_ROOT, "vector_index_additional_llm_data", "embeddings.jsonl"),
)


@dataclass
class IndexedChunk:
    id: str
    text: str
    source: str
    filename: str
    chunk_index: int
    embedding: np.ndarray


_DOCS: List[IndexedChunk] = []
_INDEX_PATH: str = DEFAULT_INDEX_PATH
_LOADED: bool = False


def _load_index(path: Optional[str] = None) -> List[IndexedChunk]:
    """Load the JSONL index from disk into memory."""
    index_path = path or _INDEX_PATH

    if not os.path.exists(index_path):
        print(f"[additional_index] No embeddings file found at {index_path}")
        return []

    docs: List[IndexedChunk] = []
    with open(index_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            obj = json.loads(line)
            emb = np.array(obj["embedding"], dtype="float32")
            docs.append(
                IndexedChunk(
                    id=obj.get("id", ""),
                    text=obj["text"],
                    source=obj.get("source", ""),
                    filename=obj.get("filename", ""),
                    chunk_index=int(obj.get("chunk_index", 0)),
                    embedding=emb,
                )
            )
    print(f"[additional_index] Loaded {len(docs)} chunks from {index_path}")
    return docs


def get_docs() -> List[IndexedChunk]:
    """Return currently loaded chunks (lazy-load on first access)."""
    global _DOCS, _LOADED
    if not _LOADED:
        _DOCS = _load_index()
        _LOADED = True
    return _DOCS


def force_reload(path: Optional[str] = None) -> int:
    """
    Force a reload of the index from disk.
    Returns the number of chunks loaded.
    """
    global _DOCS, _LOADED, _INDEX_PATH

    if path is not None:
        _INDEX_PATH = path

    _DOCS = _load_index()
    _LOADED = True
    return len(_DOCS)
