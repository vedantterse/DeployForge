/**
 * The deploy wizard: connect GitHub, pick a repository, pick what inside it,
 * then build and run.
 *
 * Four explicit steps rather than one long form, because each one can fail for
 * a reason the student has to act on — GitHub not connected, repository not
 * recognized, build failed — and a wizard makes the failure land on the step
 * that caused it.
 */

"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";

import RequireAuth from "@/components/RequireAuth";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Mono,
  Skeleton,
  Spinner,
  cx,
  relativeTime,
} from "@/components/ui";
import {
  BoxIcon,
  CheckIcon,
  DockerIcon,
  FolderIcon,
  GitHubIcon,
  RocketIcon,
  SearchIcon,
} from "@/components/Icons";
import {
  describeCandidate,
  frameworkName,
  getAuthorizeUrl,
  getConnectionStatus,
  listRepos,
  scanRepo,
  selectTarget,
  type Candidate,
  type ConnectionStatus,
  type DetectionResult,
  type GitHubRepo,
  type ScanResult,
} from "@/lib/github";
import { buildRepository } from "@/lib/deployments";

export default function NewDeploymentPage() {
  return (
    <RequireAuth>
      {() => (
        <Suspense fallback={<Skeleton className="h-96" />}>
          <Wizard />
        </Suspense>
      )}
    </RequireAuth>
  );
}

type Step = 1 | 2 | 3;

