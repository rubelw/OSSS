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
import shutil

# Optional OCR (pytesseract)
try:
    import pytesseract  # type: ignore
    HAS_PYTESSERACT = True
except Exception:
    pytesseract = None
    HAS_PYTESSERACT = False

# Toggle OCR usage (even if pytesseract is installed)
ENABLE_OCR = True  # set to True if you want OCR on images

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
PDFS_ROOT = os.path.join(OUT_DIR, "pdfs")

# Mapping index name -> data subdirectory
INDEX_DATA_DIRS = {
    "main": "additional_llm_data",
    "tutor": "additional_llm_data_for_tutors",
    "agent": "additional_llm_data_for_agents",
}

# Use Ollama's embed endpoint that supports batching
OLLAMA_EMBED_URL = "http://localhost:11434/api/embed"
# Fallback single-embedding endpoint (older style)
OLLAMA_SINGLE_EMBED_URL = "http://localhost:11434/api/embeddings"
# Keep this in sync with what you use at query time
EMBED_MODEL = "nomic-embed-text"

# Chunking tuned for policies
MAX_CHARS = 900        # 800–1200 recommended
OVERLAP_CHARS = 180    # 150–250 recommended

# Maximum characters fed into embedding model (prevents Ollama crashes)
MAX_EMBED_CHARS = 4000   # gentler on Ollama

# Batch size for embedding requests
BATCH_SIZE = 4
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


def id_exists_in_index(doc_id, index_file):
    """Check if the given doc_id already exists in the index file.

    NOTE: not used in full-rebuild mode (we truncate OUT_FILE at startup
    and use UUIDs, so collisions are effectively impossible).
    """
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as out_f:
            for line in out_f:
                record = json.loads(line)
                if record["id"] == doc_id:
                    return True  # ID exists in the file
    return False  # ID does not exist in the file


def ensure_out_dir():
    if not os.path.exists(OUT_DIR):
        os.makedirs(OUT_DIR, exist_ok=True)
        log(f"Created output dir: {OUT_DIR}")
    else:
        log(f"Output dir exists: {OUT_DIR}")

    if not os.path.exists(IMAGES_ROOT):
        os.makedirs(IMAGES_ROOT, exist_ok=True)
        log(f"Created images base dir: {IMAGES_ROOT}")
    else:
        log(f"Images base dir exists: {IMAGES_ROOT}")

    if not os.path.exists(PDFS_ROOT):
        os.makedirs(PDFS_ROOT, exist_ok=True)
        log(f"Created pdfs base dir: {PDFS_ROOT}")
    else:
        log(f"Pdfs base dir exists: {PDFS_ROOT}")


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


def build_pdf_context_prefix(path: str):
    """
    Build a short, structured context prefix for a document based on its
    directory path relative to DATA_ROOT.

    Returns:
        rel (str): relative path to DATA_ROOT
        dir_rel (str): relative directory path (without filename)
        context_prefix (str): text prefix to prepend for embedding_text
    """
    # Path relative to the active DATA_ROOT (e.g. responsibilities/...)
    rel = os.path.relpath(path, DATA_ROOT)
    dir_rel = os.path.dirname(rel)

    if not dir_rel or dir_rel == ".":
        # No meaningful directory context
        context_prefix = ""
    else:
        # Turn 'school_board/2025-02-10/attachments' into
        # 'school_board / 2025-02-10 / attachments'
        pretty_dir = dir_rel.replace(os.sep, " / ")
        context_prefix = (
            f"Directory context: {pretty_dir}. "
            "This text is from a document associated with that context.\n\n"
        )

    return rel, dir_rel, context_prefix


