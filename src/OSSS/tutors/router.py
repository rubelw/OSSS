from fastapi import APIRouter, HTTPException
from fastapi import Depends
from typing import List, Dict, Any
from .models import TutorConfig, ChatRequest, ChatResponse
from .manager import TutorManager

def get_manager() -> TutorManager:
    import os
    return TutorManager(config_dir=os.getenv("TUTOR_CONFIG_DIR", "config/tutors"))

router = APIRouter(prefix="/tutors", tags=["tutors"])

@router.get("", response_model=List[TutorConfig])
def list_tutors(mgr: TutorManager = Depends(get_manager)):
    return list(mgr.list_configs().values())

@router.post("", response_model=TutorConfig)
def upsert_tutor(cfg: TutorConfig, mgr: TutorManager = Depends(get_manager)):
    mgr.create_or_update(cfg)
    return cfg

@router.post("/{tutor_id}/chat", response_model=ChatResponse)
async def chat(tutor_id: str, req: ChatRequest, mgr: TutorManager = Depends(get_manager)):
    try:
        rt = mgr.get_runtime(tutor_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    result = await rt.chat(user_prompt=req.message, history=[h.model_dump() for h in (req.history or [])], use_rag=req.use_rag, max_tokens=req.max_tokens)
    return ChatResponse(tutor_id=tutor_id, answer=result["answer"], sources=result["sources"])

@router.post("/{tutor_id}/ingest")
def ingest(tutor_id: str, rebuild: bool=False, mgr: TutorManager = Depends(get_manager)):
    # index files in data/source/{tutor_id} into data/chroma/{tutor_id}
    rt = mgr.get_runtime(tutor_id)
    store = rt.ensure_store()
    if store is None:
        raise HTTPException(status_code=400, detail="RAG disabled for this tutor")
    import glob, os
    src_dir = f"data/source/{tutor_id}"
    os.makedirs(src_dir, exist_ok=True)
    paths = []
    for ext in ("*.txt","*.md","*.pdf"):
        paths.extend(glob.glob(os.path.join(src_dir, ext)))
    added = store.index_paths(paths, embed_fn=rt.embed_sync, rebuild=rebuild)
    return {"tutor_id": tutor_id, "files_indexed": len(paths), "chunks_added": added}
