# `om-elasticsearch` service

This page documents the configuration for the `om-elasticsearch` service from `docker-compose.yml`.

**Image:** `docker.elastic.co/elasticsearch/elasticsearch:8.11.4`
**Container name:** `om-elasticsearch`

**Ports:**

- `9201:9200`
- `9301:9300`

**Volumes:**

- `om-es-data:/usr/share/elasticsearch/data:z`

**Networks:**

- `osss-net`

**Environment:**

- `discovery.type=single-node`
- `ES_JAVA_OPTS=-Xms1024m -Xmx1024m`
- `xpack.security.enabled=false`