def get_asset_dir_for_path(path: str, base_root: str):
    """
    For a given source document path (under DATA_ROOT), compute the directory
    under base_root where we will store assets, mirroring the source directory
    structure.

    Example (PDF):
      DATA_ROOT/additional_llm_data/responsibilities/RBAC_positions_and_table_access.pdf
      base_root = vector_indexes/main/pdfs
      -> asset_dir = vector_indexes/main/pdfs/responsibilities
    """
    rel, dir_rel, _ = build_pdf_context_prefix(path)

    if not dir_rel or dir_rel == ".":
        asset_dir = base_root
    else:
        asset_dir = os.path.join(base_root, dir_rel)

    os.makedirs(asset_dir, exist_ok=True)
    return asset_dir, rel, dir_rel


def extract_images_from_page(
    doc: fitz.Document,
    page_index: int,
    pdf_basename: str,
    asset_dir: str,
) -> List[dict]:
    """
    Extract images from a single page and save them to disk in asset_dir.
    Returns a list of dicts:
      {
        "path": <relative image path from PROJECT_ROOT>,
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
        img_path = os.path.join(asset_dir, img_name)

        rel_path = os.path.relpath(img_path, PROJECT_ROOT)
        ocr_text = ""

        try:
            with Image.open(io.BytesIO(img_bytes)) as pil_img:
                # Save the image to disk (under IMAGES_ROOT mirrored structure)
                pil_img.save(img_path)

                # Run OCR if available and enabled
                if HAS_PYTESSERACT and ENABLE_OCR:
                    try:
                        ocr_text_raw = pytesseract.image_to_string(
                            pil_img,
                            lang="eng",
                            config="--oem 1 --psm 6",
                        )
                        ocr_text = (ocr_text_raw or "").strip()
                        if ocr_text:
                            log(f"    OCR: extracted {len(ocr_text)} chars from image {img_name}")
                    except Exception as oe:
                        log(f"    ! OCR failed for image {img_name}: {oe}")
                else:
                    # OCR disabled or unavailable
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

    Images are saved under IMAGES_ROOT in a directory mirroring the source
    directory structure relative to DATA_ROOT.
    """
    log(f"Reading PDF (pdfplumber + PyMuPDF): {path}")
    log_mem("before_pdf_open")

    pages = []
    pdf_basename = os.path.splitext(os.path.basename(path))[0]

    # Where to store images for this PDF (mirrors source structure under IMAGES_ROOT)
    asset_dir, _, _ = get_asset_dir_for_path(path, IMAGES_ROOT)

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
                    image_infos = extract_images_from_page(
                        fitz_doc,
                        i,
                        pdf_basename,
                        asset_dir,
                    )
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


def embed_single_text(text: str, idx: int | None = None) -> list[float]:
    """
    Fallback: embed a single text using the older /api/embeddings endpoint.
    If it fails, return a tiny zero-vector.
    """
    t = text
    if len(t) > MAX_EMBED_CHARS:
        if idx is not None:
            log(f"  [fallback] Truncating chunk {idx} from {len(t)} to {MAX_EMBED_CHARS} chars for embedding")
        t = t[:MAX_EMBED_CHARS]

    for attempt in range(3):
        resp = None
        try:
            if idx is not None:
                log(f"  [fallback embed chunk {idx}] attempt {attempt+1}")
            resp = requests.post(
                OLLAMA_SINGLE_EMBED_URL,
                json={"model": EMBED_MODEL, "prompt": t},
                timeout=600,
            )
            resp.raise_for_status()
            data = resp.json()
            emb = data.get("embedding")
            if not emb:
                raise RuntimeError(f"Unexpected single-embedding response: {data}")
            return emb
        except Exception as e:
            log(f"  ! Fallback embedding error (attempt {attempt+1}): {e}")
            status = getattr(resp, "status_code", None) if resp is not None else None
            if status and 500 <= status < 600 and attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            else:
                log("  !! Giving up on this chunk, using zero-vector.")
                return [0.0]


