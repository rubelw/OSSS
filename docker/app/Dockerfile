# Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System deps (psycopg2 compile, SSL for asyncpg, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      libpq-dev \
      curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install build tools first for better caching
COPY pyproject.toml ./
RUN python -m pip install --upgrade pip setuptools wheel

# Copy source & gunicorn config
COPY src ./src
COPY gunicorn.conf.py ./

# Make src importable as "OSSS"
ENV PYTHONPATH=/app/src

# Install your application (from pyproject)
RUN pip install .

# Install the process manager + ASGI worker
# - gunicorn: master process
# - uvicorn[standard]: uvicorn worker with uvloop, httptools, etc.
RUN pip install --no-cache-dir "gunicorn>=21" "uvicorn[standard]>=0.30"

EXPOSE 8000

# Sensible defaults; override with env at runtime if needed
ENV HOST=0.0.0.0 \
    PORT=8000 \
    LOG_LEVEL=info

# gunicorn reads settings (incl. app import) from gunicorn.conf.py
CMD ["gunicorn", "-c", "gunicorn.conf.py"]
