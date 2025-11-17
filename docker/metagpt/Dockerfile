# docker/metagpt/Dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /work

# system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      git \
    && rm -rf /var/lib/apt/lists/*

# 1) Install MetaGPT (pins openai==1.6.1)
RUN pip install --no-cache-dir "metagpt==0.8.1"

# 2) Install FastAPI + Uvicorn for the sidecar API
RUN pip install --no-cache-dir fastapi "uvicorn[standard]"

# 3) Copy OSSS sources so OSSS.agents.* is importable
COPY pyproject.toml ./pyproject.toml
COPY src ./src

# 4) Install OSSS code ONLY (no deps, to avoid conflicts)
RUN pip install -e . --no-deps

# 5) Provide a minimal MetaGPT config2.yaml that uses Ollama
#    This avoids the "Config.llm field required" ValidationError
RUN mkdir -p /root/.metagpt && \
    printf '%s\n' \
'llm:' \
'  api_type: "ollama"' \
'  base_url: "http://host.containers.internal:11434/api"' \
'  model: "mistral:latest"' \
> /root/.metagpt/config2.yaml

# 6) Run the sidecar API (server is in src/OSSS/agents/metagpt_server.py)
CMD ["uvicorn", "OSSS.agents.metagpt_server:app", "--host", "0.0.0.0", "--port", "8001"]
