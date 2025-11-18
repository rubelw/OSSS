#!/usr/bin/env python3
import os
import uuid
import json
import argparse
from datetime import datetime
from typing import List

import requests
import resource  # for memory usage on macOS/Linux
import fitz  # PyMuPDF
from PIL import Image
import io
import pdfplumber
import time  # needed for retry backoff in embed_batch
import shutil  # <-- NEW: for copying PDFs

# Optional OCR (pytesseract)
try:
    import pytesseract  # type: ignore
    HAS_PYTESSERACT = True
except Exception:
    pytesseract = None
    HAS_PYTESSERACT = False

# ---- CONFIG ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# project root = one level up from scripts
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))

# Default data root for "main"; overridden in main() based on --index
DATA_ROOT = os.path.join(PROJECT_ROOT, "additional_llm_data")

# Default index is "main"; will be overridden in main() based on --index
OUT_DIR = os.path.join(PROJECT_ROOT, "vector_indexes", "main")
OUT_FILE = os.path.join(OUT_DIR, "embeddings.jsonl")
IMAGES_ROOT = os.path.join(OUT_DIR, "images")
PDFS_ROOT = os.path.join(OUT_DIR, "pdfs")  # <-- NEW: where we keep a copy of PDFs

# Mapping index name -> data subdirectory
INDEX_DATA_DIRS = {
    "main": "additional_llm_data",
    "tutor": "additional_llm_data_for_tutors",
    "agent": "additional_llm_data_for_agents",
}

OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
# Keep this in sync with what you use at query time
EMBED_MODEL = "nomic-embed-text"

# Chunking tuned for policies
MAX_CHARS = 900        # 800–1200 recommended
OVERLAP_CHARS = 180    # 150–250 recommended

# Maximum characters fed into embedding model (prevents Ollama crashes)
MAX_EMBED_CHARS = 8000   # safe limit; you can lower to 4000 if needed
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

    if not os.path.exists(IMAGES_ROOT):
        os.makedirs(IMAGES_ROOT, exist_ok=True)
        log(f"Created images dir: {IMAGES_ROOT}")
    else:
        log(f"Images dir exists: {IMAGES_ROOT}")

    if not os.path.exists(PDFS_ROOT):  # <-- NEW
        os.makedirs(PDFS_ROOT, exist_ok=True)
        log(f"Created pdfs dir: {PDFS_ROOT}")
    else:
        log(f"Pdfs dir exists: {PDFS_ROOT}")


def iter_pdfs(root: str):
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.lower().endswith(".pdf"):
                yield os.path.join(dirpath, name)


def iter_text_files(root: str, exts=(".txt", ".csv")):
    """Iterate over .txt and .csv files under root."""
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            lower = name.lower()
            if lower.endswith(exts):
                yield os.path.join(dirpath, name)


def extract_images_from_page(doc: fitz.Document, page_index: int, pdf_basename: str) -> List[dict]:
    """
    Extract images from a single page and save them to disk.
    Returns a list of dicts:
      {
        "path": <relative image path>,
        "ocr_text": <text from OCR or "" if none/failed>
      }
    """
    page = doc[page_index]
    img_infos: List[dict] = []

    images = page.get_images(full=True)
    if not images:
        return img_infos

    for img_info in images:
        xref = img_info[0]
        try:
            base_image = doc.extract_image(xref)
        except Exception as e:
            log(f"  ! Failed to extract image xref={xref} on page {page_index}: {e}")
            continue

        img_bytes = base_image.get("image")
        if not img_bytes:
            continue

        ext = base_image.get("ext", "png")
        img_name = f"{pdf_basename}_p{page_index+1}_{uuid.uuid4().hex[:8]}.{ext}"
        img_path = os.path.join(IMAGES_ROOT, img_name)

        rel_path = os.path.relpath(img_path, PROJECT_ROOT)
        ocr_text = ""

        try:
            with Image.open(io.BytesIO(img_bytes)) as pil_img:
                # Save the image to disk
                pil_img.save(img_path)

                # Run OCR if available
                if HAS_PYTESSERACT:
                    try:
                        ocr_text_raw = pytesseract.image_to_string(
                            pil_img,
                            lang="eng",
                            config="--oem 1 --psm 6"
                        )
                        ocr_text = (ocr_text_raw or "").strip()
                        if ocr_text:
                            log(f"    OCR: extracted {len(ocr_text)} chars from image {img_name}")
                    except Exception as oe:
                        log(f"    ! OCR failed for image {img_name}: {oe}")
                else:
                    # Only log once per run ideally, but this is simple and safe.
                    pass
        except Exception as e:
            log(f"  ! Failed to process/save image {img_name}: {e}")
            continue

        img_infos.append(
            {
                "path": rel_path,
                "ocr_text": ocr_text,
            }
        )

    if img_infos:
        num_with_text = sum(1 for i in img_infos if i["ocr_text"])
        log(
            f"  Extracted {len(img_infos)} images from page {page_index+1} "
            f"({num_with_text} with non-empty OCR text)"
        )

    return img_infos


