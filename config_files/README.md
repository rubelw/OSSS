# OSSS Configuration Files

The `config_files/` directory contains example, template, and reference configuration files
used across the **Open Source School Software (OSSS)** project.  
These files serve as starting points for local development, testing, and deployment environments.

They are **not active runtime configurations** by themselves — instead, they demonstrate how OSSS
services expect their configuration to be structured.

---

## 🎯 Purpose

This directory exists to help:

- developers get started quickly with properly structured config files
- infrastructure engineers prepare deployment environments
- contributors understand how OSSS services interact with required dependencies

Using these configs as a base ensures that each OSSS component receives expected settings
such as Keycloak URLs, database URIs, service ports, and identity/authorization values.

---

## 📦 What You’ll Find Here

| File / Folder | Description |
|---------------|-------------|
| `docker-compose.yml` *(if present)* | Example service stack for local development |
| `*.env.example` | Environment variable templates for OSSS services |
| `keycloak.json` or realm exports | Keycloak realm configuration for identity/SSO |
| `*.yaml` / `*.yml` | Service configuration templates (varies per release) |
| `*.conf` | Optional service‑specific configuration stubs |

> Actual filenames may vary between OSSS releases.

These files are **safe‑to‑copy templates** — customize them before deployment.

---

## 🧪 Using Template `.env` Files

1. Copy a file such as `.env.example`:
   ```bash
   cp .env.example .env
   ```

2. Update required values inside `.env`:
   ```env
   KEYCLOAK_BASE_URL=https://kc.example.com
   OSSS_DATABASE_URL=postgresql://user:pass@localhost:5432/osss
   REDIS_URL=redis://localhost:6379
   ```

3. Make sure your services source that `.env` file when running:
   ```bash
   docker compose --env-file config_files/.env up
   ```

---

## 🧩 Keycloak Realm Configuration (optional)

If a Keycloak realm export is provided here, import it into your Keycloak instance:

```bash
docker exec -it keycloak   /opt/keycloak/bin/kc.sh import --file /config/keycloak-realm.json
```

This simplifies matching user roles, audience, and client configuration used by OSSS.
Always review and modify provided realm files before deployment.

---

## 🚀 Recommended Workflow

```bash
# 1. Clone OSSS
git clone https://github.com/rubelw/OSSS.git
cd OSSS

# 2. Copy template .env files
cp config_files/.env.example src/a2a_server/.env.local
cp config_files/web.env.example src/osss-web/.env.local

# 3. Start services
docker compose up
```

> Each OSSS service may support environment inheritance from `.env.local` or `.env` —
review its README for exact behavior.

---

## 📌 Notes

- **Never commit production secrets** back into this directory.
- Treat these as **templates**, not final configuration.
- Some values (like `NEXTAUTH_SECRET`, `KEYCLOAK_CLIENT_SECRET`) should be generated uniquely per deployment.

---

## 🧾 License

These configuration templates are part of the OSSS project and are covered under the
license in the root of the repository.

---

If you'd like these templates auto‑generated during CI or `mkdocs build`, inform the maintainers.
