# OSSS Web (Next.js) — Overview

_This page describes the **frontend** application located at:_  
`src/osss-web` (commit **e7c3fcf69557527d1c09b9d47096fac63c0af246**).

The web app is built with **Next.js (App Router)** and **TypeScript**. It integrates with **Auth.js (NextAuth)** and **Keycloak** for authentication, and optionally uses **Redis** (via `unstorage`) for user/account persistence on the server side. The app is organized to keep UI, routing, and integration code cleanly separated.

---

## Key Features

- **Next.js App Router**: `app/` directory with segment-based layouts, server/client components, and API route handlers under `app/api/**`.
- **Authentication**: NextAuth (Auth.js) configured with **Keycloak**; JWT session strategy by default.
- **Edge + Node**: Middleware and server components can run in the Edge runtime; storage-backed features (Redis adapter) run in Node.
- **TypeScript-first**: Strict typing with shared types under `types/`; utilities under `lib/`.
- **Reusable UI**: Common components in `components/`; public assets in `public/`.

---

## Project Structure (high level)

```
src/osss-web/
├── app/                         # App Router entry-point (layouts, pages, API routes)
│   ├── api/
│   │   └── auth/                # NextAuth handlers and related routes
│   ├── administration/          # Feature routes
│   ├── finance/
│   ├── human-resources/
│   ├── parent-communications/
│   ├── school-board/
│   ├── facilities/
│   ├── transportation/
│   ├── layout.tsx               # Root layout for all pages
│   └── page.tsx                 # Home page
├── components/                  # Reusable UI components (buttons, forms, nav, cards, etc.)
├── lib/                         # Non-UI helpers and integrations
│   ├── auth.ts                  # NextAuth config (Node runtime)
│   ├── auth-edge.ts             # Edge-safe auth helpers (no Node APIs)
│   ├── api-client.ts            # Typed fetch wrapper for backend calls
│   ├── kc-token.ts              # Keycloak token helpers
│   ├── redis.ts                 # Redis-backed unstorage
│   ├── redis-adapter.ts         # Unstorage adapter wiring for NextAuth
│   └── env.ts                   # Centralized environment access/validation
├── types/                       # Shared TypeScript type definitions
├── public/                      # Static assets served as-is (favicon, images, docs)
├── providers.tsx                # App-wide client providers (e.g., SessionProvider)
├── middleware.ts                # Edge middleware (auth gates, rewrites/redirects)
├── layout.tsx                   # (If colocated at root app level depending on version)
├── next.config.js               # Next.js configuration (rewrites, output tracing root)
└── package.json
```

> Some filenames may vary slightly; see local tree for the exact list. The `app/api/auth` and `lib/auth.ts` pairing is central to login/session flows.

---

## Authentication Flow (Keycloak + NextAuth)

1. **Provider**: `lib/auth.ts` registers the **Keycloak** provider with PKCE and a compact `profile(...)` mapper.  
2. **Session strategy**: JWT (stateless) by default — good for Edge; accounts/users can be persisted via Redis on Node.  
3. **Route handlers**: `app/api/auth/[...nextauth]/route.ts` exports NextAuth `GET`/`POST` handlers.  
4. **Client usage**: Components use `useSession()` to read session state; `signIn()` / `signOut()` to start flows.  
5. **Middleware**: `middleware.ts` can perform light auth gating in the Edge runtime (no Node APIs).

> For detailed explanations, see the comments in `lib/auth.ts`, `auth-edge.ts`, and `app/api/auth/` README (if present).

---

## Environment Variables

Create an `.env.local` in `src/osss-web` (or at the repository root if your tooling loads from there) with the following variables:

| Name | Purpose | Example |
|---|---|---|
| `NEXTAUTH_URL` | Absolute URL of the web app (used by NextAuth) | `http://localhost:3000` |
| `NEXTAUTH_SECRET` | Random secret for session/JWT encryption | `openssl rand -base64 32` |
| `KEYCLOAK_ISSUER` | Keycloak realm issuer URL | `https://kc.example.com/realms/OSSS` |
| `WEB_KEYCLOAK_CLIENT_ID` | Keycloak client ID for the web app | `osss-web` |
| `WEB_KEYCLOAK_CLIENT_SECRET` | Corresponding client secret | `***` |
| `REDIS_URL` | Redis base URL (optional) | `redis://127.0.0.1:6379` |
| `REDIS_PASSWORD` | Redis password (optional) | `***` |
| `NODE_ENV` | Enables debug logs when `development` | `development` |

> If Redis is password-protected, the code builds a URL like: `redis://:<PASS>@host:port`. For Edge-only deployments, JWT sessions work without Redis; Redis is useful for account persistence in Node runtimes.

---

## Local Development

> **Package manager**: This project declares a `packageManager` in `package.json`. If you see errors using `pnpm`, use **npm** (as configured).

```bash
# From repo root
cd src/osss-web

# Install dependencies
npm install

# Run the dev server
npm run dev
# → http://localhost:3000

# Type-check, lint, build
npm run typecheck
npm run lint
npm run build
npm start   # run the production build locally
```

If you proxy a backend during development, confirm `next.config.js` rewrites (e.g., `/api/osss/:path* → http://localhost:8081/:path*`). Avoid a catch‑all `/api/:path*` rewrite to prevent clashes with Next’s own API routes.

---

## Coding Conventions

- **TypeScript**: Prefer explicit types at module boundaries; use `import type` for type-only imports.
- **Components**: Co-locate feature-specific components with their routes; place shared UI in `components/`.
- **Lib utilities**: Keep non-UI logic in `lib/` (auth, env, API client, tokens).
- **Path aliases**: Use `@/lib/...`, `@/components/...`, `@/types/...` for clarity (see `tsconfig.json`).
- **Styling**: Tailwind/shadcn-ui/Radix (if configured in your project) — keep components accessible (ARIA).

---

## Testing (suggested)

- **Unit**: React Testing Library + Vitest/Jest (depending on project setup).  
- **E2E**: Playwright/Cypress.  
- **Middleware/Edge**: Use `@edge-runtime/jest` or compatible mocks for `Request`/`Response`.

> Ensure auth-dependent tests provide stubbed sessions/tokens; avoid hitting live IdP in CI.

---

## Build & Deploy

- **Build**: `npm run build` produces a `.next` output.  
- **Runtime**: Edge + Node depending on route; functions requiring Redis or other Node-only clients must run on Node.  
- **Output tracing**: `next.config.js` may set `outputFileTracingRoot` for monorepo-friendly server bundling. Adjust if you move directories.

---

## Troubleshooting

- **“This project is configured to use npm …”**: Use `npm` since `packageManager` is set in `package.json`.
- **`/api/auth/session` 500**: Verify env vars, issuer is an absolute URL, and `providers` array is defined.
- **Redis connection errors**: Validate `REDIS_URL`/`REDIS_PASSWORD`; test with `redis-cli -a` locally.
- **Edge vs Node**: Don’t import Node-only modules in Edge code paths (middleware, some RSC).

---

## Related Docs

- [`app/` directory](../app.md) – App Router overview  
- [`app/api/auth/`](../api/auth/README.md) – NextAuth routes & handlers  
- [`components/`](../components/README.components.md) – Shared UI components  
- [`lib/`](../lib/README.lib.md) – Utilities and integrations  
- [`types/`](../types/README.types.md) – Shared TS types

---

## Links

- Repo: https://github.com/rubelw/OSSS/tree/e7c3fcf69557527d1c09b9d47096fac63c0af246/src/osss-web
