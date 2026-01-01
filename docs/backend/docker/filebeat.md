# `filebeat` service

This page documents the configuration for the `filebeat` service from `docker-compose.yml`.

**Image:** `docker.elastic.co/beats/filebeat:8.14.3`
**Container name:** `filebeat`

**Volumes:**

- `es-shared:/shared:z`
- `./:/work:ro`
- `/run/systemd/journal:/run/systemd/journal:ro,rslave,z`
- `/run/log/journal:/run/log/journal:ro,rslave,z`
- `/var/log/journal:/var/log/journal:ro,rslave,z`
- `/etc/machine-id:/etc/machine-id:ro,z`
- `/var/lib/containers:/var/lib/containers:ro,rslave,z`
- `/run/podman/podman.sock:/var/run/podman.sock:ro`

**Environment:**

- `DOCKER_HOST=unix:///var/run/podman.sock`
- `VM_PROJ=/home/core/OSSS`

**Command:**

```bash
filebeat -e -c /work/config_files/filebeat/filebeat.podman.yml -E path.data=/shared/filebeat-data -E path.logs=/shared/filebeat-logs -E logging.level=debug -E logging.selectors=journald
```
