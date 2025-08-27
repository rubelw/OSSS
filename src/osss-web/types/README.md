# `types/`

This directory contains **shared TypeScript type definitions** for the OSSS Web application.  
It exists to centralize interfaces, enums, and utility types that are reused across components, API
routes, and libraries, ensuring **type safety and consistency** throughout the codebase.

---

## 📌 Purpose

- **Define global contracts** (e.g., `User`, `Organization`, `Session` extensions) used across the app.
- **Keep feature-agnostic types** in one place instead of duplicating them across modules.
- **Augment third-party libraries** with OSSS-specific type extensions (e.g., extending `next-auth` Session).
- **Improve maintainability** by providing a single source of truth for domain and utility types.

---

## 📂 Structure (typical)

```
types/
├── next-auth.d.ts    # Module augmentation for NextAuth Session/User types
├── api.ts            # Shared API response/request shapes
├── models.ts         # OSSS domain models (Goals, Plans, Periods, Payments, etc.)
├── auth.ts           # Auth-related types (tokens, roles, groups)
└── index.ts          # Barrel export to re-export shared types
```

> The actual contents may differ. Update this README as your domain model grows.

---

## 🔑 How It Works

- **Module Augmentation**:  
  - `next-auth.d.ts` augments built-in NextAuth types so that `session.user` includes `id`, `roles`,
    or custom claims like `district_id`.
- **Shared Contracts**:  
  - Types defined here (e.g., `ApiResponse<T>`, `Paginated<T>`) are imported across `lib/`, `components/`, and `app/api/` routes.
- **Domain Modeling**:  
  - Types like `Goal`, `Plan`, or `Payment` mirror backend Pydantic models, ensuring **frontend↔backend alignment**.
- **Type-Only Imports**:  
  - Use `import type { ... } from "@/types"` to keep builds fast and avoid runtime overhead.

---

## 🚦 Developer Notes

- **When to add here**:  
  - If a type/interface is reused across multiple features or layers.  
  - If you are extending/augmenting a third-party library’s types.  

- **When NOT to add here**:  
  - If a type is specific to a single component/route and not reused elsewhere — colocate it instead.  

- **Consistency**:  
  - Ensure types here stay in sync with backend schemas (FastAPI/Pydantic). Consider codegen or schema syncing if drift is a risk.

---

## ✅ Summary

The `types/` directory provides a **single source of truth for TypeScript type definitions**.  
It ensures OSSS Web maintains:

- Consistent contracts across frontend and backend.  
- Correctly typed sessions and auth flows.  
- Clean, maintainable, and DRY type definitions.  

By centralizing types, developers avoid duplication and reduce type errors across the codebase.
