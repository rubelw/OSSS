# `components/`

This directory contains **shared UI components** for the OSSS Web application.  
Components here are meant to be **reusable, composable building blocks** that form the user interface
across multiple pages and features.

---

## 📌 Purpose

- **Centralize UI elements** (buttons, cards, layouts, navigation bars, etc.) so they are implemented once and reused consistently.
- **Encapsulate design system patterns** (colors, typography, spacing, accessibility attributes) to maintain a unified look and feel.
- **Reduce duplication** across feature modules by housing generic UI parts here.
- **Provide wrappers/adapters** for third-party component libraries (e.g., shadcn/ui, Tailwind, Radix).

---

## 📂 Structure (typical)

```
components/
├── ui/               # Low-level primitives (Button, Input, Card, Modal)
├── layout/           # Layout helpers (Sidebar, Topbar, PageShell)
├── forms/            # Form-related inputs, validation wrappers
├── auth/             # Authentication-related widgets (AuthButtons, SignInForm)
└── charts/           # Data visualization helpers
```

> Your exact structure may differ; update this README as the component library evolves.

---

## 🔑 How It Works

- **Colocation**: Feature-specific components usually live with their feature. Only **generic, reusable** components belong here.
- **Styling**: Most components are styled with **Tailwind CSS** and may compose utilities from shadcn/ui.
- **Client vs Server**: Many components are `"use client"` because they rely on interactivity (hooks, state). Pure presentational components can remain server-compatible.
- **Accessibility**: Favor semantic HTML + ARIA attributes. Reuse well-tested primitives (Radix, shadcn/ui) where possible.

---

## 🚦 Developer Notes

- **When to add here**: If a component will be reused across **multiple routes/features**, add it to `components/`.
- **When NOT to add here**: If it is highly feature-specific (e.g., only used inside `/finance`), colocate it with that feature instead.
- **Imports**: Use path aliases (`@/components/...`) for clarity and to avoid long relative paths.
- **Testing**: Unit test critical UI logic (forms, conditional rendering). Snapshot test purely visual components.

---

## ✅ Summary

The `components/` directory provides the **UI toolkit** for OSSS Web.  
It ensures that buttons, forms, layouts, and navigation elements remain **consistent, accessible, and reusable** across the entire application.

By centralizing common UI, we:  

- Reduce duplication  
- Improve maintainability  
- Enforce design consistency  
- Speed up feature development  
