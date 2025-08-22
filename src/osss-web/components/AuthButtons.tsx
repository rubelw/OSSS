"use client";

import { useSession, signIn, signOut } from "next-auth/react";

export function AuthButtons() {
  const { data: session, status } = useSession();

  if (status === "loading") return <button disabled>Checking session…</button>;

  return session ? (
    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
      <span>Signed in</span>
      <button onClick={() => signOut()}>Sign out</button>
    </div>
  ) : (
    <button onClick={() => signIn("keycloak")}>Sign in with Keycloak</button>
  );
}
