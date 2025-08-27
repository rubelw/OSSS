# `app/api/auth/`

This directory contains the **authentication API routes** for the OSSS web application. It wires together **NextAuth (Auth.js v5)** with **Keycloak** and optional **Redis-based persistence** so that all frontend routes and API calls can share a unified, secure authentication layer.

---

## 📌 Purpose

- **Expose authentication endpoints** (`/api/auth/*`) that handle login, logout, callbacks, session lookups, and token refreshes.
- **Bridge Keycloak with Next.js** by using the [NextAuth.js](https://authjs.dev) library as a middleware/adapter layer.
- **Support session management** for both client components (`useSession()`) and server components (`auth()`).
- **Allow Redis-backed persistence** for accounts and users during development/Node runtimes, while keeping **JWT-based sessions** for edge runtimes.

---

## 📂 Structure

```
app/api/auth/
├── [...nextauth]/route.ts   # Primary entrypoint for NextAuth handlers (GET/POST)
├── callback/page.tsx        # (Optional) OAuth2/OIDC callback UI or redirect handler
└── edge.ts                  # Edge-safe helpers (auth() for middleware, minimal identity extraction)
```

- **`[...nextauth]/route.ts`**  
  - Implements the NextAuth `handlers` for both `GET` and `POST`.  
  - All authentication flows (sign-in, sign-out, session fetch, callback) are routed through here.  
  - Exports are imported from `lib/auth.ts` where the actual NextAuth configuration lives.

- **`callback/page.tsx`** (optional UI)  
  - Handles redirects or provides a debug page for OAuth callback responses.

- **`auth-edge.ts`** (if present)  
  - Provides **Edge Runtime–safe** versions of `auth()` helpers for use in `middleware.ts`.  
  - Avoids Node-only modules (like Redis drivers).

---

## 🔑 How It Works

1. **Configuration (`lib/auth.ts`)**  
   - Sets up NextAuth with:
     - **Keycloak provider** (with PKCE enabled and a compact user profile mapper).
     - **Redis + unstorage adapter** for account persistence (server-only).
     - **JWT-based sessions** (`session.strategy = "jwt"`) so that most routes don’t depend on Redis.

2. **Handlers (`[...nextauth]/route.ts`)**  
   - Exports the `GET` and `POST` handlers provided by NextAuth.
   - Automatically responds to:
     - `/api/auth/signin`
     - `/api/auth/signout`
     - `/api/auth/callback/*`
     - `/api/auth/session`
     - `/api/auth/providers`

3. **Middleware Integration**  
   - `middleware.ts` can call `auth()` (or an Edge-safe equivalent) to gate routes by session status.
   - Example: redirect unauthenticated users to `/login`.

---

## 🚦 Developer Notes

- **Environment variables required**:
  - `KEYCLOAK_ISSUER` – Keycloak realm issuer URL.
  - `WEB_KEYCLOAK_CLIENT_ID` / `WEB_KEYCLOAK_CLIENT_SECRET`.
  - `NEXTAUTH_URL` / `NEXTAUTH_SECRET`.
  - Optional: `REDIS_URL`, `REDIS_PASSWORD`.

- **Edge vs Node runtimes**:
  - Edge functions (middleware, app router RSC) cannot use Redis clients. Use JWT-only sessions there.
  - Node runtime (API routes, server actions) can access Redis via `unstorage`.

- **Extensibility**:
  - To add another identity provider, extend the `providers` array in `lib/auth.ts`.
  - To add RBAC/ABAC claims, enrich the JWT/session callbacks in `lib/auth.ts`.

---

## ✅ Summary

The `app/api/auth/` path is the **heart of OSSS authentication**.  
It provides a secure, standards-based, and extensible foundation for:

- Sign-in/out flows.  
- Session validation across client and server.  
- Integration with Keycloak (OIDC).  
- Optional Redis-backed persistence.  

Every request that touches user identity flows through here.  
