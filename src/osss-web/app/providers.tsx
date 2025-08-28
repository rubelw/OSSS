// src/osss-web/app/providers.tsx
"use client";

import { SessionProvider } from "next-auth/react";
import type { Session } from "next-auth";

export default function Providers({
  children,
  session,
}: {
  children: React.ReactNode;
  session?: Session | null;   // ✅ optional
}) {
  return <SessionProvider session={session}>{children}</SessionProvider>;
}
