"use client";
import { signIn, signOut, useSession } from "next-auth/react";

export function AuthButtons() {
  const { status } = useSession();
  const loggedIn = status === "authenticated";

  return loggedIn ? (
    <button onClick={() => signOut()}>Sign out</button>
  ) : (
    <button onClick={() => signIn("keycloak", { callbackUrl: "/" })}>
      Sign in
    </button>
  );
}