# Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# (optional) system deps if you use psycopg2 (non-binary)
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# install deps first for layer caching
COPY pyproject.toml ./
# if you have a poetry.lock or requirements*.txt, copy them too
# COPY poetry.lock ./
# COPY requirements.txt ./
# RUN pip install -r requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel
# copy the source next so we can install the package
COPY src ./src
COPY gunicorn.conf.py ./

# make src importable as "OSSS"
ENV PYTHONPATH=/app/src

# install the app as a package (build from pyproject)
RUN pip install .

EXPOSE 8000

# sensible defaults; override with env at runtime if needed
ENV HOST=0.0.0.0 \
    PORT=8000 \
    LOG_LEVEL=info

# gunicorn reads wsgi_app from gunicorn.conf.py, so we can keep cmd minimal
CMD ["gunicorn", "-c", "gunicorn.conf.py"]
