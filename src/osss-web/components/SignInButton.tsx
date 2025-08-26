// src/components/SignInButton.tsx
'use client';

import { signIn } from 'next-auth/react';

export function SignInButton({ force = false }: { force?: boolean }) {
  return (
    <button
      className="btn"
      onClick={() =>
        // 2nd arg = options, 3rd arg = authorizationParams
        force
          ? signIn('keycloak', { redirect: true, callbackUrl: '/' }, { prompt: 'login' })
          : signIn('keycloak', { redirect: true, callbackUrl: '/' })
      }
    >
      {force ? 'Sign In (force)' : 'Sign In'}
    </button>
  );
}