/**
 * GitHub connect-account calls.
 *
 * Kept apart from lib/auth.ts on purpose: logging into DeployForge and
 * granting DeployForge access to your GitHub are two different things, and the
 * backend keeps them in separate modules too.
 */

import { apiFetch } from "@/lib/api";

export type ConnectionStatus = {
  connected: boolean;
  github_username: string | null;
  github_user_id: number | null;
  scopes: string | null;
  connected_at: string | null;
};

export function getConnectionStatus(): Promise<ConnectionStatus> {
  return apiFetch<ConnectionStatus>("/github/status");
}

/** Ask the backend where to send the browser to start the OAuth flow. */
export function getAuthorizeUrl(): Promise<{ authorize_url: string }> {
  return apiFetch<{ authorize_url: string }>("/github/connect");
}

export function disconnectGitHub(): Promise<unknown> {
  return apiFetch<unknown>("/github/disconnect", { method: "DELETE" });
}

export type GitHubRepo = {
  github_repo_id: number;
  name: string;
  full_name: string;
  description: string | null;
  language: string | null;
  default_branch: string;
  clone_url: string;
  html_url: string;
  private: boolean;
  fork: boolean;
  updated_at: string | null;
  /** When it appeared on this account — for a fork, when it was forked. */
  created_at: string | null;
  /** True when this account has already connected a target from this repo. */
  connected: boolean;
  /** Which targets are taken. "" means the whole repository. */
  connected_paths: string[];
  deployment_id: string | null;
  /** The latest deployment's real state, or null if it was never built. */
  deployment_status: string | null;
};

export type ConnectedRepo = {
  id: string;
  github_repo_id: number;
  name: string;
  full_name: string;
  default_branch: string;
  clone_url: string;
  deploy_path: string | null;
  detected_type: "docker" | "framework" | "unknown" | null;
  detected_framework: string | null;
  detection_meta: Record<string, unknown> | null;
  last_analyzed_at: string | null;
  created_at: string;
};

export type DetectedType = "docker" | "framework" | "unknown";

export type DetectionResult = {
  repository_id: string;
  deployment_id: string;
  full_name: string;
  deploy_path: string | null;
  /** Set when several directories were connected to run together. */
  service_paths: string[] | null;
  type: DetectedType;
  framework: string | null;
  compose: boolean;
  build_method: "docker" | "buildpack" | "compose" | null;
  evidence: string[];
  reason: string | null;
  commit_sha: string | null;
  file_count: number;
  total_bytes: number;
  analyzed_at: string;
};

/** Display names for the frameworks the detector can return. */
const FRAMEWORK_NAMES: Record<string, string> = {
  nextjs: "Next.js",
  react: "React",
  express: "Express",
  node: "Node.js",
  django: "Django",
  fastapi: "FastAPI",
  flask: "Flask",
  python: "Python",
  go: "Go",
  "java-maven": "Java (Maven)",
  "java-gradle": "Java (Gradle)",
  ruby: "Ruby",
  php: "PHP",
};

export function frameworkName(framework: string | null): string {
  if (!framework) return "Unknown";
  return FRAMEWORK_NAMES[framework] ?? framework;
}

/** The one-line verdict, e.g. "This is a Django app — no Docker configuration found." */
export function describeDetection(result: DetectionResult): string {
  const where = result.deploy_path ? ` in ${result.deploy_path}/` : "";
  if (result.type === "docker") {
    return result.compose
      ? `Docker Compose found${where} — this will be built with Docker.`
      : `A Dockerfile was found${where} — this will be built with Docker.`;
  }
  if (result.type === "framework") {
    return `This is a ${frameworkName(result.framework)} app${where} — no Docker configuration found.`;
  }
  return (
    result.reason ??
    "This repository could not be identified — no Docker configuration and no recognized framework."
  );
}

export function listRepos(): Promise<GitHubRepo[]> {
  return apiFetch<GitHubRepo[]>("/github/repos");
}

/**
 * Which date to show for a repository, and what to call it.
 *
 * A fork inherits the parent's push date, so "updated 2 years ago" on a
 * repository someone forked this morning is not just unhelpful — it reads as
 * the platform having missed it. When the repository is newer on this account
 * than its last push, the honest label is when it was added.
 */
export function repoRecency(repo: GitHubRepo): {
  iso: string | null;
  label: "added" | "updated";
} {
  const pushed = repo.updated_at ?? "";
  const created = repo.created_at ?? "";
  return created > pushed
    ? { iso: repo.created_at, label: "added" }
    : { iso: repo.updated_at, label: "updated" };
}

export type Candidate = {
  path: string; // "" means the whole repository
  label: string; // "Whole repository" or "frontend/"
  type: DetectedType;
  framework: string | null;
  compose: boolean;
  build_method: "docker" | "buildpack" | "compose" | null;
  evidence: string[];
  reason: string | null;
  /** Already connected by this account — it cannot be deployed twice. */
  already_connected: boolean;
  deployment_id: string | null;
  deployment_status: string | null;
};

/**
 * What to call a connected target, and how it should read.
 *
 * "Deployed" on a repository whose build failed is a decoration, not a status.
 * A student looking at a red dashboard and a green badge for the same project
 * rightly stops believing either of them.
 */
