# OSSS/ai/rag/jsonl_rag.py

import json
import numpy as np
import httpx
from fastapi import HTTPException

EMBED_MODEL = "nomic-embed-text"
OLLAMA_BASE = "http://localhost:11434"
EMBED_URL = f"{OLLAMA_BASE}/api/embeddings"

def _extract_embedding(ej: dict) -> list[float]:
    if isinstance(ej, dict) and "data" in ej:
        return ej["data"][0]["embedding"]
    if isinstance(ej, dict) and "embedding" in ej:
        return ej["embedding"]
    if isinstance(ej, dict) and "embeddings" in ej:
        return ej["embeddings"][0]
    raise ValueError(f"Unexpected embedding response schema: {ej}")

def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)

def _search_jsonl(query_emb: np.ndarray, jsonl_path: str, top_k: int = 5):
    scored = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            emb = np.array(row["embedding"], dtype="float32")
            score = _cosine(query_emb, emb)
            scored.append((score, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]

def _format_context(results):
    lines = []
    for i, (score, row) in enumerate(results, 1):
        text = row.get("text", "")
        doc_id = row.get("id", f"chunk-{i}")
        lines.append(f"[{i}] id={doc_id} score={score:.4f}\n{text}")
    return "\n\n".join(lines)

async def rag_prefetch(query: str, jsonl_path: str, top_k: int = 5) -> str:
    async with httpx.AsyncClient(timeout=10.0) as client:
        embed_req = {"model": EMBED_MODEL, "prompt": query}
        er = await client.post(EMBED_URL, json=embed_req)
        if er.status_code >= 400:
            raise HTTPException(status_code=er.status_code, detail=er.text)
        ej = er.json()

    try:
        vec = _extract_embedding(ej)
    except ValueError as e:
        raise HTTPException(status_code=500, detail={"error": str(e), "response": ej})

    query_emb = np.array(vec, dtype="float32")
    top = _search_jsonl(query_emb, jsonl_path=jsonl_path, top_k=top_k)
    return _format_context(top)

# Optional alias to keep names stable
async def rag_prefetch_jsonl(query: str, jsonl_path: str, top_k: int = 5) -> str:
    return await rag_prefetch(query=query, jsonl_path=jsonl_path, top_k=top_k)
