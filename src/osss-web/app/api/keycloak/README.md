# `app/api/keycloak/`

This directory contains **API routes that integrate OSSS Web with Keycloak**, the chosen identity
and access management solution. While `app/api/auth/` is powered by NextAuth.js for high-level
authentication flows (login, logout, sessions), this `keycloak` directory is reserved for
**direct, lower-level interactions with Keycloak’s Admin and Token APIs**.

---

## 📌 Purpose

- **Expose Keycloak-specific endpoints** for server-side logic that NextAuth does not cover.  
- **Bridge OSSS features with Keycloak’s Admin REST API**, e.g. user provisioning, role lookups,
  group membership, token exchange, and health checks.  
- **Support RBAC/ABAC models** by surfacing Keycloak roles, groups, and custom attributes into
  the OSSS application.  
- **Keep separation of concerns**:  
  - `api/auth/` → general authentication/session flows.  
  - `api/keycloak/` → OSSS-specific management and introspection endpoints.  

---

## 📂 Structure (typical)

```
app/api/keycloak/
├── token/route.ts        # Exchange/refresh tokens, or test token validity
├── users/route.ts        # CRUD for Keycloak users (server-protected)
├── roles/route.ts        # Query or assign realm/client roles
├── groups/route.ts       # Query Keycloak group membership hierarchy
└── health/route.ts       # Connectivity check against the Keycloak server
```

> Note: Your exact set of files may differ — adjust this README as routes evolve.

---

## 🔑 How It Works

- **Authentication**:  
  - Most routes authenticate to Keycloak using a **service account (client credentials)**.  
  - Secrets are drawn from environment variables (`KEYCLOAK_ISSUER`, `KEYCLOAK_CLIENT_ID`,
    `KEYCLOAK_CLIENT_SECRET`).

- **Authorization**:  
  - Protect routes with Next.js middleware or server-only checks so only administrators can
    trigger sensitive Keycloak operations (e.g., creating users).

- **Integration Pattern**:  
  - Client → OSSS frontend → `/api/keycloak/...` → server call to Keycloak Admin REST API → result.  
  - This avoids exposing the Keycloak Admin API directly to browsers.

---

## 🚦 Developer Notes

- **Environment variables required**:
  - `KEYCLOAK_ISSUER` – Base realm URL (e.g. `https://kc.example.com/realms/OSSS`).  
  - `KEYCLOAK_CLIENT_ID` / `KEYCLOAK_CLIENT_SECRET` – Service account credentials.  
  - Optional: `KEYCLOAK_ADMIN_URL` – Explicit Admin API endpoint if not discoverable.  

- **Edge vs Node runtimes**:  
  - These routes run in the **Node runtime** (not Edge) because they rely on secure secrets and
    external HTTP calls.  

- **Error handling**:  
  - Normalize errors from Keycloak (e.g., 401, 403, 409) into a consistent OSSS error format.  
  - Log request IDs and status codes, but **never log raw secrets or tokens**.  

---

## ✅ Summary

The `app/api/keycloak/` path provides **safe, server-side wrappers around Keycloak’s APIs**.  
It exists to support OSSS-specific identity and authorization needs that go beyond what the
generic `app/api/auth/` layer provides.  

It is central for features such as:  

- Synchronizing users and groups.  
- Enforcing district/organization-level RBAC/ABAC.  
- Running health checks and diagnostics against the IdP.  