def embed_batch(texts: list[str]):
    """
    Batch embeddings using Ollama's /api/embed endpoint with 'input': [...].

    - Truncates texts to MAX_EMBED_CHARS.
    - Processes in batches of BATCH_SIZE.
    - On batch failure after retries, falls back to per-chunk embedding via
      /api/embeddings so we don't lose the entire batch.
    """
    if not texts:
        log("  DEBUG: embed_batch called with empty texts; returning []")
        return []

    total = len(texts)
    all_embeddings: list[list[float]] = []

    # Preprocess (truncate) texts
    processed: list[str] = []
    for i, original_t in enumerate(texts, start=1):
        t = original_t
        if len(t) > MAX_EMBED_CHARS:
            log(f"  Truncating chunk {i} from {len(t)} to {MAX_EMBED_CHARS} chars for embedding")
            t = t[:MAX_EMBED_CHARS]
        processed.append(t)

    # Process in batches
    for start_idx in range(0, total, BATCH_SIZE):
        batch = processed[start_idx : start_idx + BATCH_SIZE]
        batch_num = start_idx // BATCH_SIZE + 1
        log(
            f"  [embed batch {batch_num}] size={len(batch)} "
            f"(chunks {start_idx+1}-{start_idx+len(batch)} of {total})"
        )
        log_mem(f"before_embeddings_batch_{batch_num}")

        batch_success = False
        resp = None

        for attempt in range(3):
            try:
                resp = requests.post(
                    OLLAMA_EMBED_URL,
                    json={"model": EMBED_MODEL, "input": batch},
                    timeout=600,
                )
                resp.raise_for_status()
                data = resp.json()
                emb_list = data.get("embeddings")

                if not emb_list or len(emb_list) != len(batch):
                    raise RuntimeError(f"Unexpected embeddings response: {data}")

                all_embeddings.extend(emb_list)
                log_mem(f"after_embeddings_batch_{batch_num}")
                batch_success = True
                break  # success, break retry loop

            except Exception as e:
                log(f"  ! Embedding error for batch {batch_num} (attempt {attempt+1}): {e}")
                status = getattr(resp, "status_code", None) if resp is not None else None
                # If server error and we have retries left, backoff and retry
                if status and 500 <= status < 600 and attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    continue
                else:
                    break  # break out of retry loop; we'll fallback to per-chunk

        if not batch_success:
            # Fallback: embed each chunk individually using /api/embeddings
            log(f"  !! Batch {batch_num} failed after retries; falling back to per-chunk embeddings.")
            for offset, t in enumerate(batch):
                idx_global = start_idx + offset + 1  # 1-based index for logging
                emb = embed_single_text(t, idx=idx_global)
                all_embeddings.append(emb)

    if len(all_embeddings) != total:
        log(f"  !! embed_batch produced {len(all_embeddings)} embeddings for {total} texts")
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


def save_pdf_to_pdfs_folder(pdf_path: str) -> str | None:
    """
    Copy the processed PDF into PDFS_ROOT mirroring the source directory structure
    relative to DATA_ROOT, so PDF copies live under vector_indexes/<index>/pdfs/...

    Returns:
        str | None: path to the copied PDF relative to PDFS_ROOT
                    e.g. "school_board/DCG-SchoolBoard/2025-6-10/.../Dr. Scott Blum ....pdf"
    """
    try:
        asset_dir, rel, dir_rel = get_asset_dir_for_path(pdf_path, PDFS_ROOT)
        dest_name = os.path.basename(pdf_path)
        dest_path = os.path.join(asset_dir, dest_name)

        if not os.path.exists(dest_path):
            shutil.copy2(pdf_path, dest_path)
            rel_dest_root = os.path.relpath(dest_path, PROJECT_ROOT)
            log(f"  Saved source PDF copy to {rel_dest_root}")
        else:
            rel_dest_root = os.path.relpath(dest_path, PROJECT_ROOT)
            log(f"  PDF copy already exists at {rel_dest_root}")

        # Return path relative to the PDFS_ROOT (this is what the API will append)
        rel_dest_pdf_root = os.path.relpath(dest_path, PDFS_ROOT)
        return rel_dest_pdf_root

    except Exception as e:
        log(f"  ! Failed to copy PDF into mirrored pdfs folder: {e}")
        return None

