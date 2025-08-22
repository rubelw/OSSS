// Simple localStorage-backed token store.
// In a real app you might prefer httpOnly cookies set by the backend.
export type Tokens = {
  access_token: string;
  refresh_token?: string;
  expires_in?: number;
  token_type?: string;
};

const KEY = "osss.tokens";

export function saveTokens(t: Tokens) {
  if (!t?.access_token) return;
  localStorage.setItem(KEY, JSON.stringify(t));
}

export function loadTokens(): Tokens | null {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Tokens) : null;
  } catch {
    return null;
  }
}

export function clearTokens() {
  localStorage.removeItem(KEY);
}

export function isAuthenticated() {
  return !!loadTokens()?.access_token;
}

export function authHeader(): HeadersInit {
  const tok = loadTokens();
  return tok?.access_token ? { Authorization: `Bearer ${tok.access_token}` } : {};
}
