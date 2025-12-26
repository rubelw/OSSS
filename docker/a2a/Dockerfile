# Main application container (Production stage)
FROM python:3.11-slim

# Install dependencies needed for the app
RUN apt-get update && apt-get install -y --no-install-recommends \
      postgresql-client \
      curl \
      jq \
      iproute2 \
      net-tools \
      ca-certificates \
      openssl \
      git \
 && rm -rf /var/lib/apt/lists/*

# ---- Add your CA (PEM) and trust it ----
COPY config_files/keycloak/secrets/ca/ca.crt /usr/local/share/ca-certificates/keycloak-ca.crt
RUN chmod 0644 /usr/local/share/ca-certificates/keycloak-ca.crt && update-ca-certificates

# Set up environment variables for SSL certificates
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

WORKDIR /app

# Copy the app source code and installed dependencies
COPY pyproject.toml ./pyproject.toml
COPY README.md ./README.md
RUN python -m pip install --upgrade pip setuptools wheel
RUN pip install --upgrade typing-extensions>=4.14.1

COPY src ./src


COPY gunicorn.conf.py ./
ENV PYTHONPATH=/app/src
RUN pip install . --use-deprecated=legacy-resolver


# Install remaining dependencies
RUN pip install --use-deprecated=legacy-resolver --no-cache-dir \
      "metagpt==0.8.2" \
      "fastapi>=0.95" \
      "starlette>=0.21.0" \
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
      "openai>=1.39.0"
      #"itsdangerous>=2.0" \
      #"pydantic-settings" \
      #"python-jose" \
      #"redis>=4" \
      #"python-multipart" \
      #"python-dotenv" \
      #"passlib" \
      #"celery" \
      #"pytest" \
      #"pytest-asyncio" \
      #"databases" \
      #"sqlalchemy" \
      #"python-consul" \
      #"python-json-logger"

RUN pip install --upgrade typing-extensions>=4.14.1

# Minimal MetaGPT config for Ollama
RUN mkdir -p /root/.metagpt && \
    printf '%s\n' \
'llm:' \
'  api_type: "ollama"' \
'  base_url: "http://host.containers.internal:11434/api"' \
'  model: "llama3.1:latest"' \
'  api_key: "local-ollama"' \

> /root/.metagpt/config2.yaml

# Talk to Ollama or your proxy using OpenAI-compatible /v1
ENV OPENAI_BASE_URL="http://host.containers.internal:11434/v1" \
    OPENAI_API_KEY="none" \
    LLM_MODEL="llama3.1"

EXPOSE 8000
ENV HOST=0.0.0.0 PORT=8000 LOG_LEVEL=info
CMD ["gunicorn", "-c", "gunicorn.conf.py"]