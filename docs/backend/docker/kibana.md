# `kibana` service

This page documents the configuration for the `kibana` service from `docker-compose.yml`.

**Image:** `docker.elastic.co/kibana/kibana:8.14.3`
**Container name:** `kibana`

**Ports:**

- `5601:5601`

**Volumes:**

- `./config_files/elastic/kibana.yml:/usr/share/kibana/config/kibana.yml:ro,z`

**Depends on:**

- `elasticsearch`
- `kibana-pass-init`

**Networks:**

- `osss-net`

**Environment:**

- `ELASTICSEARCH_HOSTS=http://elasticsearch:9200`
- `SERVER_PUBLICBASEURL=http://kibana:5601`
- `LOGGING_VERBOSE=true`
- `ELASTICSEARCH_USERNAME=kibana_system`
- `ELASTICSEARCH_PASSWORD=${KIBANA_PASSWORD}`
- `KBN_SERVER_PUBLICBASEURL=http://localhost:5601`
- `XPACK_ENCRYPTEDSAVEDOBJECTS_ENCRYPTIONKEY=caeb7879368e3dd66d7302f6810daec1`
- `XPACK_REPORTING_ENCRYPTIONKEY=c1c89f500966ac710f7fa5eaf2939976`
- `XPACK_SECURITY_ENCRYPTIONKEY=e1458d710ffb321e4a4f4eb792c78b2b`
