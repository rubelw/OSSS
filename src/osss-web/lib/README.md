# `lib/`

This directory contains **shared utilities and library code** for the OSSS Web application.  
The code here is not UI-specific (unlike `components/`) but instead provides **core logic, helpers, and integrations** that are reused across multiple routes, API handlers, and features.

---

## 📌 Purpose

- **Encapsulate business logic** that should not live directly in components or API routes.
- **Provide thin wrappers around third-party libraries** (e.g., Keycloak, NextAuth, Redis) with OSSS-specific defaults.
- **Expose utility functions** for tasks such as API calls, auth/session handling, validation, and formatting.
- **Serve as a central place for app-wide constants and configuration helpers**.

---

## 📂 Structure (typical)

```
lib/
├── api-client.ts     # Typed fetch client for calling OSSS backend (FastAPI)
├── auth.ts           # NextAuth initialization (Node runtime)
├── auth-edge.ts      # Edge-safe authentication helpers
├── kc-token.ts       # Helpers for working with Keycloak tokens (validate/refresh)
├── redis.ts          # Redis storage initialization via unstorage
├── redis-adapter.ts  # NextAuth adapter for Redis
├── env.ts            # Centralized environment variable parsing & validation
└── utils.ts          # Generic helper functions (formatting, type guards, etc.)
```

> The exact file list may vary. Update this README as `lib/` evolves.

---

## 🔑 How It Works

- **API Clients**: Instead of calling `fetch` directly throughout the app, `api-client.ts` provides a preconfigured client with correct base URL, headers, and error handling.
- **Authentication**: `auth.ts` and `auth-edge.ts` centralize NextAuth setup so both Node and Edge runtimes can share a consistent API.
- **Keycloak Integration**: Helpers for working with Keycloak tokens ensure token parsing and refresh logic is consistent across the app.
- **Stateful Resources**: `redis.ts` and `redis-adapter.ts` initialize Redis-backed storage used by NextAuth for persistence.
- **Environment Management**: `env.ts` validates required environment variables at startup to fail fast if misconfigured.

---

## 🚦 Developer Notes

- **When to add code here**: If it’s not tied to a specific page or feature, and especially if it will be reused across multiple areas of the app, add it to `lib/`.
- **When NOT to add code here**: If the logic is feature-specific and unlikely to be reused elsewhere, colocate it with that feature’s route or component.
- **Edge vs Node**: Some files (e.g., `auth-edge.ts`) are designed for the Edge runtime; others (like `redis.ts`) only work in Node. Keep the distinction clear.
- **Testing**: All library utilities should have unit tests. Since they are pure functions or integration points, they are easiest to test in isolation.

---

## ✅ Summary

The `lib/` directory is the **core utility layer** of OSSS Web.  
It centralizes shared logic, integrations, and helpers so that:  

- API calls are consistent.  
- Authentication flows remain unified.  
- Environment variables are validated once.  
- Reusable utilities prevent code duplication.  

This makes the application **more maintainable, secure, and easier to extend**.  
