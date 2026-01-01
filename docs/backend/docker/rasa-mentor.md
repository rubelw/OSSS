# `rasa-mentor` service

This page documents the configuration for the `rasa-mentor` service from `docker-compose.yml`.

**Image:** `rasa/rasa:3.6.20`
**Container name:** `rasa-mentor`

**Ports:**

- `5005:5005`

**Volumes:**

- `./rasa:/app`

**Networks:**

- `osss-net`

**Environment:**

- `TZ=America/Chicago`
- `RASA_TELEMETRY_ENABLED=false`
- `SQLALCHEMY_SILENCE_UBER_WARNING=1`
- `SANIC_REQUEST_MAX_SIZE=104857600`
- `SANIC_REQUEST_MAX_HEADER_SIZE=65536`

**Command:**

```bash
bash -lc "set -euo pipefail;
    mkdir -p models;
    exec rasa run --enable-api --cors '*' --model models/current.tar.gz --port 5005 --debug"

```
