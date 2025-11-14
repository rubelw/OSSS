#!/usr/bin/env python3
import os
import uuid
import json
import argparse
from datetime import datetime
from typing import List

import requests
from pypdf import PdfReader
import resource  # for memory usage on macOS/Linux


# ---- CONFIG ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# project root = one level up from scripts
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
PDF_ROOT = os.path.join(PROJECT_ROOT, "additional_llm_data")
OUT_DIR = os.path.join(PROJECT_ROOT, "vector_index_additional_llm_data")
OUT_FILE = os.path.join(OUT_DIR, "embeddings.jsonl")

OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
# Keep this in sync with what you use at query time
EMBED_MODEL = "nomic-embed-text"

# Chunking tuned for policies
MAX_CHARS = 900        # 800–1200 recommended
OVERLAP_CHARS = 180    # 150–250 recommended
# -----------------


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def log_mem(tag: str = ""):
    usage = resource.getrusage(resource.RUSAGE_SELF)
    rss = usage.ru_maxrss
    if tag:
        log(f"[MEM:{tag}] ru_maxrss={rss}")
    else:
        log(f"[MEM] ru_maxrss={rss}")


def ensure_out_dir():
    if not os.path.exists(OUT_DIR):
        os.makedirs(OUT_DIR, exist_ok=True)
        log(f"Created output dir: {OUT_DIR}")
    else:
        log(f"Output dir exists: {OUT_DIR}")


def iter_pdfs(root: str):
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.lower().endswith(".pdf"):
                yield os.path.join(dirpath, name)


def extract_text(path: str) -> str:
    log(f"Reading PDF: {path}")
    log_mem("before_pdf_open")
    try:
        reader = PdfReader(path)
    except Exception as e:
        log(f"  ! Failed to open PDF: {e}")
        return ""

    parts = []
    for i, page in enumerate(reader.pages):
        try:
            parts.append(page.extract_text() or "")
        except Exception as e:
            log(f"  ! Error on page {i}: {e}")
    text = "\n".join(parts)
    log(f"  Extracted {len(text)} chars (raw)")
    log_mem("after_pdf_read")
    return text


def chunk_text(text: str, max_chars: int = MAX_CHARS, overlap: int = OVERLAP_CHARS) -> List[str]:
    log("  DEBUG: Entering chunk_text()")
    log_mem("before_chunk_text")

    chunks: List[str] = []
    n = len(text)
    start = 0

    while start < n:
        end = min(n, start + max_chars)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= n:
            break

        # Advance with overlap, but ensure we move forward
        next_start = end - overlap
        if next_start <= start:
            next_start = start + 1
        start = next_start

    log(f"  Split into {len(chunks)} chunks (size={max_chars}, overlap={overlap})")
    log_mem("after_chunk_text")
    return chunks


def embed_batch(texts: list[str]):
    """
    Get embeddings for a list of texts using Ollama's embeddings API.

    Ollama's /api/embeddings endpoint expects ONE text per request,
    under the 'prompt' key, and returns a single vector under 'embedding'.
    """

    if not texts:
        log("  DEBUG: embed_batch called with empty texts; returning []")
        return []

    all_embeddings: list[list[float]] = []
    total = len(texts)

    for i, t in enumerate(texts, start=1):
        log(f"  [embed {i}/{total}] Requesting embedding from Ollama…")
        log_mem(f"before_embeddings_{i}")

        resp = requests.post(
            OLLAMA_EMBED_URL,
            json={"model": EMBED_MODEL, "prompt": t},
            timeout=600,
        )

        try:
            resp.raise_for_status()
        except Exception as e:
            log(f"  ! HTTP error from Ollama: {e}")
            log(f"    Raw response: {resp.text[:500]}")
            raise

        try:
            data = resp.json()
        except Exception as e:
            log(f"  ! Failed to parse JSON from Ollama: {e}")
            log(f"    Raw response: {resp.text[:500]}")
            raise

        emb = data.get("embedding")
        if not emb:
            log(f"  ! Unexpected embeddings response (empty/missing embedding): {data}")
            raise RuntimeError(f"Unexpected embeddings response: {data}")

        all_embeddings.append(emb)
        log_mem(f"after_embeddings_{i}")

    return all_embeddings


