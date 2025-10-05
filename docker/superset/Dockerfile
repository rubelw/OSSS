# docker/superset/Dockerfile
FROM apache/superset:latest

# Try prebuilt wheels first (works on arm64 generally).
# If this fails on your platform, see the fallback below.
USER root
RUN pip install --no-cache-dir \
      psycopg2-binary==2.9.* \
      pillow \
      redis
USER superset

# ---- Fallback (only if the above fails to compile/install) ----
# Uncomment these lines and comment out the 'pip install psycopg2-binary' above:
# USER root
# RUN apt-get update && apt-get install -y --no-install-recommends \
#       gcc build-essential libpq-dev python3-dev \
#   && rm -rf /var/lib/apt/lists/*
# RUN pip install --no-cache-dir psycopg2==2.9.* pillow redis
# USER superset
