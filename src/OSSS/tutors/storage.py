import os, glob
from typing import List, Dict, Any
from dataclasses import dataclass
import chromadb
from chromadb.config import Settings
from pypdf import PdfReader

def chunk_text(text: str, chunk_size: int = 900, overlap: int = 150) -> List[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = words[i:i+chunk_size]
        chunks.append(" ".join(chunk))
        i += chunk_size - overlap
    return chunks

def pdf_to_text(path: str) -> str:
    reader = PdfReader(path)
    pages = []
    for p in reader.pages:
        try:
            pages.append(p.extract_text() or "")
        except Exception:
            pages.append("")
    return "\n\n".join(pages)

@dataclass
class RagStore:
    persist_dir: str
    collection_name: str
    client: chromadb.Client = None
    collection: chromadb.Collection = None

    def __post_init__(self):
        os.makedirs(self.persist_dir, exist_ok=True)
        self.client = chromadb.Client(Settings(persist_directory=self.persist_dir))
        try:
            self.collection = self.client.get_collection(self.collection_name)
        except Exception:
            self.collection = self.client.create_collection(self.collection_name)

    def index_paths(self, paths: List[str], embed_fn, rebuild: bool=False):
        if rebuild:
            self.client.delete_collection(self.collection_name)
            self.collection = self.client.create_collection(self.collection_name)

        docs, metas, ids = [], [], []
        counter = 0
        for path in paths:
            ext = os.path.splitext(path)[1].lower()
            if ext in (".txt",".md"):
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
            elif ext == ".pdf":
                text = pdf_to_text(path)
            else:
                continue

            for idx, ch in enumerate(chunk_text(text)):
                docs.append(ch)
                metas.append({"source": os.path.basename(path), "path": path, "page": idx+1})
                ids.append(f"doc-{counter}")
                counter += 1

        if not docs:
            return 0

        B = 32
        all_vecs = []
        for i in range(0, len(docs), B):
            all_vecs.extend(embed_fn(docs[i:i+B]))

        self.collection.add(documents=docs, embeddings=all_vecs, metadatas=metas, ids=ids)
        return len(ids)

    def search(self, query_vec, k:int=4):
        res = self.collection.query(query_embeddings=[query_vec], n_results=k)
        out = []
        for txt, meta in zip(res.get("documents", [[]])[0], res.get("metadatas", [[]])[0]):
            out.append({"text": txt, "metadata": meta})
        return out
