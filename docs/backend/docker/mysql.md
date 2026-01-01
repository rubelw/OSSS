# `mysql` service

This page documents the configuration for the `mysql` service from `docker-compose.yml`.

**Image:** `docker.getcollate.io/openmetadata/db:1.9.12`
**Container name:** `mysql`

**Ports:**

- `3306:3306`

**Volumes:**

- `mysql_data:/var/lib/mysql:z`

**Networks:**

- `osss-net`

**Environment:**

- `MYSQL_ROOT_PASSWORD=password`
- `MYSQL_DATABASE=openmetadata`
- `MYSQL_USER=openmetadata_user`
- `MYSQL_PASSWORD=openmetadata_password`

**Command:**

```bash
--sort_buffer_size=10M
```