def parse_args():
    parser = argparse.ArgumentParser(
        description="Index PDFs under additional_llm_data/ into a JSONL file using Ollama embeddings."
    )
    parser.add_argument(
        "--max-pdfs",
        type=int,
        default=None,
        help="Limit the number of PDFs processed (for testing / incremental runs).",
    )
    parser.add_argument(
        "--single-pdf",
        type=str,
        default=None,
        help="Path to a single PDF (relative to project root or absolute).",
    )
    parser.add_argument(
        "--extract-only",
        action="store_true",
        help="Only extract and chunk PDFs; do NOT call Ollama (for debugging).",
    )
    return parser.parse_args()


def main():
    print("\n============================================================")
    print(" Rebuilding PDF index from additional_llm_data/ for Ollama RAG (JSONL, no Chroma)")
    print("============================================================\n")

    args = parse_args()

    log(f"Current working dir: {os.getcwd()}")
    log(f"Project root:        {PROJECT_ROOT}")
    log(f"PDF root:            {PDF_ROOT}")
    log(f"Out dir:             {OUT_DIR}")
    log(f"Out file:            {OUT_FILE}")
    log(f"Embedding model:     {EMBED_MODEL}")
    log(f"Chunk size/overlap:  {MAX_CHARS}/{OVERLAP_CHARS}")
    log(f"Args: {args}")
    log_mem("startup")

    ensure_out_dir()

    # Decide which PDFs to process
    if args.single_pdf:
        pdf_path = args.single_pdf
        # If it's not absolute, treat it as relative to PROJECT_ROOT
        if not os.path.isabs(pdf_path):
            pdf_path = os.path.abspath(os.path.join(PROJECT_ROOT, pdf_path))
        log(f"Resolved single PDF path: {pdf_path}")
        if not os.path.exists(pdf_path):
            log(f"  !! Resolved path does NOT exist: {pdf_path}")
            return
        pdfs = [pdf_path]
    else:
        all_pdfs = list(iter_pdfs(PDF_ROOT))
        log(f"Found {len(all_pdfs)} PDFs total.")
        if args.max_pdfs is not None:
            pdfs = all_pdfs[:args.max_pdfs]
            log(f"Limiting to first {args.max_pdfs} PDFs.")
        else:
            pdfs = all_pdfs

    if not pdfs:
        log("No PDFs to process. Exiting.")
        return

    # Start with a fresh JSONL file for this run
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write("")  # truncate

    for idx, pdf_path in enumerate(pdfs, start=1):
        log(f"\n---- [{idx}/{len(pdfs)}] Processing PDF ----")
        log(f"PDF path: {pdf_path}")
        log_mem("before_extract_text")

        text = extract_text(pdf_path)
        if not text.strip():
            log("  ! Empty or unreadable text, skipping.")
            continue

        # 🔧 Normalize whitespace before chunking
        clean_text = " ".join(text.split())
        log(f"  Normalized text length: {len(clean_text)} chars (was {len(text)})")

        log("DEBUG: calling chunk_text()")
        chunks = chunk_text(clean_text)
        if not chunks:
            log("  ! No chunks produced, skipping.")
            continue

        if args.extract_only:
            log("DEBUG: --extract-only set; not calling Ollama.")
            continue

        rel = os.path.relpath(pdf_path, PDF_ROOT)
        filename = os.path.basename(pdf_path)
        doc_ids = [str(uuid.uuid4()) for _ in chunks]

        try:
            embeddings = embed_batch(chunks)
        except Exception as e:
            log(f"  ! Embedding error, skipping this PDF: {e}")
            continue

        if len(embeddings) != len(chunks):
            log(f"  ! Embedding count mismatch: {len(embeddings)} vs {len(chunks)}")
            continue

        # Append to JSONL
        with open(OUT_FILE, "a", encoding="utf-8") as out_f:
            for doc_id, chunk, emb_idx in zip(doc_ids, chunks, range(len(chunks))):
                record = {
                    "id": doc_id,
                    "source": rel,             # relative path under additional_llm_data
                    "filename": filename,      # base filename for prompts / UI
                    "chunk_index": emb_idx,
                    "text": chunk,
                    "embedding": embeddings[emb_idx],
                }
                out_f.write(json.dumps(record) + "\n")

        log(f"  ✔ Wrote {len(chunks)} chunks for {rel} to JSONL")

    log("\n✅ Index rebuild run complete.")
    log_mem("shutdown")


if __name__ == "__main__":
    main()
