"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  describeCandidate,
  describeDetection,
  listRepos,
  scanRepo,
  selectTarget,
  type Candidate,
  type DetectionResult,
  type GitHubRepo,
  type ScanResult,
} from "@/lib/github";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

type Selection =
  | { repo: GitHubRepo; state: "scanning" }
  | { repo: GitHubRepo; state: "choosing"; scan: ScanResult }
  | { repo: GitHubRepo; state: "connecting"; scan: ScanResult }
  | { repo: GitHubRepo; state: "done"; result: DetectionResult }
  | { repo: GitHubRepo; state: "error"; message: string };

/**
 * Lists the connected account's repositories with a filter box. Selecting one
 * connects it (persisting a Repository row) and downloads it on the server.
 */
export default function RepoList({ connected }: { connected: boolean }) {
  const [repos, setRepos] = useState<GitHubRepo[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [selection, setSelection] = useState<Selection | null>(null);

  useEffect(() => {
    // Nothing to fetch until GitHub is connected; the component renders
    // nothing in that case anyway.
    if (!connected) return;
    let active = true;
    listRepos()
      .then((r) => {
        if (active) setRepos(r);
      })
      .catch((err: unknown) => {
        if (active)
          setError(
            err instanceof Error ? err.message : "Could not load repositories.",
          );
      });
    return () => {
      active = false;
    };
  }, [connected]);

  const visible = useMemo(() => {
    if (!repos) return [];
    const needle = filter.trim().toLowerCase();
    if (!needle) return repos;
    return repos.filter(
      (r) =>
        r.full_name.toLowerCase().includes(needle) ||
        (r.description ?? "").toLowerCase().includes(needle) ||
        (r.language ?? "").toLowerCase().includes(needle),
    );
  }, [repos, filter]);

  /** Step 1: download once and find out what could be deployed. */
  async function scan(repo: GitHubRepo) {
    setSelection({ repo, state: "scanning" });
    try {
      setSelection({ repo, state: "choosing", scan: await scanRepo(repo.full_name) });
    } catch (err) {
      setSelection({
        repo,
        state: "error",
        message: err instanceof Error ? err.message : "Something went wrong.",
      });
    }
  }

  /** Step 2: record the target the user picked. No second download. */
  async function choose(repo: GitHubRepo, scanResult: ScanResult, path: string) {
    setSelection({ repo, state: "connecting", scan: scanResult });
    try {
      const result = await selectTarget(scanResult.scan_token, path);
      setSelection({ repo, state: "done", result });
    } catch (err) {
      setSelection({
        repo,
        state: "error",
        message: err instanceof Error ? err.message : "Something went wrong.",
      });
    }
  }

  if (!connected) return null;

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-semibold">Your repositories</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {repos === null
              ? "Loading from GitHub…"
              : `${visible.length} of ${repos.length} shown`}
          </p>
        </div>
        <input
          type="search"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter by name, language, description…"
          className="w-full max-w-xs rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-slate-500 dark:border-slate-700 dark:bg-slate-950"
        />
      </div>

      {error && (
        <p className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      )}

      {selection?.state === "scanning" && (
        <p className="mt-4 rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-700 dark:bg-slate-800 dark:text-slate-200">
          <span className="font-mono">{selection.repo.full_name}</span> —
          downloading and scanning for deployable apps…
        </p>
      )}

      {(selection?.state === "choosing" || selection?.state === "connecting") && (
        <TargetPicker
          scan={selection.scan}
          busy={selection.state === "connecting"}
          onChoose={(path) => void choose(selection.repo, selection.scan, path)}
        />
      )}

      {selection?.state === "error" && (
        <p className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          <span className="font-mono">{selection.repo.full_name}</span> —{" "}
          {selection.message}
        </p>
      )}

      {selection?.state === "done" && selection.result && (
        <DetectionCard result={selection.result} />
      )}

      <ul className="mt-4 divide-y divide-slate-100 dark:divide-slate-800">
        {visible.map((repo) => (
          <li
            key={repo.github_repo_id}
            className="flex flex-wrap items-center justify-between gap-3 py-3"
          >
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-medium">{repo.full_name}</span>
                {repo.private && (
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs dark:bg-slate-800">
                    private
                  </span>
                )}
              </div>
              <p className="truncate text-sm text-slate-500 dark:text-slate-400">
                {repo.description || "No description"}
              </p>
              <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">
                {repo.language ?? "—"} · {repo.default_branch}
                {repo.updated_at &&
                  ` · updated ${new Date(repo.updated_at).toLocaleDateString()}`}
              </p>
            </div>
            <button
              onClick={() => void scan(repo)}
              disabled={
                selection?.state === "scanning" &&
                selection.repo.github_repo_id === repo.github_repo_id
              }
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium transition hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:hover:bg-slate-800"
            >
              {selection?.state === "scanning" &&
              selection.repo.github_repo_id === repo.github_repo_id
                ? "Scanning…"
                : "Select"}
            </button>
          </li>
        ))}
      </ul>

      {repos !== null && visible.length === 0 && (
        <p className="mt-4 text-sm text-slate-500 dark:text-slate-400">
          {repos.length === 0
            ? "No repositories found on the connected account."
            : "No repositories match that filter."}
        </p>
      )}
    </section>
  );
}

