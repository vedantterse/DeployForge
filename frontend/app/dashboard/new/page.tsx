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
  RestartIcon,
  RocketIcon,
  SearchIcon,
} from "@/components/Icons";
import {
  connectedState,
  describeCandidate,
  frameworkName,
  getAuthorizeUrl,
  getConnectionStatus,
  listRepos,
  repoRecency,
  scanRepo,
  selectTarget,
  type Candidate,
  type ConnectionStatus,
  type GitHubRepo,
  type ScanResult,
} from "@/lib/github";
import { buildRepository } from "@/lib/deployments";

export default function NewDeploymentPage() {
  return (
    <RequireAuth studentOnly>
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
  const [refreshing, setRefreshing] = useState(false);

  const [scan, setScan] = useState<ScanResult | null>(null);
  const [scanning, setScanning] = useState<string | null>(null);
  // Which directories are ticked. Local until "Build and deploy" is pressed,
  // so browsing the options no longer writes anything to the database.
  const [picked, setPicked] = useState<string[]>([]);
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
    // The loader is async: every setState inside it runs after an await, not
    // during this effect. The rule cannot see through the call, so it is
    // silenced here rather than contorting the fetch to satisfy a heuristic.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadConnection();
  }, [loadConnection]);

  /**
   * Re-read the repository list from GitHub.
   *
   * Nothing is cached server-side, but the list is fetched once when this page
   * mounts — so a repository created or forked while the page was already open
   * will not be there until someone asks again. This is that ask.
   */
  async function refreshRepos() {
    setRefreshing(true);
    setError("");
    try {
      setRepos(await listRepos());
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not refresh the list.",
      );
    } finally {
      setRefreshing(false);
    }
  }

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
    setPicked([]);
    try {
      setScan(await scanRepo(repo.full_name));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not scan that repository.");
    } finally {
      setScanning(null);
    }
  }

  function toggle(candidate: Candidate) {
    setError("");
    setPicked((current) =>
      current.includes(candidate.path)
        ? current.filter((p) => p !== candidate.path)
        : [...current, candidate.path],
    );
  }

  async function build() {
    if (!scan || picked.length === 0) return;
    setWorking(true);
    setError("");
    try {
      const target = await selectTarget(scan.scan_token, picked);
      const { deployment_id } = await buildRepository(target.repository_id);
      // The build runs in the background; its own page shows the log.
      router.push(`/deployments/${deployment_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the build.");
      setWorking(false);
    }
  }

  const step: Step = !connection?.connected ? 1 : !scan ? 2 : 3;

  // Which ticked directory receives public traffic. Mirrors the backend's
  // choice so the wizard promises what the platform will actually do.
  const WEB_NAMES = ["frontend", "web", "client", "ui", "www", "site", "app", "dashboard"];
  const webService =
    picked.find((p) => WEB_NAMES.includes(p.toLowerCase())) ?? picked[0] ?? "";
  const chosen =
    picked.length === 1
      ? scan?.candidates.find((c) => c.path === picked[0])
      : undefined;

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
                  className="w-full rounded-full border border-[var(--hairline-strong)] bg-[var(--surface-2)] py-2.5 pl-10 pr-4 text-sm shadow-[var(--bevel)] placeholder:text-[var(--text-dim)] transition-[border-color,background-color] duration-[var(--t-hover)] focus:border-[var(--accent-line)] focus:bg-[var(--surface-3)] focus:outline-none"
                />
              </div>

              <div className="flex items-center justify-between gap-3 text-xs text-[var(--text-dim)]">
                <span>Newest first — forks count from when you forked them.</span>
                <Button
                  size="sm"
                  variant="ghost"
                  loading={refreshing}
                  onClick={refreshRepos}
                  title="Fetch the list from GitHub again"
                >
                  <RestartIcon className="h-3.5 w-3.5" />
                  Refresh
                </Button>
              </div>

              <div className="max-h-96 space-y-2 overflow-auto pr-1">
                {filtered?.map((repo) => {
                  const deployed = repo.connected;
                  const state = connectedState(repo.deployment_status);
                  const recency = repoRecency(repo);
                  return (
                    <div
                      key={repo.github_repo_id}
                      className={cx(
                        "flex w-full items-center justify-between gap-3 rounded-[var(--r-sm)] border px-4 py-3 transition-colors",
                        scan?.full_name === repo.full_name
                          ? "border-[var(--accent)] bg-[var(--accent-soft)]"
                          : deployed
                            ? "border-[var(--hairline)] bg-[var(--surface-2)]/50"
                            : "border-[var(--hairline)] bg-[var(--surface-2)] hover:border-[var(--hairline-strong)] hover:bg-[var(--surface-3)]",
                      )}
                    >
                      <button
                        onClick={() => pickRepo(repo)}
                        disabled={scanning !== null}
                        className="min-w-0 flex-1 text-left disabled:cursor-not-allowed"
                      >
                        <span className="flex items-center gap-2">
                          <span className="truncate text-sm font-medium">
                            {repo.full_name}
                          </span>
                          {repo.private && <Badge>Private</Badge>}
                          {repo.fork && <Badge>Fork</Badge>}
                          {deployed && (
                            <Badge tone={state.tone}>{state.label}</Badge>
                          )}
                        </span>
                        <span className="mt-0.5 flex items-center gap-2 text-xs text-[var(--text-dim)]">
                          {repo.language && <span>{repo.language}</span>}
                          <span>
                            {recency.label} {relativeTime(recency.iso)}
                          </span>
                          {deployed && (
                            <span>
                              {repo.connected_paths
                                .map((path) => path || "whole repository")
                                .join(", ")}{" "}
                              connected
                            </span>
                          )}
                        </span>
                      </button>

                      <span className="flex shrink-0 items-center gap-3">
                        {deployed && repo.deployment_id && (
                          <Link
                            href={`/deployments/${repo.deployment_id}`}
                            className="text-xs text-[var(--accent)] hover:underline"
                          >
                            View
                          </Link>
                        )}
                        {scanning === repo.full_name ? (
                          <Spinner />
                        ) : (
                          <span className="text-xs text-[var(--text-dim)]">
                            {deployed ? "Scan again" : "Scan"}
                          </span>
                        )}
                      </span>
                    </div>
                  );
                })}
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
          done={picked.length > 0}
          description={
            scan.candidates.length > 1
              ? "Tick one directory, or several to run them together on a shared network."
              : "What was found in this repository."
          }
        >
          <div className="space-y-3">
            {scan.candidates.map((candidate) => {
              const active = picked.includes(candidate.path);
              const taken = candidate.already_connected;
              const takenState = connectedState(candidate.deployment_status);
              // The root candidate contains the others, so it cannot be part
              // of a combination — it would build the same code twice.
              const isRoot = candidate.path === "";
              const blockedByRoot =
                picked.length > 0 && (isRoot ? !active : picked.includes(""));
              const deployable =
                candidate.type !== "unknown" && !taken && !blockedByRoot;
              return (
                <button
                  key={candidate.path || "__root__"}
                  onClick={() => deployable && toggle(candidate)}
                  disabled={!deployable || working}
                  className={cx(
                    "flex w-full items-center justify-between gap-3 rounded-[var(--r-sm)] border px-4 py-3 text-left transition-colors",
                    active
                      ? "border-[var(--accent)] bg-[var(--accent-soft)]"
                      : "border-[var(--hairline)] bg-[var(--surface-2)]",
                    deployable
                      ? "hover:border-[var(--hairline-strong)] hover:bg-[var(--surface-3)]"
                      : "cursor-not-allowed opacity-50",
                  )}
                >
                  <span className="flex min-w-0 items-center gap-3">
                    {/* A tick box, because more than one may be chosen. */}
                    <span
                      aria-hidden
                      className={cx(
                        "flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-[6px] border",
                        "transition-colors duration-[var(--t-hover)]",
                        active
                          ? "border-[var(--accent)] bg-[var(--accent)] text-[var(--bg-deep)]"
                          : "border-[var(--hairline-strong)]",
                      )}
                    >
                      {active && <CheckIcon className="h-3 w-3" />}
                    </span>
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
                        {taken
                          ? `Already connected — ${takenState.label.toLowerCase()}. Manage it from My apps.`
                          : blockedByRoot
                            ? isRoot
                              ? "Cannot be combined with a directory inside it"
                              : "Cannot be combined with the whole repository"
                            : describeCandidate(candidate)}
                        {!taken &&
                          candidate.evidence.length > 0 &&
                          ` · ${candidate.evidence.slice(0, 3).join(", ")}`}
                      </span>
                    </span>
                  </span>
                  {taken ? (
                    <Badge tone={takenState.tone}>{takenState.label}</Badge>
                  ) : active && picked.length > 1 ? (
                    <Badge tone="accent">
                      {candidate.path === webService ? "Public" : "Internal"}
                    </Badge>
                  ) : null}
                </button>
              );
            })}
          </div>

          {picked.length > 0 && (
            <div className="mt-5 rounded-[var(--r-sm)] border border-[var(--hairline-strong)] bg-[var(--surface-2)] p-4">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="min-w-0">
                  <p className="text-sm font-medium">
                    {picked.length > 1
                      ? `${picked.length} services will run together on a private network`
                      : chosen?.type === "docker"
                        ? "Will be built from your Dockerfile"
                        : `Will be built with buildpacks as a ${frameworkName(chosen?.framework ?? null)} app`}
                  </p>
                  {picked.length > 1 ? (
                    <p className="mt-1.5 text-xs text-[var(--text-dim)]">
                      <span className="text-[var(--accent)]">{webService || "root"}</span>{" "}
                      gets the public URL. Each service reaches the others by
                      name — {picked
                        .filter((p) => p !== webService)
                        .map((p) => `${(p || "app").toUpperCase()}_URL`)
                        .join(", ")}{" "}
                      {picked.length === 2 ? "is" : "are"} set automatically.
                    </p>
                  ) : (
                    scan.commit_sha && (
                      <Mono className="mt-1 block">
                        commit {scan.commit_sha.slice(0, 7)} · {scan.file_count} files
                      </Mono>
                    )
                  )}
                </div>
                <Button
                  variant="primary"
                  size="lg"
                  loading={working}
                  onClick={build}
                  trailing={<RocketIcon className="h-3.5 w-3.5" />}
                >
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

          {scan.candidates.length > 0 &&
            scan.candidates.every((c) => c.already_connected) && (
              <Alert tone="ok" title="Everything here is already deployed">
                Every deployable target in this repository is connected to your
                account. Manage them from My apps.
              </Alert>
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
                  "bg-[var(--solid)] text-[var(--solid-text)]",
                state === "todo" &&
                  "border border-[var(--hairline-strong)] text-[var(--text-dim)]",
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
