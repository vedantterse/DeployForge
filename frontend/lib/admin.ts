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
  github_username: string | null;
  deployments: Deployment[];
};

export type PlatformStats = {
  users: number;
  admins: number;
  github_connections: number;
  repositories: number;
  deployments: number;
  running: number;
  failed: number;
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

export function getStats(): Promise<PlatformStats> {
  return apiFetch<PlatformStats>("/admin/stats");
}

export function getPlatformStatus(): Promise<PlatformStatus> {
  return apiFetch<PlatformStatus>("/admin/platform/status");
}

export function getAllDeployments(): Promise<Deployment[]> {
  return apiFetch<Deployment[]>("/admin/deployments");
}

export function suspendDeployment(id: string): Promise<Deployment> {
  return apiFetch<Deployment>(`/admin/deployments/${id}/suspend`, {
    method: "POST",
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

export function updateUser(
  id: string,
  changes: { is_active?: boolean; max_deployments?: number; role?: UserRole },
): Promise<User> {
  return apiFetch<User>(`/admin/users/${id}`, {
    method: "PATCH",
    body: JSON.stringify(changes),
  });
}
