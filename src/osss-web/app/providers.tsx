// src/osss-web/app/providers.tsx
"use client";

import { SessionProvider } from "next-auth/react";

export default function Providers({
  children,
  session,
}: {
  children: React.ReactNode;
  session?: any;
}) {
  // With a server-provided `session`, SessionProvider won't fetch /api/auth/session
  return <SessionProvider session={session}>{children}</SessionProvider>;
}
