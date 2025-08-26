// src/components/SignOutButton.tsx
'use client'
import { signOut } from 'next-auth/react'

export function SignOutButton() {
  return (
    <button
      className="btn"
      onClick={() =>
        signOut({ redirect: true, callbackUrl: "/api/keycloak/logout" })
      }
    >
      Sign Out
    </button>
  )
}
