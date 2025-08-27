/**
 * OSSS Web — App Providers (Client Component)
 * Purpose: Host top-level React context providers for the App Router.
 * Key provider: next-auth's SessionProvider — makes `useSession()` available to all children.
 * Runtime: Client-only (`"use client"`) because SessionProvider relies on client features.
 * Props: { children, session } — session can be pre-fetched on the server and hydrated here.
 * A11y/Perf: Keep provider tree shallow; avoid re-render storms by memoizing heavy contexts.
 */
// src/osss-web/app/providers.tsx
// This directive marks the file as a Client Component so hooks like `useSession()` work.

"use client";

import { SessionProvider } from "next-auth/react";
import type { Session } from "next-auth";

/**
 * Providers({ children, session })
 * • Wraps the application with context providers needed across routes.
 * • `SessionProvider` hydrates the session received from the server (if any) so that
 *   client components can call `useSession()` without an extra round-trip.
 * • Any additional global providers (Theme, i18n, QueryClient) would be added here.
 */
export default function Providers({
  children,
  session,
}: {
  children: React.ReactNode;
  session: Session | null;
}) {
  return <SessionProvider session={session}>{children}</SessionProvider>;
}
