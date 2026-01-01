# `elasticsearch` service

This page documents the configuration for the `elasticsearch` service from `docker-compose.yml`.

**Image:** `docker.elastic.co/elasticsearch/elasticsearch:8.14.3`
**Container name:** `elasticsearch`

**Ports:**

- `9200:9200`
- `9300:9300`

**Volumes:**

- `es-data:/usr/share/elasticsearch/data:z`
- `./config_files/elastic/elasticsearch.yml:/usr/share/elasticsearch/config/elasticsearch.yml:ro,z`
- `./config_files/keycloak/secrets/ca/ca.crt:/usr/share/elasticsearch/config/keycloak-ca.crt:ro,z`

**Networks:**

- `osss-net`

**Environment:**

- `OIDC_CLIENT_SECRET=${KIBANA_OIDC_CLIENT_SECRET}`
- `discovery.type=single-node`
- `xpack.security.enabled=true`
- `xpack.security.http.ssl.enabled=false`
- `ELASTIC_PASSWORD=${ELASTIC_PASSWORD}`
- `ES_JAVA_OPTS=-Xms512m -Xmx512m`
- `network.host=0.0.0.0`

**Command:**

```bash
/bin/bash -lc set -euo pipefail; [ -f config/elasticsearch.keystore ] || bin/elasticsearch-keystore create; if ! bin/elasticsearch-keystore list | grep -qx 'xpack.security.authc.realms.oidc.oidc1.rp.client_secret'; then echo "$OIDC_CLIENT_SECRET" | bin/elasticsearch-keystore add -xf xpack.security.authc.realms.oidc.oidc1.rp.client_secret; fi; exec /usr/local/bin/docker-entrypoint.sh eswrapper
```