def extract_pages_with_images(path: str):
    """
    Open a PDF and return a list of:
      {
        "page_index": int,
        "text": str,                 # includes PDF text (from pdfplumber) + OCR text from images
        "image_paths": List[str],
        "image_ocr_texts": List[str] # OCR text per image on that page
      }

    Uses:
      - pdfplumber for text extraction (better layout-aware text)
      - PyMuPDF (fitz) + pytesseract for image extraction/OCR.
    """
    log(f"Reading PDF (pdfplumber + PyMuPDF): {path}")
    log_mem("before_pdf_open")

    pages = []
    pdf_basename = os.path.splitext(os.path.basename(path))[0]

    # Open pdfplumber and fitz docs
    pdf_doc = None
    fitz_doc = None

    try:
        try:
            pdf_doc = pdfplumber.open(path)
        except Exception as e:
            log(f"  ! Failed to open PDF with pdfplumber: {e}")
            return []

        try:
            fitz_doc = fitz.open(path)
        except Exception as e:
            log(f"  ! Failed to open PDF with PyMuPDF for images: {e}")
            fitz_doc = None  # we'll just skip images if this fails

        num_pages = len(pdf_doc.pages)
        log(f"  PDF has {num_pages} pages")

        for i, p_page in enumerate(pdf_doc.pages):
            # 1. Extract text with pdfplumber
            try:
                text = p_page.extract_text() or ""
            except Exception as e:
                log(f"  ! Error extracting text on page {i} with pdfplumber: {e}")
                text = ""

            text = text.strip()

            # 2. Extract images + OCR text using fitz if available
            image_paths: List[str] = []
            image_ocr_texts: List[str] = []

            if fitz_doc is not None:
                try:
                    image_infos = extract_images_from_page(fitz_doc, i, pdf_basename)
                    image_paths = [info["path"] for info in image_infos]
                    image_ocr_texts = [info["ocr_text"] for info in image_infos if info.get("ocr_text")]
                except Exception as e:
                    log(f"  ! Error extracting images on page {i}: {e}")
            else:
                image_infos = []

            # 3. Append OCR text from images to page text
            if image_ocr_texts:
                ocr_blob = "\n".join(image_ocr_texts)
                combined = (text + "\n\n" + ocr_blob).strip() if text else ocr_blob
                text = combined

            # Keep the page if it has *either* text or images
            if text or image_paths:
                pages.append(
                    {
                        "page_index": i,
                        "text": text,
                        "image_paths": image_paths,
                        "image_ocr_texts": image_ocr_texts,
                    }
                )

        total_chars = sum(len(p["text"]) for p in pages)
        log(f"  Extracted {len(pages)} pages with content, total {total_chars} chars of text (incl. OCR)")
        log_mem("after_pdf_read")

    finally:
        if pdf_doc is not None:
            try:
                pdf_doc.close()
            except Exception:
                pass
        if fitz_doc is not None:
            try:
                fitz_doc.close()
            except Exception:
                pass

    return pages


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
    if not texts:
        log("  DEBUG: embed_batch called with empty texts; returning []")
        return []

    all_embeddings: list[list[float]] = []
    total = len(texts)

    for i, original_t in enumerate(texts, start=1):
        t = original_t
        if len(t) > MAX_EMBED_CHARS:
            log(f"  Truncating chunk {i} from {len(t)} to {MAX_EMBED_CHARS} chars for embedding")
            t = t[:MAX_EMBED_CHARS]

        for attempt in range(3):
            log(f"  [embed {i}/{total}] Requesting embedding from Ollama… (attempt {attempt+1})")
            log_mem(f"before_embeddings_{i}")

            try:
                resp = requests.post(
                    OLLAMA_EMBED_URL,
                    json={"model": EMBED_MODEL, "prompt": t},
                    timeout=600,
                )
                resp.raise_for_status()
                data = resp.json()
                emb = data.get("embedding")
                if not emb:
                    raise RuntimeError(f"Unexpected embeddings response: {data}")

                all_embeddings.append(emb)
                log_mem(f"after_embeddings_{i}")
                break  # success, break retry loop

            except Exception as e:
                log(f"  ! Embedding error for chunk {i} (attempt {attempt+1}): {e}")
                # If server error and we have retries left, backoff and retry
                status = getattr(resp, "status_code", None)
                if status and 500 <= status < 600 and attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    continue
                else:
                    log(f"  !! Giving up on chunk {i}, skipping this chunk.")
                    # For now, append a tiny zero-vector to preserve indexing:
                    all_embeddings.append([0.0])
                    break

    return all_embeddings


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Index documents into JSONL files using Ollama embeddings, including OCR text from "
            "embedded images in PDFs.\n"
            "Data roots:\n"
            "  main  -> ./additional_llm_data\n"
            "  tutor -> ./additional_llm_data_for_tutors\n"
            "  agent -> ./additional_llm_data_for_agents"
        )
    )

    parser.add_argument(
        "--index",
        type=str,
        choices=["main", "tutor", "agent"],
        default="main",
        help=(
            "Which index to write to. Controls BOTH the input data directory and the "
            "output under vector_indexes/.\n"
            "main  -> additional_llm_data\n"
            "tutor -> additional_llm_data_for_tutors\n"
            "agent -> additional_llm_data_for_agents"
        ),
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
        help="Only extract and preprocess documents (including OCR for PDFs) without calling Ollama or writing JSONL.",
    )

    return parser.parse_args()


