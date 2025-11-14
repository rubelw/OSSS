#!/usr/bin/env python3
import os
from datetime import datetime
from pypdf import PdfReader
import resource

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
PDF_ROOT = os.path.join(PROJECT_ROOT, "additional_llm_data")

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def mem(tag=""):
    usage = resource.getrusage(resource.RUSAGE_SELF)
    if tag:
        log(f"[MEM:{tag}] ru_maxrss={usage.ru_maxrss}")
    else:
        log(f"[MEM] ru_maxrss={usage.ru_maxrss}")

def find_first_pdf(root):
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.lower().endswith(".pdf"):
                return os.path.join(dirpath, name)
    return None

log("Starting test_pdf_chunk.py")
log(f"CWD:         {os.getcwd()}")
log(f"Project root:{PROJECT_ROOT}")
log(f"PDF root:    {PDF_ROOT}")
mem("startup")

pdf_path = find_first_pdf(PDF_ROOT)
if not pdf_path:
    log("No PDFs found under additional_llm_data/. Exiting.")
    exit(0)

log(f"Using first PDF found: {pdf_path}")
mem("before_open")

reader = PdfReader(pdf_path)
text = "\n".join((page.extract_text() or "") for page in reader.pages)
log(f"Extracted {len(text)} chars")
mem("after_read")

MAX_CHARS = 1200
OVERLAP_CHARS = 200
chunks = []
start = 0
n = len(text)
log("Beginning chunk loop")
mem("before_loop")

MAX_CHARS = 1200
OVERLAP_CHARS = 200
chunks = []
start = 0
n = len(text)
log("Beginning chunk loop")
mem("before_loop")

while start < n:
    end = min(n, start + MAX_CHARS)
    chunk = text[start:end].strip()
    if chunk:
        chunks.append(chunk)

    if end >= n:
        break

    next_start = end - OVERLAP_CHARS
    if next_start <= start:
        next_start = start + 1
    start = next_start

log(f"Finished chunking, got {len(chunks)} chunks")
mem("after_loop")
