FROM python:3.11-slim

# --- Runtime env ---
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

# --- System deps (curl handy for debugging/health checks) ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
 && rm -rf /var/lib/apt/lists/*

# --- Python deps ---
# If you eventually add the A2A server to pyproject.toml, you can do `pip install .` instead.
RUN pip install --no-cache-dir \
    fastapi \
    "metagpt==0.8.1" \
    "uvicorn[standard]" \
    httpx \
    openai \
    python-a2a


# Minimal MetaGPT config for Ollama
RUN mkdir -p /root/.metagpt && \
    printf '%s\n' \
'llm:' \
'  api_type: "ollama"' \
'  base_url: "http://host.containers.internal:11434/api"' \
'  model: "llama3.2-vision:latest"' \
> /root/.metagpt/config2.yaml


# if you’re building code inside the image
# COPY src ./src

# make /app/src importable as top-level package root
ENV PYTHONPATH=/app/src