def save_pdf_to_pdfs_folder(pdf_path: str):
    """
    Copy the processed PDF into the pdfs folder under OUT_DIR.
    If a file with the same name already exists, we keep the existing one.
    """
    try:
        os.makedirs(PDFS_ROOT, exist_ok=True)
        dest_name = os.path.basename(pdf_path)
        dest_path = os.path.join(PDFS_ROOT, dest_name)

        if not os.path.exists(dest_path):
            shutil.copy2(pdf_path, dest_path)
            rel_dest = os.path.relpath(dest_path, PROJECT_ROOT)
            log(f"  Saved source PDF copy to {rel_dest}")
        else:
            rel_dest = os.path.relpath(dest_path, PROJECT_ROOT)
            log(f"  PDF copy already exists at {rel_dest}")
    except Exception as e:
        log(f"  ! Failed to copy PDF into pdfs folder: {e}")


def process_pdf(pdf_path: str, idx: int, total: int, args):
    log(f"\n---- [{idx}/{total}] Processing PDF ----")
    log(f"PDF path: {pdf_path}")
    log_mem("before_extract_text")

    pages = extract_pages_with_images(pdf_path)
    if not pages:
        log("  ! No readable text or images, skipping.")
        return

    # Save a copy of the PDF into the pdfs folder
    save_pdf_to_pdfs_folder(pdf_path)

    # Build per-chunk data: text + metadata (page index, image paths, OCR texts)
    all_chunks: List[str] = []
    meta: List[dict] = []
    global_chunk_index = 0

    for page_data in pages:
        page_index = page_data["page_index"]
        page_text = page_data["text"]
        image_paths = page_data.get("image_paths", []) or []
        image_ocr_texts = page_data.get("image_ocr_texts", []) or []

        if not page_text:
            # If truly no text even after OCR, skip
            continue

        # Normalize whitespace before chunking
        clean_text = " ".join(page_text.split())
        if not clean_text:
            continue

        log(
            f"  Page {page_index+1}: normalized text length {len(clean_text)} chars "
            f"(images={len(image_paths)}, ocr_texts={len(image_ocr_texts)})"
        )
        page_chunks = chunk_text(clean_text)

        for page_chunk_idx, chunk in enumerate(page_chunks):
            all_chunks.append(chunk)
            meta.append(
                {
                    "page_index": page_index,
                    "page_chunk_index": page_chunk_idx,
                    "image_paths": image_paths,
                    "image_ocr_texts": image_ocr_texts,
                }
            )
            global_chunk_index += 1

    if not all_chunks:
        log("  ! No chunks produced for this PDF, skipping.")
        return

    if args.extract_only:
        log("DEBUG: --extract-only set; not calling Ollama.")
        return

    rel = os.path.relpath(pdf_path, DATA_ROOT)
    filename = os.path.basename(pdf_path)
    doc_ids = [str(uuid.uuid4()) for _ in all_chunks]

    try:
        embeddings = embed_batch(all_chunks)
    except Exception as e:
        log(f"  ! Embedding error, skipping this PDF: {e}")
        return

    if len(embeddings) != len(all_chunks):
        log(f"  ! Embedding count mismatch: {len(embeddings)} vs {len(all_chunks)}")
        return

    # Append to JSONL
    with open(OUT_FILE, "a", encoding="utf-8") as out_f:
        for doc_id, chunk, emb_idx, m in zip(doc_ids, all_chunks, range(len(all_chunks)), meta):
            record = {
                "id": doc_id,
                "source": rel,                      # relative path under this index's data root
                "filename": filename,               # base filename for prompts / UI
                "chunk_index": emb_idx,             # global chunk index within this PDF
                "page_index": m["page_index"],      # original page index
                "page_chunk_index": m["page_chunk_index"],
                "text": chunk,
                "embedding": embeddings[emb_idx],
                # local image paths (relative to PROJECT_ROOT)
                "image_paths": m.get("image_paths", []),
                # OCR text per image on that page (may be empty strings)
                "image_ocr_texts": m.get("image_ocr_texts", []),
            }
            out_f.write(json.dumps(record) + "\n")

    log(f"  ✔ Wrote {len(all_chunks)} chunks for {rel} to JSONL")