def process_pdf(pdf_path: str, idx: int, total: int, args):
    log(f"\n---- [{idx}/{total}] Processing PDF ----")
    log(f"PDF path: {pdf_path}")
    log_mem("before_extract_text")

    pages = extract_pages_with_images(pdf_path)
    if not pages:
        log("  ! No readable text or images, skipping.")
        return

    # Save a copy of the PDF into the mirrored structure under PDFS_ROOT
    # and get the path relative to PDFS_ROOT (e.g. "school_board/.../Dr. Scott ....pdf")
    pdf_index_rel = save_pdf_to_pdfs_folder(pdf_path)

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
                    "global_chunk_index": global_chunk_index,
                }
            )
            global_chunk_index += 1

    if not all_chunks:
        log("  ! No chunks produced for this PDF, skipping.")
        return

    # Build directory-based context prefix and relative paths
    rel, dir_rel, context_prefix = build_pdf_context_prefix(pdf_path)
    filename = os.path.basename(pdf_path)

    # embedding_text = directory context + chunk text
    if context_prefix:
        embedding_texts = [context_prefix + chunk for chunk in all_chunks]
    else:
        embedding_texts = list(all_chunks)

    log(f"  Directory context for embeddings: {dir_rel or '(none)'}")
    if context_prefix:
        log(f"  Example embedding prefix: {context_prefix[:120]!r}...")

    if args.extract_only:
        log("DEBUG: --extract-only set; not calling Ollama.")
        return

    doc_ids = [str(uuid.uuid4()) for _ in all_chunks]

    try:
        embeddings = embed_batch(embedding_texts)
    except Exception as e:
        log(f"  ! Embedding error, skipping this PDF: {e}")
        return

    if len(embeddings) != len(all_chunks):
        log(f"  ! Embedding count mismatch: {len(embeddings)} vs {len(all_chunks)}")
        return

    log(f"  Finished embeddings for {filename}, preparing to write {len(all_chunks)} chunks to JSONL")

    written_count = 0
    skipped_count = 0

    with open(OUT_FILE, "a", encoding="utf-8") as out_f:
        for emb_idx, (doc_id, chunk, emb) in enumerate(zip(doc_ids, all_chunks, embeddings)):
            m = meta[emb_idx]

            # Skip chunks where embedding fell back to a zero-vector
            if isinstance(emb, list) and len(emb) == 1 and emb[0] == 0.0:
                skipped_count += 1
                continue

            record = {
                "id": doc_id,
                "source": rel,  # path relative to DATA_ROOT
                "filename": filename,
                "chunk_index": emb_idx,
                "page_index": m["page_index"],
                "page_chunk_index": m["page_chunk_index"],
                "text": chunk,  # raw clean chunk text
                "embedding_text": embedding_texts[emb_idx],
                "embedding": emb,
                "image_paths": m.get("image_paths", []),
                "image_ocr_texts": m.get("image_ocr_texts", []),
                "directory_context": dir_rel,
                # 👇 NEW: path to the mirrored PDF under vector_indexes/<index>/pdfs
                # e.g. "school_board/DCG-SchoolBoard/2025-6-10/special_meeting/attachments/Dr. Scott Blum ....pdf"
                "pdf_index_path": pdf_index_rel,
            }
            out_f.write(json.dumps(record) + "\n")
            written_count += 1

    log(
        f"  ✔ Wrote {written_count} chunks for {rel} to JSONL "
        f"(skipped {skipped_count} chunks with failed embeddings)"
    )


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

    # Build directory-based context prefix and relative paths
    rel, dir_rel, context_prefix = build_pdf_context_prefix(doc_path)
    filename = os.path.basename(doc_path)

    # Build embedding_text by prepending the directory context to each chunk
    if context_prefix:
        embedding_texts = [context_prefix + chunk for chunk in all_chunks]
    else:
        embedding_texts = list(all_chunks)

    log(f"  Directory context for embeddings: {dir_rel or '(none)'}")
    if context_prefix:
        log(f"  Example embedding prefix: {context_prefix[:120]!r}...")

    if args.extract_only:
        log("DEBUG: --extract-only set; not calling Ollama.")
        return

    doc_ids = [str(uuid.uuid4()) for _ in all_chunks]

    try:
        # IMPORTANT: embed the enriched text, not the raw chunk
        embeddings = embed_batch(embedding_texts)
    except Exception as e:
        log(f"  ! Embedding error, skipping this document: {e}")
        return

    if len(embeddings) != len(all_chunks):
        log(f"  ! Embedding count mismatch: {len(embeddings)} vs {len(all_chunks)}")
        return

    log(f"  Finished embeddings for {filename}, preparing to write {len(all_chunks)} chunks to JSONL")

    written_count = 0
    skipped_count = 0

    # Now continue with appending to the file (no per-id existence check in full rebuild)
    with open(OUT_FILE, "a", encoding="utf-8") as out_f:
        for doc_id, chunk, emb_idx in zip(doc_ids, all_chunks, range(len(all_chunks))):
            emb = embeddings[emb_idx]

            # Skip chunks where embedding fell back to a zero-vector
            if isinstance(emb, list) and len(emb) == 1 and emb[0] == 0.0:
                skipped_count += 1
                continue

            record = {
                "id": doc_id,
                "source": rel,  # path relative to DATA_ROOT
                "filename": filename,
                "chunk_index": emb_idx,
                "page_index": None,  # no pages for TXT/CSV
                "page_chunk_index": None,
                "text": chunk,  # raw clean chunk text
                "embedding_text": embedding_texts[emb_idx],  # what we actually embedded
                "embedding": emb,
                "image_paths": [],  # no images for TXT/CSV
                "image_ocr_texts": [],
                "directory_context": dir_rel,  # e.g. "school_board/2025-11-10/notes"
            }
            out_f.write(json.dumps(record) + "\n")
            written_count += 1

    log(
        f"  ✔ Wrote {written_count} chunks for {rel} to JSONL "
        f"(skipped {skipped_count} chunks with failed embeddings)"
    )


