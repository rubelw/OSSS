import { keycloak } from "../keycloak";

const base = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (keycloak.authenticated) {
    await keycloak.updateToken(30).catch(() => keycloak.login());
  }
  const headers = new Headers(init.headers || {});
  headers.set("Content-Type", "application/json");
  if (keycloak.token) headers.set("Authorization", `Bearer ${keycloak.token}`);
  const res = await fetch(`${base}${path}`, { ...init, headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<T>;
}