def process_text_or_csv(doc_path: str, idx: int, total: int, args):
    log(f"\n---- [{idx}/{total}] Processing TEXT/CSV ----")
    log(f"Doc path: {doc_path}")
    log_mem("before_text_read")

    try:
        with open(doc_path, "r", encoding="utf-8", errors="ignore") as f:
            raw_text = f.read()
    except Exception as e:
        log(f"  ! Failed to read file: {e}")
        return

    # Normalize whitespace
    clean_text = " ".join(raw_text.split())
    if not clean_text:
        log("  ! No text content after normalization, skipping.")
        return

    log(f"  Normalized text length {len(clean_text)} chars")
    all_chunks = chunk_text(clean_text)

    if not all_chunks:
        log("  ! No chunks produced, skipping.")
        return

    if args.extract_only:
        log("DEBUG: --extract-only set; not calling Ollama.")
        return

    rel = os.path.relpath(doc_path, DATA_ROOT)
    filename = os.path.basename(doc_path)
    doc_ids = [str(uuid.uuid4()) for _ in all_chunks]

    try:
        embeddings = embed_batch(all_chunks)
    except Exception as e:
        log(f"  ! Embedding error, skipping this document: {e}")
        return

    if len(embeddings) != len(all_chunks):
        log(f"  ! Embedding count mismatch: {len(embeddings)} vs {len(all_chunks)}")
        return

    with open(OUT_FILE, "a", encoding="utf-8") as out_f:
        for doc_id, chunk, emb_idx in zip(doc_ids, all_chunks, range(len(all_chunks))):
            record = {
                "id": doc_id,
                "source": rel,
                "filename": filename,
                "chunk_index": emb_idx,
                "page_index": None,          # no pages for TXT/CSV
                "page_chunk_index": None,
                "text": chunk,
                "embedding": embeddings[emb_idx],
                "image_paths": [],
                "image_ocr_texts": [],
            }
            out_f.write(json.dumps(record) + "\n")

    log(f"  ✔ Wrote {len(all_chunks)} chunks for {rel} to JSONL")