export function connectedState(status: string | null): {
  label: string;
  tone: "ok" | "danger" | "info" | "warn" | "neutral";
} {
  switch (status) {
    case "running":
    case "live":
      return { label: "Running", tone: "ok" };
    case "failed":
      return { label: "Build failed", tone: "danger" };
    case "queued":
    case "building":
    case "pushing":
    case "starting":
      return { label: "Building", tone: "info" };
    case "built":
      return { label: "Built, not started", tone: "info" };
    case "stopped":
      return { label: "Stopped", tone: "warn" };
    default:
      // Connected, but no build has ever run against it.
      return { label: "Connected", tone: "neutral" };
  }
}

export type ScanResult = {
  full_name: string;
  default_branch: string;
  commit_sha: string | null;
  file_count: number;
  total_bytes: number;
  candidates: Candidate[];
  scan_token: string;
};

/**
 * Download the repo once and list what could be deployed from it. Writes
 * nothing — the user has not chosen a target yet.
 */
export function scanRepo(fullName: string): Promise<ScanResult> {
  return apiFetch<ScanResult>("/repos/scan", {
    method: "POST",
    body: JSON.stringify({ full_name: fullName }),
  });
}

/**
 * Connect the target the user picked. The scan token carries the signed scan
 * result, so this needs no second download.
 */
/**
 * Connect what the user picked.
 *
 * One path connects a single directory. Several connect them as one
 * deployment whose containers share a private network — a frontend and the
 * backend it calls are one app, not two.
 */
export function selectTarget(
  scanToken: string,
  deployPaths: string[],
): Promise<DetectionResult> {
  return apiFetch<DetectionResult>("/repos/select", {
    method: "POST",
    body: JSON.stringify({
      scan_token: scanToken,
      deploy_path: deployPaths[0] ?? "",
      deploy_paths: deployPaths,
    }),
  });
}

/** One-line summary of a candidate, for the picker. */
export function describeCandidate(candidate: Candidate): string {
  if (candidate.type === "docker") {
    return candidate.compose
      ? "Docker Compose — every service in the file is started"
      : "Dockerfile";
  }
  if (candidate.type === "framework") {
    return `${frameworkName(candidate.framework)} — built with buildpacks`;
  }
  return "Nothing recognized here";
}

/**
 * Download the repo to a temp dir on the server, detect how it should be
 * built, and store the result. The files are removed before this returns.
 */
export function analyzeRepo(repoId: string): Promise<DetectionResult> {
  return apiFetch<DetectionResult>(`/repos/${repoId}/analyze`, { method: "POST" });
}

export type DeploymentStatus =
  | "analyzed"
  | "queued"
  | "building"
  | "built"
  | "running"
  | "live"
  | "failed";

/** Statuses where the build is still moving and the UI should keep polling. */
export const IN_FLIGHT: DeploymentStatus[] = ["queued", "building"];

export type DeploymentRow = {
  id: string;
  status: DeploymentStatus;
  build_method: "docker" | "buildpack" | null;
  commit_sha: string | null;
  created_at: string;
  updated_at: string;
  image_ref: string | null;
  build_started_at: string | null;
  build_finished_at: string | null;
  error_message: string | null;
  has_logs: boolean;
  repository_id: string;
  full_name: string;
  deploy_path: string | null;
  target_label: string;
  detected_type: DetectedType | null;
  detected_framework: string | null;
  user_id: string | null;
  user_email: string | null;
};

export type UserDeployments = {
  id: string;
  email: string;
  role: "admin" | "user";
  is_active: boolean;
  created_at: string;
  deployment_count: number;
  repository_count: number;
  github_username: string | null;
  deployments: DeploymentRow[];
};

export function listMyDeployments(): Promise<DeploymentRow[]> {
  return apiFetch<DeploymentRow[]>("/deployments");
}

export function listAllDeployments(): Promise<DeploymentRow[]> {
  return apiFetch<DeploymentRow[]>("/admin/deployments");
}

export function platformOverview(): Promise<UserDeployments[]> {
  return apiFetch<UserDeployments[]>("/admin/overview");
}

// --- Environment variables --------------------------------------------------

export type EnvVar = {
  id: string;
  key: string;
  /** null for secrets — the plaintext never leaves the server once saved. */
  value: string | null;
  is_secret: boolean;
  has_value: boolean;
  created_at: string;
  updated_at: string;
};

export type EnvVarInput = {
  key: string;
  /** null means "keep the stored value" — how a secret survives a save. */
  value: string | null;
  is_secret: boolean;
};

export function listEnvVars(repoId: string): Promise<EnvVar[]> {
  return apiFetch<EnvVar[]>(`/repos/${repoId}/env`);
}

/** Replace the whole set. This is the form's Save button. */
export function saveEnvVars(
  repoId: string,
  variables: EnvVarInput[],
): Promise<EnvVar[]> {
  return apiFetch<EnvVar[]>(`/repos/${repoId}/env`, {
    method: "PUT",
    body: JSON.stringify({ variables }),
  });
}


// --- Building ---------------------------------------------------------------

export type BuildStarted = {
  deployment_id: string;
  status: DeploymentStatus;
  target_label: string;
};

export type BuildLogs = {
  deployment_id: string;
  status: DeploymentStatus;
  logs: string;
  truncated: boolean;
};

/** Queue a build. Returns as soon as it is queued — the build runs in the background. */
export function startBuild(repoId: string): Promise<BuildStarted> {
  return apiFetch<BuildStarted>(`/repos/${repoId}/build`, { method: "POST" });
}

export function getDeployment(deploymentId: string): Promise<DeploymentRow> {
  return apiFetch<DeploymentRow>(`/deployments/${deploymentId}`);
}

export function getBuildLogs(deploymentId: string): Promise<BuildLogs> {
  return apiFetch<BuildLogs>(`/deployments/${deploymentId}/logs`);
}
