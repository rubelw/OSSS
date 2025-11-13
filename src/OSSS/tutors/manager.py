import os, yaml, httpx, anyio
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
import httpx

from .models import TutorConfig
from .storage import RagStore

log = logging.getLogger("OSSS.tutors")

# Read OSSS_TUTOR_CONFIG_DIR (fallback to /app/config/tutors), expand ~, and resolve
CFG_DIR = Path(os.getenv("OSSS_TUTOR_CONFIG_DIR", "/app/config/tutors")).expanduser().resolve()
log.info("Tutor config dir = %s", CFG_DIR)


OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://host.containers.internal:11434")
log.info("Tutor: using OLLAMA_BASE=%s", OLLAMA_BASE)

# Reusable short, sane timeouts: 5s connect, 30s read, 35s total
_HTTPX_TIMEOUT = httpx.Timeout(timeout=610.0, connect=5.0, read=600.0, write=60.0)


async def ollama_embed(model: str, texts: list[str]) -> list[list[float]]:
    try:
        async with httpx.AsyncClient(timeout=_HTTPX_TIMEOUT) as client:
            r = await client.post(f"{OLLAMA_BASE}/api/embeddings",
                                  json={"model": model, "input": texts})
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict) and "embeddings" in data: return data["embeddings"]
            if "embedding" in data: return [data["embedding"]]
            raise RuntimeError("Unexpected embeddings response")
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        # bubble up a clean message; FastAPI will turn into 502/500
        raise RuntimeError(f"[embed] Cannot reach Ollama at {OLLAMA_BASE}: {e}") from e


async def ollama_chat(model, messages, num_predict=512, temperature=0.2) -> str:
    payload = {"model": model, "messages": messages, "stream": False,
               "options": {"temperature": temperature, "num_predict": num_predict}}
    try:
        async with httpx.AsyncClient(timeout=_HTTPX_TIMEOUT) as client:
            r = await client.post(f"{OLLAMA_BASE}/api/chat", json=payload)
            if r.status_code == 404:
                raise RuntimeError(
                    f"Ollama not found at {OLLAMA_BASE}/api/chat. "
                    f'Check OLLAMA_BASE. Example values: '
                    f'"http://host.containers.internal:11434" (same network), '
                    f'"http://host.containers.internal:11434" (host).'
                )
            r.raise_for_status()
            data = r.json()
            return data.get("message", {}).get("content") or data.get("response", "")
    except httpx.ReadTimeout as e:
        raise RuntimeError(
            f"Ollama timed out at {OLLAMA_BASE} (model '{model}'). "
            f"Pre-pull the model or increase timeout."
        ) from e

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

    async def chat(self, user_prompt: str, history: List[Dict[str,str]]|None=None,
                   use_rag: Optional[bool]=None, max_tokens: Optional[int]=None) -> Dict[str, Any]:

        log.debug("tutor[%s]: chat start (rag=%s)", self.cfg.tutor_id,
           use_rag if use_rag is not None else self.cfg.rag_enabled)


        msgs = [{"role":"system","content": self.cfg.system_prompt}]
        if history:
            msgs.extend(history)

        sources = []
        if (use_rag if use_rag is not None else self.cfg.rag_enabled):
            store = self.ensure_store()
            if store:
                # 🔑 use async embed when already in an async context
                qv = (await self.embed([user_prompt]))[0]
                top = store.search(qv, k=4)
                if top:
                    blocks = []
                    for t in top:
                        meta = t["metadata"]; txt = t["text"]
                        blocks.append(f"[{meta.get('source','unknown')} — p{meta.get('page','?')}]\\n{txt}")
                        sources.append(meta)
                    context = "\\n\\n".join(blocks)
                    user_prompt = (
                        "Use the retrieved notes to answer clearly.\n\n"
                        f"Notes:\n{context}\n\nQuestion: {user_prompt}"
                    )

        msgs.append({"role":"user","content": user_prompt})
        log.debug("tutor[%s]: calling ollama_chat at %s", self.cfg.tutor_id, OLLAMA_BASE)

        answer = await ollama_chat(
            self.cfg.llm_model,
            msgs,
            num_predict=max_tokens or self.cfg.max_tokens,
            temperature=self.cfg.temperature
        )

        log.debug("tutor[%s]: chat done", self.cfg.tutor_id)

        return {"answer": answer, "sources": sources}

@dataclass
class TutorManager:
    config_dir: Optional[str] = None
    _runtimes: Dict[str, TutorRuntime] = field(default_factory=dict)


    def __post_init__(self):
        # If no path passed, use environment/CFG_DIR default
        base = Path(self.config_dir) if self.config_dir else CFG_DIR
        # Resolve but don’t fail if it doesn’t exist yet
        self.config_dir = str(base)
        os.makedirs(self.config_dir, exist_ok=True)
        log.info("TutorManager using config_dir=%s", self.config_dir)

    def list_configs(self) -> Dict[str, TutorConfig]:
        out = {}
        for path in sorted(os.listdir(self.config_dir)):
            if not path.endswith((".yml", ".yaml")):
                continue
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
        cfg_path_yml  = os.path.join(self.config_dir, f"{tutor_id}.yml")
        path = cfg_path_yaml if os.path.exists(cfg_path_yaml) else cfg_path_yml
        if not os.path.exists(path):
            raise FileNotFoundError(f"No config found for tutor '{tutor_id}' in {self.config_dir}")
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        cfg = TutorConfig(**raw)
        rt = TutorRuntime(cfg=cfg)
        self._runtimes[tutor_id] = rt
        return rt

    def create_or_update(self, cfg: TutorConfig):
        os.makedirs(self.config_dir, exist_ok=True)
        path = os.path.join(self.config_dir, f"{cfg.tutor_id}.yaml")
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(cfg.model_dump(), f, sort_keys=False, allow_unicode=True)
        self._runtimes.pop(cfg.tutor_id, None)
        log.info("Wrote tutor config: %s", path)
        return path

    pass

manager = TutorManager()  # uses OSSS_TUTOR_CONFIG_DIR or /app/config/tutors
