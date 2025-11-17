#!/usr/bin/env python3
import json
import math
import os
from datetime import datetime
from typing import List, Dict, Any

import requests

# ---- CONFIG ----
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_PATH = os.path.join(
    PROJECT_ROOT, "vector_indexes/main", "embeddings.jsonl"
)

OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"
GEN_MODEL = "llama3.1"
TOP_K = 5
# -----------------


def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def load_index() -> List[Dict[str, Any]]:
    if not os.path.exists(INDEX_PATH):
        raise SystemExit(f"Index file not found: {INDEX_PATH}")

    docs = []
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("embedding"):
                docs.append(obj)
    log(f"Loaded {len(docs)} embedded chunks from {INDEX_PATH}")
    return docs


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if len(a) != len(b):
        raise ValueError("Embedding dimension mismatch")
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def get_embedding(text: str) -> List[float]:
    resp = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": EMBED_MODEL, "prompt": text},
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    emb = data.get("embedding")
    if not emb:
        raise RuntimeError(f"Unexpected embedding response: {data}")
    return emb


def retrieve(question: str, docs: List[Dict[str, Any]], k: int = TOP_K):
    q_emb = get_embedding(question)
    scored = []
    for d in docs:
        emb = d.get("embedding")
        if not emb:
            continue
        sim = cosine_similarity(q_emb, emb)
        scored.append((sim, d))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:k]


def ask_llm(question: str, context_chunks: List[Dict[str, Any]]) -> str:
    context_text = "\n\n".join(
        f"[{i+1}] {c.get('source','?')}:\n{c.get('text','')}"
        for i, c in enumerate(context_chunks)
    )

    prompt = f"""You are an assistant answering questions using ONLY the provided school board policy text.

RULES:
- ONLY use the provided excerpts.
- If the answer is not clearly in the excerpts, say:
  "I don’t know based on the provided policies."
- Do NOT guess or invent new policy language.

EXCERPTS:
{context_text}

QUESTION: {question}

Answer based ONLY on the excerpts above.
"""

    resp = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": GEN_MODEL,
            "messages": [
                {"role": "system", "content": "You are a careful policy summarizer."},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        },
        timeout=600,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["message"]["content"]


def main():
    print("\n============================================================")
    print(" Test Ollama RAG over additional_llm_data embeddings.jsonl")
    print("============================================================\n")

    docs = load_index()

    try:
        while True:
            question = input("\n❓ Enter a policy question (or blank to exit): ").strip()
            if not question:
                break

            log(f"Embedding question: {question!r}")
            top = retrieve(question, docs, k=TOP_K)

            log("\nTop retrieved chunks:")
            for i, (score, d) in enumerate(top, start=1):
                print("------------------------------------------------------------")
                print(f"[{i}] score={score:.4f}")
                print(f"    source: {d.get('source')}")
                print("    text preview:")
                preview = (d.get("text") or "").replace("\n", " ")
                print("     ", preview[:300], "..." if len(preview) > 300 else "")

            answer = ask_llm(question, [d for _, d in top])
            print("\n💬 LLM Answer:")
            print(answer)
            print("\n============================================================")

    except KeyboardInterrupt:
        print("\nExiting.")


if __name__ == "__main__":
    main()
