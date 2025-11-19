# docker/a2a/Dockerfile  (for a2a-agent only)
FROM python:3.11-slim

# --- Runtime env ---
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# --- System deps (curl handy for debugging/health checks) ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
 && rm -rf /var/lib/apt/lists/*

# --- Python deps ---
# The agent only needs python-a2a + httpx to talk to MetaGPT over HTTP.
RUN pip install --no-cache-dir \
    python-a2a \
    httpx

# Make /app/src importable as top-level package root.
# (docker-compose mounts ./src -> /app/src)
ENV PYTHONPATH=/app/src