function Wizard() {
  const router = useRouter();
  const params = useSearchParams();

  const [connection, setConnection] = useState<ConnectionStatus | null>(null);
  const [connectError, setConnectError] = useState("");
  const [repos, setRepos] = useState<GitHubRepo[] | null>(null);
  const [query, setQuery] = useState("");

  const [scan, setScan] = useState<ScanResult | null>(null);
  const [scanning, setScanning] = useState<string | null>(null);
  const [selected, setSelected] = useState<DetectionResult | null>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");

  // The OAuth callback returns here with the outcome in the query string.
  const callbackError = params.get("github") === "error" ? params.get("reason") : null;

  const loadConnection = useCallback(async () => {
    try {
      const status = await getConnectionStatus();
      setConnection(status);
      if (status.connected) {
        setRepos(await listRepos());
      }
    } catch (err) {
      setConnectError(
        err instanceof Error ? err.message : "Could not check your GitHub connection.",
      );
      setConnection({
        connected: false,
        github_username: null,
        github_user_id: null,
        scopes: null,
        connected_at: null,
      });
    }
  }, []);

  useEffect(() => {
    loadConnection();
  }, [loadConnection]);

  async function connect() {
    setConnectError("");
    try {
      const { authorize_url } = await getAuthorizeUrl();
      window.location.href = authorize_url;
    } catch (err) {
      setConnectError(
        err instanceof Error ? err.message : "Could not start the GitHub flow.",
      );
    }
  }

  async function pickRepo(repo: GitHubRepo) {
    setScanning(repo.full_name);
    setError("");
    setScan(null);
    setSelected(null);
    try {
      setScan(await scanRepo(repo.full_name));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not scan that repository.");
    } finally {
      setScanning(null);
    }
  }

  async function pickTarget(candidate: Candidate) {
    if (!scan) return;
    setWorking(true);
    setError("");
    try {
      setSelected(await selectTarget(scan.scan_token, candidate.path));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not select that target.");
    } finally {
      setWorking(false);
    }
  }

  async function build() {
    if (!selected) return;
    setWorking(true);
    setError("");
    try {
      const { deployment_id } = await buildRepository(selected.repository_id);
      // The build runs in the background; its own page shows the log.
      router.push(`/deployments/${deployment_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the build.");
      setWorking(false);
    }
  }

  const step: Step = !connection?.connected ? 1 : !scan ? 2 : 3;

  const filtered = useMemo(() => {
    if (!repos) return null;
    const q = query.trim().toLowerCase();
    if (!q) return repos;
    return repos.filter(
      (r) =>
        r.full_name.toLowerCase().includes(q) ||
        (r.language ?? "").toLowerCase().includes(q),
    );
  }, [repos, query]);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Deploy a new app</h1>
        <p className="mt-1 text-sm text-[var(--text-muted)]">
          Connect GitHub, choose a repository, and DeployForge works out how to
          build and run it.
        </p>
      </div>

      <Steps current={step} />

      {callbackError && (
        <Alert title="GitHub did not complete the connection">{callbackError}</Alert>
      )}
      {error && <Alert>{error}</Alert>}

      {/* --- Step 1: connect ------------------------------------------- */}
      <StepCard
        number={1}
        title="Connect GitHub"
        done={!!connection?.connected}
        description="DeployForge needs read access to list and download your repositories."
      >
        {connection === null ? (
          <Skeleton className="h-10 w-48" />
        ) : connection.connected ? (
          <div className="flex flex-wrap items-center gap-3">
            <Badge tone="ok">
              <CheckIcon className="h-3 w-3" />
              Connected as {connection.github_username}
            </Badge>
            <span className="text-xs text-[var(--text-dim)]">
              since {relativeTime(connection.connected_at)}
            </span>
          </div>
        ) : (
          <div className="space-y-3">
            <Button variant="primary" onClick={connect}>
              <GitHubIcon className="h-4 w-4" />
              Authorize GitHub
            </Button>
            {connectError && <Alert>{connectError}</Alert>}
            <p className="text-xs text-[var(--text-dim)]">
              The token is exchanged and encrypted on the server — it never
              reaches your browser.
            </p>
          </div>
        )}
      </StepCard>

      {/* --- Step 2: repository ---------------------------------------- */}
      {connection?.connected && (
        <StepCard
          number={2}
          title="Choose a repository"
          done={!!scan}
          description="Read live from GitHub. Nothing is stored until you pick one."
        >
          {repos === null ? (
            <div className="space-y-2">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-14" />
              ))}
            </div>
          ) : repos.length === 0 ? (
            <EmptyState title="No repositories found">
              This GitHub account has no repositories DeployForge can see.
            </EmptyState>
          ) : (
            <div className="space-y-3">
              <div className="relative">
                <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-dim)]" />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={`Search ${repos.length} repositories…`}
                  className="w-full rounded-[var(--radius-sm)] border border-[var(--border-strong)] bg-[var(--surface-2)] py-2 pl-9 pr-3 text-sm placeholder:text-[var(--text-dim)] focus:border-[var(--accent)] focus:outline-none"
                />
              </div>

              <div className="max-h-96 space-y-2 overflow-auto pr-1">
                {filtered?.map((repo) => (
                  <button
                    key={repo.github_repo_id}
                    onClick={() => pickRepo(repo)}
                    disabled={scanning !== null}
                    className={cx(
                      "flex w-full items-center justify-between gap-3 rounded-[var(--radius-sm)] border px-4 py-3 text-left transition-colors",
                      scan?.full_name === repo.full_name
                        ? "border-[var(--accent)] bg-[var(--accent-soft)]"
                        : "border-[var(--border)] bg-[var(--surface-2)] hover:border-[var(--border-strong)] hover:bg-[var(--surface-3)]",
                      scanning !== null && "opacity-60",
                    )}
                  >
                    <span className="min-w-0">
                      <span className="flex items-center gap-2">
                        <span className="truncate text-sm font-medium">
                          {repo.full_name}
                        </span>
                        {repo.private && <Badge>Private</Badge>}
                      </span>
                      <span className="mt-0.5 flex items-center gap-2 text-xs text-[var(--text-dim)]">
                        {repo.language && <span>{repo.language}</span>}
                        <span>updated {relativeTime(repo.updated_at)}</span>
                      </span>
                    </span>
                    {scanning === repo.full_name ? (
                      <Spinner />
                    ) : (
                      <span className="shrink-0 text-xs text-[var(--text-dim)]">
                        Scan
                      </span>
                    )}
                  </button>
                ))}
                {filtered?.length === 0 && (
                  <p className="py-6 text-center text-sm text-[var(--text-dim)]">
                    No repository matches “{query}”.
                  </p>
                )}
              </div>
            </div>
          )}
        </StepCard>
      )}

      {/* --- Step 3: target + build ------------------------------------ */}
      {scan && (
        <StepCard
          number={3}
          title="Choose what to deploy"
          done={!!selected}
          description={
            scan.candidates.length > 1
              ? "This repository has more than one deployable directory. Only you know which one you meant."
              : "What was found in this repository."
          }
        >
          <div className="space-y-3">
            {scan.candidates.map((candidate) => {
              const active = selected?.deploy_path === (candidate.path || null);
              const deployable = candidate.type !== "unknown";
              return (
                <button
                  key={candidate.path || "__root__"}
                  onClick={() => deployable && pickTarget(candidate)}
                  disabled={!deployable || working}
                  className={cx(
                    "flex w-full items-center justify-between gap-3 rounded-[var(--radius-sm)] border px-4 py-3 text-left transition-colors",
                    active
                      ? "border-[var(--accent)] bg-[var(--accent-soft)]"
                      : "border-[var(--border)] bg-[var(--surface-2)]",
                    deployable
                      ? "hover:border-[var(--border-strong)] hover:bg-[var(--surface-3)]"
                      : "cursor-not-allowed opacity-50",
                  )}
                >
                  <span className="flex min-w-0 items-center gap-3">
                    <span className="text-[var(--text-dim)]">
                      {candidate.type === "docker" ? (
                        <DockerIcon className="h-5 w-5" />
                      ) : candidate.path ? (
                        <FolderIcon className="h-5 w-5" />
                      ) : (
                        <BoxIcon className="h-5 w-5" />
                      )}
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium">
                        {candidate.label}
                      </span>
                      <span className="text-xs text-[var(--text-dim)]">
                        {describeCandidate(candidate)}
                        {candidate.evidence.length > 0 &&
                          ` · ${candidate.evidence.slice(0, 3).join(", ")}`}
                      </span>
                    </span>
                  </span>
                  {active && (
                    <Badge tone="accent">
                      <CheckIcon className="h-3 w-3" />
                      Selected
                    </Badge>
                  )}
                </button>
              );
            })}
          </div>

          {selected && (
            <div className="mt-5 rounded-[var(--radius-sm)] border border-[var(--border-strong)] bg-[var(--surface-2)] p-4">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-medium">
                    {selected.type === "docker"
                      ? "Will be built from your Dockerfile"
                      : `Will be built with buildpacks as a ${frameworkName(selected.framework)} app`}
                  </p>
                  {selected.commit_sha && (
                    <Mono className="mt-1 block">
                      commit {selected.commit_sha.slice(0, 7)} ·{" "}
                      {selected.file_count} files
                    </Mono>
                  )}
                </div>
                <Button variant="primary" loading={working} onClick={build}>
                  <RocketIcon className="h-4 w-4" />
                  Build and deploy
                </Button>
              </div>
              <p className="mt-3 text-xs text-[var(--text-dim)]">
                The build runs in the background. You will be taken to its page,
                where the log streams as it happens. The first buildpack build on
                a machine downloads a large builder image and takes a while.
              </p>
            </div>
          )}

          {scan.candidates.every((c) => c.type === "unknown") && (
            <Alert tone="warn" title="Nothing deployable was found">
              No Dockerfile, and no recognized framework markers such as
              package.json, requirements.txt or go.mod. Add a Dockerfile to the
              directory you want to deploy, then scan again.
            </Alert>
          )}
        </StepCard>
      )}

      <p className="text-center text-sm text-[var(--text-dim)]">
        <Link href="/dashboard" className="hover:text-[var(--text)]">
          Back to my apps
        </Link>
      </p>
    </div>
  );
}

/* --- Chrome ------------------------------------------------------------- */

function Steps({ current }: { current: Step }) {
  const labels = ["Connect GitHub", "Choose repository", "Choose target"];
  return (
    <ol className="flex items-center gap-2">
      {labels.map((label, i) => {
        const n = (i + 1) as Step;
        const state = n < current ? "done" : n === current ? "active" : "todo";
        return (
          <li key={label} className="flex flex-1 items-center gap-2">
            <span
              className={cx(
                "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                state === "done" && "bg-[var(--ok-soft)] text-[var(--ok)]",
                state === "active" &&
                  "bg-[var(--accent)] text-[var(--accent-text)]",
                state === "todo" &&
                  "border border-[var(--border-strong)] text-[var(--text-dim)]",
              )}
            >
              {state === "done" ? <CheckIcon className="h-3.5 w-3.5" /> : n}
            </span>
            <span
              className={cx(
                "hidden text-xs font-medium sm:block",
                state === "todo" ? "text-[var(--text-dim)]" : "text-[var(--text)]",
              )}
            >
              {label}
            </span>
            {i < labels.length - 1 && (
              <span className="h-px flex-1 bg-[var(--border-strong)]" />
            )}
          </li>
        );
      })}
    </ol>
  );
}

function StepCard({
  number,
  title,
  description,
  done,
  children,
}: {
  number: number;
  title: string;
  description: string;
  done: boolean;
  children: React.ReactNode;
}) {
  return (
    <Card className="p-6">
      <div className="mb-4 flex items-start gap-3">
        <span
          className={cx(
            "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
            done
              ? "bg-[var(--ok-soft)] text-[var(--ok)]"
              : "bg-[var(--accent-soft)] text-[var(--accent)]",
          )}
        >
          {done ? <CheckIcon className="h-3.5 w-3.5" /> : number}
        </span>
        <div>
          <h2 className="font-semibold tracking-tight">{title}</h2>
          <p className="mt-0.5 text-sm text-[var(--text-muted)]">{description}</p>
        </div>
      </div>
      {children}
    </Card>
  );
}