function DetectionCard({ result }: { result: DetectionResult }) {
  const isUnknown = result.type === "unknown";

  return (
    <div
      className={`mt-4 rounded-lg border p-4 ${
        isUnknown
          ? "border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950"
          : "border-emerald-200 bg-emerald-50 dark:border-emerald-900 dark:bg-emerald-950"
      }`}
    >
      <p className="font-mono text-xs text-slate-500 dark:text-slate-400">
        {result.full_name}
        {result.deploy_path ? ` / ${result.deploy_path}` : ""}
      </p>
      <p
        className={`mt-1 text-base font-semibold ${
          isUnknown
            ? "text-amber-900 dark:text-amber-100"
            : "text-emerald-900 dark:text-emerald-100"
        }`}
      >
        {describeDetection(result)}
      </p>

      <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-5">
        <div>
          <dt className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Target
          </dt>
          <dd className="font-mono">
            {result.deploy_path ? `${result.deploy_path}/` : "whole repo"}
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Type
          </dt>
          <dd className="font-mono">{result.type}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Build method
          </dt>
          <dd className="font-mono">{result.build_method ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Compose
          </dt>
          <dd className="font-mono">{String(result.compose)}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Commit
          </dt>
          <dd className="font-mono">
            {result.commit_sha ? result.commit_sha.slice(0, 7) : "—"}
          </dd>
        </div>
      </dl>

      {result.evidence.length > 0 && (
        <div className="mt-3">
          <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Evidence
          </p>
          <ul className="mt-1 flex flex-wrap gap-2">
            {result.evidence.map((item) => (
              <li
                key={item}
                className="rounded-full bg-white/70 px-2 py-0.5 font-mono text-xs dark:bg-slate-900/60"
              >
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
        Analyzed {result.file_count} files ({formatBytes(result.total_bytes)}).
        The download has been deleted; nothing from the repository was executed.
      </p>

      <Link
        href="/dashboard"
        className="mt-4 inline-block rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
      >
        View my deployments
      </Link>
    </div>
  );
}

/**
 * Asks what to deploy.
 *
 * A monorepo with a Python backend and a TypeScript frontend has two valid
 * answers, and scanning cannot pick between them — so the user does, with the
 * detection result for each candidate shown alongside.
 */
function TargetPicker({
  scan,
  busy,
  onChoose,
}: {
  scan: ScanResult;
  busy: boolean;
  onChoose: (path: string) => void;
}) {
  const deployable = scan.candidates.filter((c) => c.type !== "unknown");
  const [chosen, setChosen] = useState<string>(
    deployable.length > 0 ? deployable[0].path : "",
  );

  return (
    <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800">
      <p className="font-medium">
        What should DeployForge deploy from{" "}
        <span className="font-mono">{scan.full_name}</span>?
      </p>
      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
        Scanned {scan.file_count} files
        {scan.commit_sha && ` at ${scan.commit_sha.slice(0, 7)}`}.
      </p>

      <fieldset className="mt-3 space-y-2" disabled={busy}>
        {scan.candidates.map((candidate: Candidate) => {
          const unusable = candidate.type === "unknown";
          return (
            <label
              key={candidate.path || "__root__"}
              className={`flex cursor-pointer items-start gap-3 rounded-md border p-3 transition ${
                chosen === candidate.path
                  ? "border-slate-900 bg-white dark:border-slate-100 dark:bg-slate-900"
                  : "border-slate-200 bg-white/60 hover:bg-white dark:border-slate-700 dark:bg-slate-900/40"
              } ${unusable ? "opacity-70" : ""}`}
            >
              <input
                type="radio"
                name="deploy-target"
                className="mt-1"
                checked={chosen === candidate.path}
                onChange={() => setChosen(candidate.path)}
              />
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-sm">{candidate.label}</span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs ${
                      unusable
                        ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200"
                        : "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200"
                    }`}
                  >
                    {describeCandidate(candidate)}
                  </span>
                  {candidate.build_method && (
                    <span className="font-mono text-xs text-slate-500 dark:text-slate-400">
                      {candidate.build_method}
                    </span>
                  )}
                </span>
                {candidate.evidence.length > 0 && (
                  <span className="mt-1 block font-mono text-xs text-slate-500 dark:text-slate-400">
                    {candidate.evidence.join(", ")}
                  </span>
                )}
              </span>
            </label>
          );
        })}
      </fieldset>

      <button
        onClick={() => onChoose(chosen)}
        disabled={busy}
        className="mt-3 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
      >
        {busy ? "Connecting…" : "Deploy this target"}
      </button>
    </div>
  );
}
