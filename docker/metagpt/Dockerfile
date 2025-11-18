# docker/metagpt/Dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/work/src:$PYTHONPATH

WORKDIR /work

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      git \
    && rm -rf /var/lib/apt/lists/*

# MetaGPT + FastAPI/uvicorn for the sidecar
RUN pip install --no-cache-dir "metagpt==0.8.1" fastapi "uvicorn[standard]"

# Minimal MetaGPT config for Ollama
RUN mkdir -p /root/.metagpt && \
    printf '%s\n' \
'llm:' \
'  api_type: "ollama"' \
'  base_url: "http://host.containers.internal:11434/api"' \
'  model: "mistral:latest"' \
> /root/.metagpt/config2.yaml

# Code is provided at runtime via bind mount (see docker-compose)
# so no COPY src here.

CMD ["uvicorn", "MetaGPT.metagpt_server:app", \
     "--host", "0.0.0.0", \
     "--port", "8001", \
     "--reload", \
     "--reload-dir", "/work/src/MetaGPT"]
