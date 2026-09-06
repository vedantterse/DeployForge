/**
 * Apps — the things a student owns.
 *
 * An app is a repository target they connected. A deployment is one attempt to
 * build and run it. Rebuilding gives an app another deployment, not the
 * student another app, so the list they see is a list of apps and the history
 * lives inside each one.
 *
 * Lifecycle actions still belong to `lib/deployments.ts`: an app has no
 * lifecycle of its own, only the lifecycle of whichever deployment is current.
 */

import { apiFetch } from "@/lib/api";
import type { DetectedType, Deployment } from "@/lib/deployments";

export type App = {
  id: string;
  name: string;
  full_name: string;
  target_label: string;
  deploy_path: string | null;
  service_paths: string[] | null;
  is_multi_service: boolean;
  detected_type: DetectedType | null;
  detected_framework: string | null;
  created_at: string;
  updated_at: string;

  /**
   * The deployment the app's URL points at: the running one, or the most
   * recent attempt when nothing is up. Null only for an app connected but
   * never built.
   */
  current: Deployment | null;
  deployment_count: number;
  last_deployed_at: string | null;
};

export type AppDetail = App & {
  /** Every deployment of this app, newest first. */
  deployments: Deployment[];
};

export function listApps(): Promise<App[]> {
  return apiFetch<App[]>("/apps");
}

export function getApp(id: string): Promise<AppDetail> {
  return apiFetch<AppDetail>(`/apps/${id}`);
}

/** Remove the app entirely: its containers, its history, and the connection. */
export function deleteApp(id: string): Promise<null> {
  return apiFetch<null>(`/apps/${id}`, { method: "DELETE" });
}

/* -------------------------------------------------------------------------
 * Reading an app's state
 * ---------------------------------------------------------------------- */

/**
 * What the app is doing right now, in one word.
 *
 * An app with no deployment has been connected but never built — "Not
 * deployed" rather than any status, because none of the deployment vocabulary
 * applies to something that has never been one.
 */
export function appState(app: App): {
  label: string;
  tone: "ok" | "warn" | "danger" | "info" | "neutral";
} {
  if (!app.current) return { label: "Not deployed", tone: "neutral" };
  switch (app.current.status) {
    case "running":
    case "live":
      return { label: "Running", tone: "ok" };
    case "queued":
    case "building":
    case "pushing":
      return { label: "Building", tone: "info" };
    case "starting":
      return { label: "Starting", tone: "info" };
    case "built":
      return { label: "Built, not started", tone: "info" };
    case "stopped":
      return { label: "Stopped", tone: "warn" };
    case "failed":
      return { label: "Build failed", tone: "danger" };
    case "analyzed":
      return { label: "Not deployed", tone: "neutral" };
    default:
      return { label: app.current.status, tone: "neutral" };
  }
}

/** Whether anything about this app is still in motion, so it is worth polling. */
export function appIsBusy(app: App): boolean {
  if (!app.current) return false;
  return ["queued", "building", "pushing", "starting"].includes(
    app.current.status,
  );
}
