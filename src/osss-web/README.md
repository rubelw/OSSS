# OSSS Web (Next.js) — Frontend Application

The **OSSS Web** app is the primary frontend for **Open Source School Software (OSSS)**.

It is built with **Next.js (App Router)** and **TypeScript**, and integrates with **Auth.js (NextAuth)** and
**Keycloak** for authentication. The app is organized to keep routing, UI components, and integration logic
cleanly separated.

This directory corresponds to:

```text
src/osss-web
```

---

## ✨ Key Features

- **Next.js App Router**
  - `app/` directory with layouts, route segments, and server/client components.
  - API route handlers under `app/api/**`.

- **Authentication**
  - NextAuth (Auth.js) configured with a **Keycloak** provider.
  - JWT session strategy by default (Edge‑friendly).
  - Optional Redis‑backed adapter for account persistence in Node runtimes.

- **TypeScript‑first**
  - Strict typing with shared types under `types/`.
  - Utility modules under `lib/` for auth, environment, and API calls.

- **Reusable UI**
  - Shared components in `components/`.
  - Static assets in `public/` (favicons, images, etc.).

---

## 📁 Project Structure (high level)

```text
src/osss-web/
├── app/                         # App Router entry point (layouts, pages, API routes)
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
├── lib/                         # Non‑UI helpers and integrations
│   ├── auth.ts                  # NextAuth config (Node runtime)
│   ├── auth-edge.ts             # Edge‑safe auth helpers (no Node APIs)
│   ├── api-client.ts            # Typed fetch wrapper for backend calls
│   ├── kc-token.ts              # Keycloak token helpers
│   ├── redis.ts                 # Redis‑backed unstorage
│   ├── redis-adapter.ts         # Unstorage adapter wiring for NextAuth
│   └── env.ts                   # Centralized environment access/validation
├── types/                       # Shared TypeScript type definitions
├── public/                      # Static assets (favicon, images, docs)
├── providers.tsx                # App‑wide client providers (e.g., SessionProvider)
├── middleware.ts                # Edge middleware (auth gates, rewrites/redirects)
├── next.config.js               # Next.js configuration (rewrites, output tracing root)
├── package.json
└── tsconfig.json
```

> Exact filenames and route segments may vary; check the local tree for the authoritative structure.

---

## 🔐 Authentication Flow (Keycloak + NextAuth)

The web app uses **NextAuth** with a **Keycloak** provider:

1. **Provider configuration** is defined in `lib/auth.ts`:
   - Keycloak issuer URL
   - client ID / secret
   - profile mapping
2. **Session strategy** is typically JWT:
   - Edge‑compatible
   - Optional Redis adapter for account/user persistence on Node.
3. **Route handlers**:
   - `app/api/auth/[...nextauth]/route.ts` exports NextAuth `GET`/`POST` handlers.
4. **Client usage**:
   - Components use `useSession()` to read session state.
   - `signIn()` and `signOut()` trigger auth flows.
5. **Middleware**:
   - `middleware.ts` can protect routes or redirect based on session presence.

---

## 🌱 Environment Variables

Create an `.env.local` file inside `src/osss-web` (or at the repository root if your tooling is configured that way)
with values similar to:

```env
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=your-random-secret

KEYCLOAK_ISSUER=https://kc.example.com/realms/OSSS
WEB_KEYCLOAK_CLIENT_ID=osss-web
WEB_KEYCLOAK_CLIENT_SECRET=your-client-secret

REDIS_URL=redis://127.0.0.1:6379
REDIS_PASSWORD=your-redis-password
NODE_ENV=development
```

Notes:

- `NEXTAUTH_SECRET` can be generated via: `openssl rand -base64 32`.
- If Redis is password‑protected, the code typically constructs:
  `redis://:<PASSWORD>@host:port`.
- Edge‑only deployments can run with pure JWT sessions (no Redis).

---

## 🧑‍💻 Local Development

From the repository root:

```bash
cd src/osss-web

# Install dependencies
npm install

# Run the dev server
npm run dev
# → http://localhost:3000

# Type‑check, lint, build
npm run typecheck
npm run lint
npm run build

# Run the production build locally
npm start
```

> If the project declares a `packageManager` in `package.json` (e.g. `npm`),
> use that tool instead of `pnpm`/`yarn` to avoid lockfile conflicts.

If you proxy the backend during development, confirm `next.config.js` rewrites:

```js
// example
async rewrites() {
  return [
    {
      source: "/api/osss/:path*",
      destination: "http://localhost:8081/:path*",
    },
  ];
}
```

Avoid a catch‑all `/api/:path*` rewrite that could clash with Next’s own API routes.

---

## 🧩 Coding Conventions

- **TypeScript**
  - Prefer explicit types at module boundaries.
  - Use `import type` for type‑only imports to improve tree‑shaking.

- **Components**
  - Co‑locate feature‑specific components near their routes.
  - Use `components/` for shared UI patterns.

- **Utilities**
  - Put non‑UI logic in `lib/` (auth, env, API client, tokens).

- **Path aliases**
  - Commonly: `@/lib/...`, `@/components/...`, `@/types/...` (configured in `tsconfig.json`).

- **Styling**
  - Tailwind / shadcn‑ui / Radix UI (if configured).
  - Keep components accessible (proper ARIA attributes, semantic HTML).

---

## 🧪 Testing (Suggested)

You can wire up:

- **Unit tests** with React Testing Library and Vitest/Jest.
- **E2E tests** with Playwright or Cypress.
- **Middleware/Edge tests** using `@edge-runtime/jest` or similar to mock `Request`/`Response`.

> For auth‑dependent tests, provide stubbed sessions/tokens rather than calling a live IdP in CI.

---

## 🔗 Related OSSS Docs

If you’re using MkDocs for documentation, a page like `docs/frontend/overview.md` can link here and
describe how the web app fits into the broader OSSS architecture (backend, agents, orchestration, etc.).

---

## 🧾 License

This frontend is part of the **OSSS** project and is covered under the root project license
(see `LICENSE` at the repository root).

