/**
 * Token storage and the current-user helper.
 *
 * The JWT lives in localStorage. That is the pragmatic choice for a
 * token-in-header API like this one; the trade-off is that it is readable by
 * any script on the page, so an httpOnly cookie would be the hardening step if
 * this ever faces the public internet.
 *
 * Client-side redirects based on these helpers are UX only. Every route is
 * enforced on the backend by get_current_user / require_admin.
 */

import { apiFetch } from "@/lib/api";

const TOKEN_KEY = "deployforge_token";

export type UserRole = "admin" | "user";

export type User = {
  id: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  max_deployments?: number;
  /** False when an admin has revoked this account's permission to deploy. */
  can_deploy?: boolean;
  deploy_block_reason?: string | null;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  expires_in_minutes: number;
  user: User;
};

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
}

export function login(email: string, password: string): Promise<TokenResponse> {
  return apiFetch<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function signup(email: string, password: string): Promise<TokenResponse> {
  return apiFetch<TokenResponse>("/auth/signup", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

/** The logged-in user, or null if there is no usable token. */
export async function getCurrentUser(): Promise<User | null> {
  if (!getToken()) return null;
  try {
    return await apiFetch<User>("/auth/me");
  } catch {
    clearToken(); // expired or invalid — don't keep a dead token around
    return null;
  }
}
