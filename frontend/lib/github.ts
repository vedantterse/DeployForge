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
  updated_at: string | null;
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
  type: DetectedType;
  framework: string | null;
  compose: boolean;
  build_method: "docker" | "buildpack" | null;
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

export type Candidate = {
  path: string; // "" means the whole repository
  label: string; // "Whole repository" or "frontend/"
  type: DetectedType;
  framework: string | null;
  compose: boolean;
  build_method: "docker" | "buildpack" | null;
  evidence: string[];
  reason: string | null;
};

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
export function selectTarget(
  scanToken: string,
  deployPath: string,
): Promise<DetectionResult> {
  return apiFetch<DetectionResult>("/repos/select", {
    method: "POST",
    body: JSON.stringify({ scan_token: scanToken, deploy_path: deployPath }),
  });
}

/** One-line summary of a candidate, for the picker. */
export function describeCandidate(candidate: Candidate): string {
  if (candidate.type === "docker") {
    return candidate.compose ? "Docker Compose" : "Dockerfile";
  }
  if (candidate.type === "framework") {
    return frameworkName(candidate.framework);
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
  | "running"
  | "live"
  | "failed";

export type DeploymentRow = {
  id: string;
  status: DeploymentStatus;
  build_method: "docker" | "buildpack" | null;
  commit_sha: string | null;
  created_at: string;
  updated_at: string;
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
