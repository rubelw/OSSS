/**
 * =================================================================================================
 * OSSS Web — Redis-backed Unstorage Adapter Helpers
 * -------------------------------------------------------------------------------------------------
 * Purpose: Thin wrappers/utilities to wire `@auth/unstorage-adapter` with a Redis storage backend.
 *  Clarifies keyspace conventions, TTLs, and serialization; avoids deep imports of .d.ts.
 *  Notes operational characteristics (lazyConnect, retries, failure modes).
 *
 * General guidance
 *  • This module is server-only unless otherwise stated; do not import into client components.
 *  • Prefer explicit, validated environment access (no silent fallbacks).
 *  • Keep exported surface minimal and stable; this module is a building block for the app.
 * =================================================================================================
 */
// lib/redis-adapter.ts
import type { Adapter, AdapterUser, AdapterAccount, AdapterSession } from "next-auth/adapters";
import type Redis from "ioredis";

type StoredSession = { userId: string; expires: string }; // ISO in Redis

export function RedisAdapter(redis: Redis): Adapter {
  // ----- keys
  const kUser = (id: string) => `user:${id}`;
  const kEmail = (email: string) => `user:email:${email.toLowerCase()}`;
  const kAccount = (provider: string, providerAccountId: string) =>
    `account:${provider}:${providerAccountId}`;
  const kSession = (token: string) => `session:${token}`;

  // ----- helpers
  const msUntil = (d: Date) => Math.max(0, d.getTime() - Date.now());

  const getUserById = async (id: string): Promise<AdapterUser | null> => {
    const raw = await redis.get(kUser(id));
    return raw ? (JSON.parse(raw) as AdapterUser) : null;
  };

  const saveUser = async (user: AdapterUser) => {
    await redis.set(kUser(user.id), JSON.stringify(user));
    if (user.email) await redis.set(kEmail(user.email), user.id);
  };

  return {
    // ===== Users =====
    createUser: async (user) => {
      // `user` has id already in v5
      await saveUser(user as AdapterUser);
      return user as AdapterUser;
    },

    getUser: getUserById,

    getUserByEmail: async (email) => {
      const id = await redis.get(kEmail(email));
      return id ? await getUserById(id) : null;
    },

    getUserByAccount: async ({ provider, providerAccountId }) => {
      const userId = await redis.get(kAccount(provider, providerAccountId));
      return userId ? await getUserById(userId) : null;
    },

    updateUser: async (user) => {
      const existing = await getUserById(user.id);
      const merged = { ...(existing ?? {}), ...user } as AdapterUser;
      await saveUser(merged);
      return merged;
    },

    // ===== Accounts =====
    linkAccount: async (account) => {
      // Keep minimal mapping for lookup
      await redis.set(kAccount(account.provider, account.providerAccountId), account.userId);
      // Optionally also store account data:
      await redis.set(`${kAccount(account.provider, account.providerAccountId)}:data`, JSON.stringify(account));
      return account as AdapterAccount;
    },

    unlinkAccount: async ({ provider, providerAccountId }) => {
      await redis.del(kAccount(provider, providerAccountId));
    },

    // ===== Sessions (database strategy) =====
    createSession: async (session) => {
      // session.expires is a Date coming from Auth.js — KEEP IT a Date in the return value
      const toStore: StoredSession = {
        userId: session.userId,
        expires: session.expires.toISOString(),
      };
      await redis.set(kSession(session.sessionToken), JSON.stringify(toStore), "PX", msUntil(session.expires));
      // Return with Date
      return {
        sessionToken: session.sessionToken,
        userId: session.userId,
        expires: new Date(session.expires),
      } satisfies AdapterSession;
    },

    getSessionAndUser: async (sessionToken) => {
      const raw = await redis.get(kSession(sessionToken));
      if (!raw) return null;
      const stored = JSON.parse(raw) as StoredSession;
      const user = await getUserById(stored.userId);
      if (!user) return null;

      return {
        session: {
          sessionToken,
          userId: stored.userId,
          expires: new Date(stored.expires), // <- Date
        },
        user,
      };
    },

    updateSession: async (partial) => {
      const key = kSession(partial.sessionToken);
      const raw = await redis.get(key);
      if (!raw) return null;

      const prev = JSON.parse(raw) as StoredSession;
      const nextExpires = partial.expires ? new Date(partial.expires) : new Date(prev.expires);

      const next: StoredSession = {
        userId: prev.userId,
        expires: nextExpires.toISOString(),
      };

      await redis.set(key, JSON.stringify(next), "PX", msUntil(nextExpires));

      return {
        sessionToken: partial.sessionToken,
        userId: prev.userId,
        expires: nextExpires, // <- Date
      };
    },

    deleteSession: async (sessionToken) => {
      await redis.del(kSession(sessionToken));
    },

    // ===== Verification tokens (not needed for OIDC, but stub safely) =====
    createVerificationToken: async (token) => token,
    useVerificationToken: async () => null,
  };
}

/**
 * -------------------------------------------------------------------------------------------------
 * Operational notes
 *  • Observability: log request ids and lightweight outcome metrics; never log raw tokens.
 *  • Security: ensure all outbound calls to Keycloak/backends use HTTPS and strict TLS.
 *  • Resilience: handle transient failures with jittered backoff; fail fast on configuration errors.
 *  • Testing: mock network calls (fetch) and time (Date.now) for deterministic token/expiry tests.
 * -------------------------------------------------------------------------------------------------
 */
