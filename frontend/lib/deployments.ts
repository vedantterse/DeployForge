/**
 * Deployment types and the calls that act on them.
 *
 * The status vocabulary is duplicated from the backend enum on purpose: it is
 * the contract between the two, and having it written down here is what lets
 * the UI decide what a status *means* — is it moving, can it be started, is it
 * worth polling — in one place instead of scattering string comparisons
 * through the components.
 */

import { apiFetch } from "@/lib/api";

export type DeploymentStatus =
  | "analyzed"
  | "queued"
  | "building"
  | "pushing"
  | "built"
  | "starting"
  | "running"
  | "live"
  | "stopped"
  | "failed";

export type BuildMethod = "docker" | "buildpack" | "compose";
export type DetectedType = "docker" | "framework" | "unknown";

export type Deployment = {
  id: string;
  status: DeploymentStatus;
  build_method: BuildMethod | null;
  commit_sha: string | null;
  created_at: string;
  updated_at: string;

  image_ref: string | null;
  build_started_at: string | null;
  build_finished_at: string | null;
  error_message: string | null;
  has_logs: boolean;

  url: string | null;
  subdomain: string | null;
  app_port: number | null;
  container_name: string | null;
  runtime_started_at: string | null;
  runtime_stopped_at: string | null;
  suspended_by_admin: boolean;
  suspension_reason: string | null;
  compose_project: string | null;
  compose_services: string[] | null;
  /** Which service receives public traffic. Recorded, not inferred. */
  compose_web_service: string | null;

  repository_id: string;
  full_name: string;
  deploy_path: string | null;
  target_label: string;
  detected_type: DetectedType | null;
  detected_framework: string | null;

  user_id?: string | null;
  user_email?: string | null;
};

export type DeploymentEvent = {
  id: string;
  stage: string;
  level: "info" | "success" | "warning" | "error";
  message: string;
  actor: string | null;
  created_at: string;
};

export type BuildLogs = {
  deployment_id: string;
  status: DeploymentStatus;
  logs: string;
  truncated: boolean;
};

export type RuntimeLogs = {
  deployment_id: string;
  status: DeploymentStatus;
  logs: string;
  running: boolean;
};

/* -------------------------------------------------------------------------
 * Status semantics
 * ---------------------------------------------------------------------- */

/** A background task owns this deployment — show a spinner, keep polling. */
export const BUSY_STATUSES: DeploymentStatus[] = [
  "queued",
  "building",
  "pushing",
  "starting",
];

export function isBusy(status: DeploymentStatus): boolean {
  return BUSY_STATUSES.includes(status);
}

export function isRunning(status: DeploymentStatus): boolean {
  return status === "running" || status === "live";
}

/** Whether a "Start" action makes sense right now. */
export function canStart(d: Deployment): boolean {
  // A compose stack never has a single image; being prepared is what counts.
  const buildable = d.build_method === "compose" ? !!d.compose_project : !!d.image_ref;
  return (
    buildable && !isBusy(d.status) && !isRunning(d.status) && !d.suspended_by_admin
  );
}

export type StatusTone = "ok" | "warn" | "danger" | "info" | "neutral";

/** How a status should read: colour, label, and whether it is in motion. */
export function statusMeta(status: DeploymentStatus): {
  label: string;
  tone: StatusTone;
  moving: boolean;
} {
  switch (status) {
    case "running":
    case "live":
      return { label: "Running", tone: "ok", moving: false };
    case "built":
      return { label: "Built", tone: "info", moving: false };
    case "building":
      return { label: "Building", tone: "info", moving: true };
    case "pushing":
      return { label: "Storing image", tone: "info", moving: true };
    case "queued":
      return { label: "Queued", tone: "info", moving: true };
    case "starting":
      return { label: "Starting", tone: "info", moving: true };
    case "analyzed":
      return { label: "Ready to build", tone: "neutral", moving: false };
    case "stopped":
      return { label: "Stopped", tone: "warn", moving: false };
    case "failed":
      return { label: "Failed", tone: "danger", moving: false };
    default:
      return { label: status, tone: "neutral", moving: false };
  }
}

/** How a build method reads in the UI, and what it implies. */
export function methodMeta(d: Deployment): { label: string; detail: string } {
  switch (d.build_method) {
    case "compose":
      return {
        label: "Docker Compose",
        detail:
          d.compose_services && d.compose_services.length > 0
            ? `${d.compose_services.length} services: ${d.compose_services.join(", ")}`
            : "multi-service stack",
      };
    case "docker":
      return { label: "Dockerfile", detail: "built from your Dockerfile" };
    case "buildpack":
      return {
        label: "Buildpack",
        detail: d.detected_framework
          ? `detected as ${d.detected_framework}`
          : "framework detected automatically",
      };
    default:
      return { label: "Not built", detail: "no build has run yet" };
  }
}

/* -------------------------------------------------------------------------
 * Calls
 * ---------------------------------------------------------------------- */

export function listDeployments(): Promise<Deployment[]> {
  return apiFetch<Deployment[]>("/deployments");
}

export function getDeployment(id: string): Promise<Deployment> {
  return apiFetch<Deployment>(`/deployments/${id}`);
}

export function getBuildLogs(id: string): Promise<BuildLogs> {
  return apiFetch<BuildLogs>(`/deployments/${id}/logs`);
}

export function getRuntimeLogs(id: string): Promise<RuntimeLogs> {
  return apiFetch<RuntimeLogs>(`/deployments/${id}/runtime-logs`);
}

export function getEvents(id: string): Promise<DeploymentEvent[]> {
  return apiFetch<DeploymentEvent[]>(`/deployments/${id}/events`);
}

export function startDeployment(id: string): Promise<Deployment> {
  return apiFetch<Deployment>(`/deployments/${id}/start`, { method: "POST" });
}

export function stopDeployment(id: string): Promise<Deployment> {
  return apiFetch<Deployment>(`/deployments/${id}/stop`, { method: "POST" });
}

export function restartDeployment(id: string): Promise<Deployment> {
  return apiFetch<Deployment>(`/deployments/${id}/restart`, { method: "POST" });
}

export function deleteDeployment(id: string): Promise<null> {
  return apiFetch<null>(`/deployments/${id}`, { method: "DELETE" });
}

export function buildRepository(
  repoId: string,
): Promise<{ deployment_id: string; status: DeploymentStatus; target_label: string }> {
  return apiFetch(`/repos/${repoId}/build`, { method: "POST" });
}
