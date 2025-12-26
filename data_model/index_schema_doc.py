#!/usr/bin/env python3
"""
Build a small schema index from schema_doc.md, embed it, and append
those chunks into the main additional index:

  ./schema_doc.md                → ./schema.index.jsonl
  ./schema.index.jsonl (+embed)  → ../vector_indexes/main/embeddings.jsonl
"""

from __future__ import annotations
import random
import time
import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict

import httpx

# Max characters per text we send to the embed endpoint.
# Prevents huge intent blocks from blowing up the server.
MAX_EMBED_TEXT_CHARS = int(os.getenv("OSSS_EMBED_MAX_CHARS", "4000"))

MAX_RETRIES = int(os.getenv("OSSS_EMBED_MAX_RETRIES", "4"))

RETRY_BASE_DELAY = float(os.getenv("OSSS_EMBED_RETRY_BASE_DELAY", "1.0"))  # seconds

# -----------------------------------------------------
# Paths
# -----------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent

SCHEMA_DOC_PATH = BASE_DIR / "schema_doc.md"
SCHEMA_INDEX_PATH = BASE_DIR / "schema.index.jsonl"

MAIN_INDEX_DIR = REPO_ROOT / "vector_indexes" / "main"
MAIN_INDEX_PATH = MAIN_INDEX_DIR / "embeddings.jsonl"

# -----------------------------------------------------
# Embedding config – local-friendly defaults
# -----------------------------------------------------

EMBED_MODEL = os.getenv("OSSS_EMBED_MODEL", "nomic-embed-text")

# On Mac/local CLI, talk to localhost by default.
# In containers, you can override with OSSS_EMBED_BASE / OSSS_EMBED_URL.
DEFAULT_EMBED_BASE = os.getenv("OSSS_EMBED_BASE", "http://localhost:11434")
EMBED_URL = os.getenv("OSSS_EMBED_URL", f"{DEFAULT_EMBED_BASE}/api/embeddings")

print(f"[index_schema_doc] Using EMBED_URL={EMBED_URL} model={EMBED_MODEL}")


class EmbeddingError(Exception):
    """Non-fatal error while requesting an embedding."""
    pass


def _extract_embedding(ej: dict) -> List[float]:
    """
    Normalize various embedding response schemas into a 1D list[float].

    Supports:
    - OpenAI-style: {"data": [{"embedding": [...]}]}
    - Ollama-style: {"embedding": [...]}
    """
    if isinstance(ej, dict):
        if "data" in ej and ej["data"]:
            return list(map(float, ej["data"][0]["embedding"]))
        if "embedding" in ej:
            return list(map(float, ej["embedding"]))
    raise ValueError(f"Could not find embedding in response: keys={list(ej.keys())}")