def main():
    print("\n============================================================")
    print(" Rebuilding index for Ollama RAG (JSONL, no Chroma)")
    print(" (PDFs with OCR + TXT and CSV files)")
    print("============================================================\n")

    args = parse_args()

    # Recompute DATA_ROOT, OUT_DIR, OUT_FILE, IMAGES_ROOT, PDFS_ROOT based on --index
    global DATA_ROOT, OUT_DIR, OUT_FILE, IMAGES_ROOT, PDFS_ROOT

    data_subdir = INDEX_DATA_DIRS.get(args.index, "additional_llm_data")
    DATA_ROOT = os.path.join(PROJECT_ROOT, data_subdir)

    OUT_DIR = os.path.join(PROJECT_ROOT, "vector_indexes", args.index)
    OUT_FILE = os.path.join(OUT_DIR, "embeddings.jsonl")
    IMAGES_ROOT = os.path.join(OUT_DIR, "images")
    PDFS_ROOT = os.path.join(OUT_DIR, "pdfs")  # <-- recompute per index

    log(f"Current working dir: {os.getcwd()}")
    log(f"Project root:        {PROJECT_ROOT}")
    log(f"Data subdir:         {data_subdir}")
    log(f"Data root:           {DATA_ROOT}")
    log(f"Index name:          {args.index}")
    log(f"Out dir:             {OUT_DIR}")
    log(f"Out file:            {OUT_FILE}")
    log(f"Images dir:          {IMAGES_ROOT}")
    log(f"Pdfs dir:            {PDFS_ROOT}")
    log(f"Embedding model:     {EMBED_MODEL}")
    log(f"Chunk size/overlap:  {MAX_CHARS}/{OVERLAP_CHARS}")
    log(f"OCR available:       {HAS_PYTESSERACT}")
    if not HAS_PYTESSERACT:
        log("  WARNING: pytesseract not installed or tesseract not available; OCR text will NOT be extracted.")
    log(f"Args: {args}")
    log_mem("startup")

    ensure_out_dir()

    # Decide which documents to process
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
        text_files: List[str] = []
    else:
        all_pdfs = list(iter_pdfs(DATA_ROOT))
        log(f"Found {len(all_pdfs)} PDFs total in {DATA_ROOT}.")
        if args.max_pdfs is not None:
            pdfs = all_pdfs[:args.max_pdfs]
            log(f"Limiting to first {args.max_pdfs} PDFs.")
        else:
            pdfs = all_pdfs

        text_files = list(iter_text_files(DATA_ROOT))
        log(f"Found {len(text_files)} TXT/CSV files total in {DATA_ROOT}.")

    docs = pdfs + text_files

    if not docs:
        log("No documents to process. Exiting.")
        return

    # Start with a fresh JSONL file for this run
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write("")  # truncate

    total = len(docs)
    for idx, path in enumerate(docs, start=1):
        ext = os.path.splitext(path)[1].lower()
        if ext == ".pdf":
            process_pdf(path, idx, total, args)
        elif ext in (".txt", ".csv"):
            process_text_or_csv(path, idx, total, args)
        else:
            log(f"\n---- [{idx}/{total}] Skipping unsupported file type: {path}")

    log("\n✅ Index rebuild run complete.")
    log_mem("shutdown")


if __name__ == "__main__":
    main()
