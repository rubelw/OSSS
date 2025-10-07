# syntax=docker/dockerfile:1.7
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends     curl ca-certificates tzdata  && rm -rf /var/lib/apt/lists/*

COPY src/gateway/requirements.txt .
RUN pip install -r requirements.txt

COPY src/gateway/app ./app

# Non-root user
RUN useradd -ms /bin/bash appuser
USER appuser

EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=5s --retries=5 CMD curl -fsS http://localhost:8080/healthz || exit 1

ENV UVICORN_WORKERS=2
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
