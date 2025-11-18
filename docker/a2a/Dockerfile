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
    "uvicorn[standard]" \
    httpx \
    openai

# --- App code ---
# Copy OSSS shared code if your A2A server imports from it (optional but probably useful)
COPY ./src/a2a_server ./a2a_server


# --- Uvicorn entrypoint ---
# Must match the actual module path: a2a_server/main.py with `app = FastAPI(...)`
CMD ["uvicorn", "a2a_server.main:app", "--host", "0.0.0.0", "--port", "8086"]


