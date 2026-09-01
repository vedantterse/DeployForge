/**
 * Thin fetch wrapper around the DeployForge backend.
 *
 * Every request goes through here so that the base URL lives in one place and
 * the JWT (added in Task 2) is attached consistently.
 */

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Read the stored JWT directly to avoid a circular import with lib/auth. */
function authHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = window.localStorage.getItem("deployforge_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeader(),
      ...(options.headers ?? {}),
    },
  });

  // 204 No Content has no body to parse.
  const body = res.status === 204 ? null : await res.json().catch(() => null);

  if (!res.ok) {
    const message =
      (body as { error?: { message?: string } } | null)?.error?.message ??
      formatDetail((body as { detail?: unknown } | null)?.detail) ??
      `Request failed with status ${res.status}`;
    throw new ApiError(message, res.status);
  }

  return body as T;
}

/** FastAPI validation errors arrive as a list of objects, not a string. */
function formatDetail(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((d) => (d as { msg?: string })?.msg)
      .filter(Boolean);
    if (messages.length > 0) return messages.join("; ");
  }
  return null;
}

export type HealthResponse = {
  status: string;
  service: string;
  version: string;
  environment: string;
  database: string;
  detail: string | null;
};

export function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/health");
}
