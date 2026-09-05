/**
 * Admin-only calls: who is on the platform, what they are running, and the
 * levers for controlling it.
 */

import { apiFetch } from "@/lib/api";
import type { Deployment } from "@/lib/deployments";
import type { User, UserRole } from "@/lib/auth";

export type UserWithDeployments = {
  id: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  deployment_count: number;
  repository_count: number;
  running_count: number;
  max_deployments: number;
  can_deploy: boolean;
  deploy_block_reason: string | null;
  github_username: string | null;
  deployments: Deployment[];
};

export type PlatformAnalytics = {
  users: number;
  admins: number;
  active_users: number;
  blocked_users: number;
  github_connections: number;
  repositories: number;
  deployments: number;
  running: number;
  stopped: number;
  failed: number;
  suspended: number;
  by_method: Record<string, number>;
  by_framework: Record<string, number>;
  by_status: Record<string, number>;
  daily: { date: string; count: number }[];
  top_users: { email: string; deployments: number; running: number }[];
  build_seconds_median: number | null;
  build_seconds_max: number | null;
  success_rate: number | null;
};

export type PlatformStatus = {
  docker: boolean;
  registry: boolean;
  router: boolean;
  buildpacks: boolean;
  detail: Record<string, string>;
};

export function getOverview(): Promise<UserWithDeployments[]> {
  return apiFetch<UserWithDeployments[]>("/admin/overview");
}

export function getAnalytics(): Promise<PlatformAnalytics> {
  return apiFetch<PlatformAnalytics>("/admin/analytics");
}

export function getPlatformStatus(): Promise<PlatformStatus> {
  return apiFetch<PlatformStatus>("/admin/platform/status");
}

export function getAllDeployments(): Promise<Deployment[]> {
  return apiFetch<Deployment[]>("/admin/deployments");
}

export function suspendDeployment(
  id: string,
  reason?: string,
): Promise<Deployment> {
  return apiFetch<Deployment>(`/admin/deployments/${id}/suspend`, {
    method: "POST",
    body: JSON.stringify({ reason: reason ?? null }),
  });
}

export function resumeDeployment(id: string): Promise<Deployment> {
  return apiFetch<Deployment>(`/admin/deployments/${id}/resume`, {
    method: "POST",
  });
}

export function adminDeleteDeployment(id: string): Promise<null> {
  return apiFetch<null>(`/admin/deployments/${id}`, { method: "DELETE" });
}

export type UserChanges = {
  is_active?: boolean;
  max_deployments?: number;
  role?: UserRole;
  can_deploy?: boolean;
  deploy_block_reason?: string | null;
};

export function updateUser(id: string, changes: UserChanges): Promise<User> {
  return apiFetch<User>(`/admin/users/${id}`, {
    method: "PATCH",
    body: JSON.stringify(changes),
  });
}

/** "2m 04s" — build durations read better than a raw second count. */
export function formatSeconds(seconds: number | null): string {
  if (seconds === null || Number.isNaN(seconds)) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${String(Math.round(seconds % 60)).padStart(2, "0")}s`;
}
