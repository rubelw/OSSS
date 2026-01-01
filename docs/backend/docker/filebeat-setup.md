# `filebeat-setup` service

This page documents the configuration for the `filebeat-setup` service from `docker-compose.yml`.

**Image:** `docker.elastic.co/beats/filebeat:8.14.3`
**Container name:** `filebeat-setup`

**Volumes:**

- `./config_files/filebeat/filebeat.setup.yml:/usr/share/filebeat/filebeat.yml:ro,z`
- `es-shared:/shared:z`
- `./config_files/filebeat/setup.sh:/usr/local/bin/setup.sh:ro,z`
- `filebeat-data:/usr/share/filebeat/data:z`
- `filebeat-logs:/usr/share/filebeat/logs:z`

**Depends on:**

- `elasticsearch`
- `kibana`
- `es-shared-init`

**Networks:**

- `osss-net`

**Environment:**

- `KIBANA_URL=http://host.containers.internal:5601`
- `ES_URL=http://host.containers.internal:9200`
- `KIBANA_USERNAME=${KIBANA_USERNAME:-elastic}`
- `KIBANA_PASSWORD=${ELASTIC_PASSWORD:-password}`
- `ELASTIC_PASSWORD=${ELASTIC_PASSWORD:-password}`

**Command:**

```bash
/usr/local/bin/setup.sh
```
