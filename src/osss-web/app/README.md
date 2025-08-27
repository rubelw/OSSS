# `app/`

This directory contains the **App Router entrypoint** for the OSSS Web application, built on
Next.js 13+ with the new App Router paradigm. It defines the **routing, layouts, and server/client
components** that make up the frontend of OSSS Web.

---

## 📌 Purpose

- **Define application routes** using the file-system router (`app/**/page.tsx`).
- **Establish layouts** (`layout.tsx`) that wrap groups of routes with shared UI (header, sidebar).
- **Host API route handlers** (`app/api/**/route.ts`) which run on the server (Node/Edge).
- **Provide colocation of UI, logic, and data fetching** at the route level.

---

## 📂 Structure (typical)

```
app/
├── layout.tsx              # Root layout (applies to all routes)
├── page.tsx                # Root index page ("/")
├── api/                    # Next.js server API routes (Auth, Keycloak, OSSS backend proxy)
│   ├── auth/               # Authentication endpoints (NextAuth handlers)
│   ├── keycloak/           # Direct Keycloak API integrations
│   └── osss/               # Proxies to OSSS FastAPI backend
├── administration/         # Feature route: admin dashboards/settings
├── finance/                # Feature route: finance pages
├── human-resources/        # Feature route: HR pages
├── parent-communications/  # Feature route: parent comms pages
├── school-board/           # Feature route: board of education pages
├── facilities/             # Feature route: facilities management pages
├── transportation/         # Feature route: transportation module
└── (other features)...
```

> Each folder under `app/` can contain its own `page.tsx`, `layout.tsx`, `loading.tsx`, `error.tsx`,
> and API route files (`route.ts`). This keeps concerns colocated per feature/route.

---

## 🔑 How It Works

- **File-based Routing**:  
  - `page.tsx` → renders a page at its path.  
  - `layout.tsx` → persistent wrapper (navbars, sidebars).  
  - `route.ts` (in `api/`) → runs as a serverless function or edge handler.  

- **Server & Client Components**:  
  - By default, components in `app/` are **server components**.  
  - Add `"use client"` at the top of a file to opt into client interactivity (hooks, state).  

- **API Routes**:  
  - Lives under `app/api/`. These run only on the server and can use secrets or connect to Keycloak/Redis/OSSS backend.  

---

## 🚦 Developer Notes

- **When to add here**:  
  - New pages, features, or API routes.  
  - Shared layouts or loading states.  

- **When NOT to add here**:  
  - Reusable UI components → put in `components/`.  
  - Shared libraries/helpers → put in `lib/`.  
  - Type definitions → put in `types/`.  

- **Performance**:  
  - Prefer server components when possible (lighter bundles).  
  - Use client components only when interactivity is needed.  

- **Error Handling**:  
  - Use `error.tsx` in route segments for scoped error boundaries.  
  - Use `loading.tsx` for built-in suspense/loading states.  

---

## ✅ Summary

The `app/` directory is the **core of OSSS Web’s frontend architecture**.  
It defines all pages, layouts, and API endpoints using Next.js App Router conventions.  

By colocating UI and server logic per route, OSSS Web achieves:  

- Clear separation of concerns.  
- Easier feature development.  
- Better performance (server components by default).  
- Stronger alignment between backend APIs and frontend routes.  
