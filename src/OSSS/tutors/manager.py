import os, yaml, httpx, anyio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from .models import TutorConfig
from .storage import RagStore

OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://127.0.0.1:11434")

async def ollama_embed(model: str, texts: List[str]) -> List[List[float]]:
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{OLLAMA_BASE}/api/embeddings", json={"model": model, "input": texts})
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and "embeddings" in data:
            return data["embeddings"]
        if "embedding" in data:
            return [data["embedding"]]
        raise RuntimeError("Unexpected embeddings response")

async def ollama_chat(model: str, messages: List[Dict[str, str]], num_predict: int=512, temperature: float=0.2) -> str:
    payload = {"model": model, "messages": messages, "stream": False, "options": {"temperature": temperature, "num_predict": num_predict}}
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{OLLAMA_BASE}/api/chat", json=payload)
        r.raise_for_status()
        data = r.json()
        if "message" in data and "content" in data["message"]:
            return data["message"]["content"]
        return data.get("response", "")

@dataclass
class TutorRuntime:
    cfg: TutorConfig
    store: Optional[RagStore] = None

    def ensure_store(self):
        if not self.cfg.rag_enabled:
            return None
        if self.store is None:
            persist_dir = self.cfg.rag_index_dir.format(tutor_id=self.cfg.tutor_id)
            self.store = RagStore(persist_dir, collection_name=f"kb_{self.cfg.tutor_id}")
        return self.store

    async def embed(self, texts: List[str]) -> List[List[float]]:
        return await ollama_embed(self.cfg.embed_model, texts)

    def embed_sync(self, texts: List[str]) -> List[List[float]]:
        return anyio.run(self.embed, texts)

    def query_vec(self, text: str) -> List[float]:
        return self.embed_sync([text])[0]

    async def chat(self, user_prompt: str, history: List[Dict[str,str]]|None=None, use_rag: Optional[bool]=None, max_tokens: Optional[int]=None) -> Dict[str, Any]:
        msgs = [{"role":"system","content": self.cfg.system_prompt}]
        if history: msgs.extend(history)
        sources = []
        if (use_rag if use_rag is not None else self.cfg.rag_enabled):
            store = self.ensure_store()
            if store:
                qv = self.query_vec(user_prompt)
                top = store.search(qv, k=4)
                if top:
                    blocks = []
                    for t in top:
                        meta = t["metadata"]; txt = t["text"]
                        blocks.append(f"[{meta.get('source','unknown')} — p{meta.get('page','?')}]\\n{txt}")
                        sources.append(meta)
                    context = "\\n\\n".join(blocks)
                    user_prompt = f"Use the retrieved notes to answer clearly.\n\nNotes:\n{context}\n\nQuestion: {user_prompt}"
        msgs.append({"role":"user","content": user_prompt})
        answer = await ollama_chat(self.cfg.llm_model, msgs, num_predict=max_tokens or self.cfg.max_tokens, temperature=self.cfg.temperature)
        return {"answer": answer, "sources": sources}

@dataclass
class TutorManager:
    config_dir: str
    _runtimes: Dict[str, TutorRuntime] = field(default_factory=dict)

    def list_configs(self) -> Dict[str, TutorConfig]:
        out = {}
        for path in sorted(os.listdir(self.config_dir)):
            if not path.endswith((".yml",".yaml")): continue
            with open(os.path.join(self.config_dir, path), "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f)
            cfg = TutorConfig(**raw)
            out[cfg.tutor_id] = cfg
        return out

    def get_runtime(self, tutor_id: str) -> TutorRuntime:
        if tutor_id in self._runtimes:
            return self._runtimes[tutor_id]
        # load config
        cfg_path_yaml = os.path.join(self.config_dir, f"{tutor_id}.yaml")
        cfg_path_yml = os.path.join(self.config_dir, f"{tutor_id}.yml")
        path = cfg_path_yaml if os.path.exists(cfg_path_yaml) else cfg_path_yml
        if not os.path.exists(path):
            raise FileNotFoundError(f"No config found for tutor '{tutor_id}'")
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        cfg = TutorConfig(**raw)
        rt = TutorRuntime(cfg=cfg)
        self._runtimes[tutor_id] = rt
        return rt

    def create_or_update(self, cfg: TutorConfig):
        os.makedirs(self.config_dir, exist_ok=True)
        path = os.path.join(self.config_dir, f"{cfg.tutor_id}.yaml")
        import yaml
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(cfg.model_dump(), f, sort_keys=False, allow_unicode=True)
        # invalidate runtime to pick up new config next call
        if cfg.tutor_id in self._runtimes:
            del self._runtimes[cfg.tutor_id]
        return path