def embed_text(text: str) -> List[float]:
    """
    Call the embedding endpoint for a single piece of text.
    Retries on transient errors (5xx, network issues) with exponential backoff.
    Only raises EmbeddingError after MAX_RETRIES attempts.
    """
    payload = {
        "model": EMBED_MODEL,
        "prompt": text,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = httpx.post(EMBED_URL, json=payload, timeout=30.0)
            resp.raise_for_status()
            data = resp.json()
            return _extract_embedding(data)

        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            # ❓ Retry only transient failures
            should_retry = False

            if isinstance(exc, httpx.HTTPStatusError):
                status = exc.response.status_code
                # Retry only 5xx (not 4xx or 3xx)
                if 500 <= status < 600:
                    should_retry = True
            else:
                # Network-level errors: retry
                should_retry = True

            if should_retry and attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                # small jitter avoids synchronized retry storms
                delay = delay + random.uniform(0, 0.3)
                print(
                    f"[index_schema_doc] embed failed (attempt {attempt}/{MAX_RETRIES}), "
                    f"retrying in {delay:.1f}s..."
                )
                time.sleep(delay)
                continue

            # 🚨 Final failure — now we raise non-fatal EmbeddingError
            raise EmbeddingError(
                f"[index_schema_doc] Embed failed after {attempt} attempts\n"
                f"  URL={EMBED_URL}\n"
                f"  error={exc}"
            ) from exc

# -----------------------------------------------------
# Schema Doc → schema.index.jsonl
# -----------------------------------------------------

@dataclass
class SchemaChunk:
    id: str
    text: str
    source: str = "schema_doc"
    filename: str = "schema_doc.md"
    chunk_index: int = 0
    # Optional helper metadata (not required by additional_index loader)
    table: str | None = None


# Special-case synonyms / typos for tricky tables
TABLE_SYNONYMS: Dict[str, List[str]] = {
    # This is the important one for your use case:
    "consents": [
        "consent",
        "consents",
        "concent",   # common typo
        "concents",  # the one you've been using
    ],
    # Add more tables here if you want similar behavior:
    # "meetings": ["meeting", "meetings", "board meeting"],
}


def build_intent_phrases(table: str, description: str) -> List[str]:
    """
    Build natural-language 'intent' phrases for a given table.

    These get embedded into the additional index so that fuzzy queries
    like 'I want to query consents' / 'I want to update consents'
    / 'I want to delete some concents' are semantically close to
    the relevant table.

    We generate phrases for:
      - create
      - query / read
      - update / modify
      - delete / remove
    """
    # Human-readable form of the table name
    base = table.replace("_", " ")

    # Collect all terms we want to generate patterns for:
    #   - pretty name with spaces
    #   - raw table name
    #   - any configured synonyms/typos
    synonyms = TABLE_SYNONYMS.get(table, [])
    all_terms = {base, table, *synonyms}

    phrases: List[str] = []

    # --- CREATE / ADD ---
    for s in all_terms:
        phrases.extend(
            [
                f"I want to create {s}.",
                f"I want to create new {s}.",
                f"create {s}",
                f"create new {s}",
                f"add a new {s} record",
                f"add new {s} records",
            ]
        )

    # --- QUERY / READ ---
    for s in all_terms:
        phrases.extend(
            [
                f"I want to query {s}.",
                f"query {s}",
                f"show me {s}",
                f"list all {s}",
                f"get {s} records",
                f"fetch {s} data",
            ]
        )

    # --- UPDATE / MODIFY ---
    for s in all_terms:
        phrases.extend(
            [
                f"I want to update {s}.",
                f"I want to modify {s}.",
                f"update {s}",
                f"modify {s}",
                f"change existing {s} record",
                f"edit {s} records",
            ]
        )

    # --- DELETE / REMOVE ---
    for s in all_terms:
        phrases.extend(
            [
                f"I want to delete {s}.",
                f"delete {s}",
                f"remove {s} records",
                f"delete some {s}",
                f"remove some {s} records",
            ]
        )

    # Optional: tie to the description if present
    if description:
        desc = description.strip().replace("\n", " ")
        phrases.append(
            (
                f"This table is used when users ask to create, query, "
                f"update, modify, or delete {base}. {desc}"
            )
        )

    return phrases


def _split_schema_doc(md_text: str) -> List[SchemaChunk]:
    """
    Very simple parser:

    Treat any line starting with "TABLE: " as the start of a new chunk,
    and accumulate until the next TABLE or EOF.

    For each table we emit:
      1) A main schema-doc chunk.
      2) An 'intent' chunk with natural-language phrases (CRUD-style).
    """
    lines = md_text.splitlines()
    chunks: List[SchemaChunk] = []

    current_table: str | None = None
    buffer: List[str] = []

    def flush():
        nonlocal current_table, buffer, chunks
        if current_table is None:
            return
        text = "\n".join(buffer).strip()
        if not text:
            return

        chunk_id = f"schema::{current_table}"

        # 1) Main schema description chunk
        main_chunk = SchemaChunk(
            id=chunk_id,
            text=text,
            source="schema_doc",
            filename="schema_doc.md",
            chunk_index=0,  # will be overwritten later with a stable index
            table=current_table,
        )
        chunks.append(main_chunk)

        # 2) Intent phrases chunk (natural language CRUD-style phrases)
        intent_phrases = build_intent_phrases(current_table, text)
        if intent_phrases:
            intent_chunk = SchemaChunk(
                id=f"{chunk_id}::intent",
                text="\n".join(intent_phrases),
                source="schema_doc_intent",
                filename="schema_doc.md",
                chunk_index=0,  # will be overwritten later
                table=current_table,
            )
            chunks.append(intent_chunk)

        buffer = []

    for line in lines:
        if line.startswith("TABLE: "):
            # new table section
            flush()
            current_table = line[len("TABLE: ") :].strip()
            buffer = [line]
        else:
            if current_table is not None:
                buffer.append(line)

    # flush last
    flush()
    return chunks


def build_schema_index() -> None:
    """
    Read schema_doc.md and create schema.index.jsonl with records for each table
    plus synthetic 'intent' records (e.g., "I want to query consents",
    "I want to update consents", "I want to delete some concents").
    """
    if not SCHEMA_DOC_PATH.exists():
        raise SystemExit(f"schema_doc.md not found at {SCHEMA_DOC_PATH}")

    print(f"[index_schema_doc] Loading schema_doc.md → {SCHEMA_DOC_PATH}")
    md_text = SCHEMA_DOC_PATH.read_text(encoding="utf-8")
    chunks = _split_schema_doc(md_text)

    with SCHEMA_INDEX_PATH.open("w", encoding="utf-8") as f:
        for idx, chunk in enumerate(chunks):
            # Give each chunk a stable index
            chunk.chunk_index = idx
            f.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")

    print(
        f"[index_schema_doc] Wrote {len(chunks)} schema chunks (including intent phrases) → {SCHEMA_INDEX_PATH}"
    )


# -----------------------------------------------------
# schema.index.jsonl → embeddings → append to main
# -----------------------------------------------------

def load_schema_records() -> List[dict]:
    if not SCHEMA_INDEX_PATH.exists():
        raise SystemExit(
            f"{SCHEMA_INDEX_PATH} not found. Run this script once to build it from schema_doc.md."
        )

    records: List[dict] = []
    with SCHEMA_INDEX_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    print(f"[index_schema_doc] Loaded {len(records)} records from schema.index.jsonl")
    return records


def embed_and_append_to_main(records: List[dict]) -> None:
    MAIN_INDEX_DIR.mkdir(parents=True, exist_ok=True)

    # Append-mode: we don't try to dedupe; easiest for now.
    appended = 0
    skipped = 0

    with MAIN_INDEX_PATH.open("a", encoding="utf-8") as out:
        for rec in records:
            text = rec.get("text", "")
            if not text:
                continue

            rec_id = rec.get("id", "(no id)")

            # Truncate very long texts so the embed server doesn't 500 on us.
            if len(text) > MAX_EMBED_TEXT_CHARS:
                print(
                    f"[index_schema_doc] WARNING: text for {rec_id} is "
                    f"{len(text)} chars; truncating to {MAX_EMBED_TEXT_CHARS}"
                )
                text = text[:MAX_EMBED_TEXT_CHARS]

            print(f"[index_schema_doc] Embedding {rec_id} ...")
            try:
                emb = embed_text(text)
            except EmbeddingError as exc:
                skipped += 1
                print(
                    f"[index_schema_doc] ERROR embedding {rec_id}; skipping this record.\n"
                    f"{exc}"
                )
                continue

            rec["embedding"] = emb

            # Ensure required metadata fields exist
            rec.setdefault("source", "schema_doc")
            rec.setdefault("filename", "schema_doc.md")
            rec.setdefault("chunk_index", 0)

            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            appended += 1

    print(
        f"[index_schema_doc] Appended {appended} embedded schema chunks "
        f"(skipped {skipped} records) → {MAIN_INDEX_PATH}"
    )
    print(
        "[index_schema_doc] Now reload in-app with:\n"
        "  POST /ai/a2a/reload-additional-index?index=main"
    )


# -----------------------------------------------------
# Main
# -----------------------------------------------------

def main():
    # 1) Build / refresh schema.index.jsonl from schema_doc.md
    build_schema_index()

    # 2) Load those records
    records = load_schema_records()

    # 3) Embed + append into main embeddings.jsonl
    embed_and_append_to_main(records)


if __name__ == "__main__":
    main()