def main():
    print("\n============================================================")
    print(" Rebuilding index for Ollama RAG (JSONL, no Chroma)")
    print(" (PDFs with optional OCR + TXT and CSV files)")
    print("============================================================\n")

    args = parse_args()

    # Recompute DATA_ROOT, OUT_DIR, OUT_FILE, IMAGES_ROOT, PDFS_ROOT based on --index
    global DATA_ROOT, OUT_DIR, OUT_FILE, IMAGES_ROOT, PDFS_ROOT

    data_subdir = INDEX_DATA_DIRS.get(args.index, "additional_llm_data")
    DATA_ROOT = os.path.join(PROJECT_ROOT, data_subdir)

    OUT_DIR = os.path.join(PROJECT_ROOT, "vector_indexes", args.index)
    OUT_FILE = os.path.join(OUT_DIR, "embeddings.jsonl")
    IMAGES_ROOT = os.path.join(OUT_DIR, "images")
    PDFS_ROOT = os.path.join(OUT_DIR, "pdfs")

    log(f"Current working dir: {os.getcwd()}")
    log(f"Project root:        {PROJECT_ROOT}")
    log(f"Data subdir:         {data_subdir}")
    log(f"Data root:           {DATA_ROOT}")
    log(f"Index name:          {args.index}")
    log(f"Out dir:             {OUT_DIR}")
    log(f"Out file:            {OUT_FILE}")
    log(f"Images base dir:     {IMAGES_ROOT}")
    log(f"Pdfs base dir:       {PDFS_ROOT}")
    log(f"Embedding model:     {EMBED_MODEL}")
    log(f"Chunk size/overlap:  {MAX_CHARS}/{OVERLAP_CHARS}")
    log(f"OCR available:       {HAS_PYTESSERACT}")
    log(f"OCR enabled:         {ENABLE_OCR}")
    if not HAS_PYTESSERACT or not ENABLE_OCR:
        log("  NOTE: OCR text from images will NOT be extracted (either pytesseract missing or OCR disabled).")
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
