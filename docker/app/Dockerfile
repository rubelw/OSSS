# Dockerfile (with CA baked in)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install dependencies + trust store tooling
RUN apt-get update && apt-get install -y --no-install-recommends \
      postgresql-client \
      curl \
      jq \
      iproute2 \
      net-tools \
      ca-certificates \
      openssl \
 && rm -rf /var/lib/apt/lists/*

# ---- Add your CA (PEM) and trust it ----
# Copy CA from repo into system trust store
COPY config_files/keycloak/secrets/ca/ca.crt /usr/local/share/ca-certificates/keycloak-ca.crt
RUN chmod 0644 /usr/local/share/ca-certificates/keycloak-ca.crt && update-ca-certificates

# Nice fallback envs pointing to the system bundle
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

WORKDIR /app

COPY pyproject.toml ./
RUN python -m pip install --upgrade pip setuptools wheel

COPY src ./src
COPY gunicorn.conf.py ./
ENV PYTHONPATH=/app/src
RUN pip install .

RUN pip install --no-cache-dir \
      "alembic>=1.13" \
      "gunicorn>=21" \
      "uvicorn[standard]>=0.30" \
      "asyncpg>=0.29" \
      "psycopg2-binary>=2.9" \
      "httpx>=0.27" \
      "prometheus-client>=0.20" \
      "PyJWT>=2.8,<3" \
      "chromadb==0.5.5" \
      "pypdf==4.3.1" \
      "guardrails-ai>=0.6.7" \
      "pydantic>=2.7" \
      "openai>=1.39"

# Talk to Ollama or your proxy using OpenAI-compatible /v1
ENV OPENAI_BASE_URL="http://ollama:11434/v1" \
    OPENAI_API_KEY="none" \
    LLM_MODEL="llama3.1"


EXPOSE 8000
ENV HOST=0.0.0.0 PORT=8000 LOG_LEVEL=info
CMD ["gunicorn", "-c", "gunicorn.conf.py"]