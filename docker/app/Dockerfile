# Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# + iproute2 (ss) and net-tools (netstat)
RUN apt-get update && apt-get install -y --no-install-recommends \
      postgresql-client \
      curl \
      jq \
      iproute2 \
      net-tools \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
RUN python -m pip install --upgrade pip setuptools wheel

COPY src ./src
COPY gunicorn.conf.py ./
ENV PYTHONPATH=/app/src
RUN pip install .

RUN pip install --no-cache-dir \
      "gunicorn>=21" \
      "uvicorn[standard]>=0.30" \
      "asyncpg>=0.29" \
      "psycopg2-binary>=2.9"

EXPOSE 8000
ENV HOST=0.0.0.0 PORT=8000 LOG_LEVEL=info
CMD ["gunicorn", "-c", "gunicorn.conf.py"]
