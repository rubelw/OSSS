# Start from official Postgres 16 image
#FROM postgres:16
FROM pgvector/pgvector:pg16


# Install curl and jq (optional but useful for JSON parsing)
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl jq \
 && rm -rf /var/lib/apt/lists/*

# Verify binaries
RUN psql --version && curl --version

# Default command remains the same as postgres:16
