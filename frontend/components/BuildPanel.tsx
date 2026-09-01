"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import StatusBadge from "@/components/StatusBadge";
import {
  getBuildLogs,
  getDeployment,
  startBuild,
  IN_FLIGHT,
  type DeploymentRow,
  type DeploymentStatus,
} from "@/lib/github";

const POLL_MS = 2000;

function elapsed(from: string | null, to: string | null): string | null {
  if (!from) return null;
  const seconds = Math.round(
    ((to ? new Date(to) : new Date()).getTime() - new Date(from).getTime()) / 1000,
  );
  if (seconds < 0) return null;
  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

/**
 * Starts a build and follows it.
 *
 * The build runs on the server outside the request that queued it, so this
 * polls the deployment until it reaches a terminal state, showing the log as
 * it grows. Buildpack builds take minutes; the first one on a machine also
 * downloads a multi-gigabyte builder image.
 */
export default function BuildPanel({
  repositoryId,
  onFinished,
}: {
  repositoryId: string;
  onFinished?: (deployment: DeploymentRow) => void;
}) {
  const [deployment, setDeployment] = useState<DeploymentRow | null>(null);
  const [logs, setLogs] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [showLogs, setShowLogs] = useState(true);
  const logBox = useRef<HTMLPreElement>(null);

  const status: DeploymentStatus | null = deployment?.status ?? null;
  const running = status !== null && IN_FLIGHT.includes(status);

  async function begin() {
    setStarting(true);
    setError(null);
    setLogs("");
    try {
      const started = await startBuild(repositoryId);
      setDeployment(await getDeployment(started.deployment_id));
      setShowLogs(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the build.");
    } finally {
      setStarting(false);
    }
  }

  const poll = useCallback(async (deploymentId: string) => {
    const [current, logResponse] = await Promise.all([
      getDeployment(deploymentId),
      getBuildLogs(deploymentId),
    ]);
    setDeployment(current);
    setLogs(logResponse.logs);
    return current;
  }, []);

  useEffect(() => {
    if (!deployment || !IN_FLIGHT.includes(deployment.status)) return;

    let active = true;
    const id = deployment.id;
    const timer = setInterval(() => {
      poll(id)
        .then((current) => {
          if (active && !IN_FLIGHT.includes(current.status)) {
            clearInterval(timer);
            onFinished?.(current);
          }
        })
        .catch(() => {
          /* a transient poll failure is not worth surfacing; the next tick retries */
        });
    }, POLL_MS);

    return () => {
      active = false;
      clearInterval(timer);
    };
    // onFinished is intentionally omitted: the parent passes a new closure each
    // render, which would restart the interval continuously.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deployment?.id, deployment?.status, poll]);

  useEffect(() => {
    if (logBox.current) logBox.current.scrollTop = logBox.current.scrollHeight;
  }, [logs]);

  const succeeded = status === "built";
  const failed = status === "failed";

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="font-semibold">Build image</h3>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Cloud Native Buildpacks turn the source into a container image. No
            Dockerfile needed.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {status && <StatusBadge status={status} />}
          <button
            onClick={() => void begin()}
            disabled={starting || running}
            className="rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white transition hover:brightness-110 disabled:opacity-50"
          >
            {starting
              ? "Starting…"
              : running
                ? "Building…"
                : deployment
                  ? "Build again"
                  : "Build image"}
          </button>
        </div>
      </div>

      {error && (
        <p className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      )}

      {deployment && (
        <div className="mt-4 space-y-3">
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-xs uppercase tracking-wide text-[var(--muted)]">
                Status
              </dt>
              <dd className="font-mono">{deployment.status}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-[var(--muted)]">
                Commit
              </dt>
              <dd className="font-mono">
                {deployment.commit_sha ? deployment.commit_sha.slice(0, 7) : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-[var(--muted)]">
                Elapsed
              </dt>
              <dd className="font-mono">
                {elapsed(deployment.build_started_at, deployment.build_finished_at) ??
                  "—"}
              </dd>
            </div>
            <div className="col-span-2 min-w-0">
              <dt className="text-xs uppercase tracking-wide text-[var(--muted)]">
                Image
              </dt>
              <dd className="truncate font-mono">{deployment.image_ref ?? "—"}</dd>
            </div>
          </dl>

          {succeeded && (
            <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200">
              Image built. Running it is the next phase — for now you can start it
              yourself with{" "}
              <code className="font-mono">docker run {deployment.image_ref}</code>.
            </p>
          )}

          {failed && deployment.error_message && (
            <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
              {deployment.error_message}
            </p>
          )}

          {running && (
            <p className="text-xs text-[var(--muted)]">
              Building on the server. The first build on a machine also downloads
              the builder image (several GB), so it can take a while.
            </p>
          )}

          <div>
            <button
              onClick={() => setShowLogs((s) => !s)}
              className="text-sm text-[var(--muted)] underline underline-offset-4 transition hover:text-[var(--foreground)]"
            >
              {showLogs ? "Hide build log" : "Show build log"}
            </button>

            {showLogs && (
              <pre
                ref={logBox}
                className="mt-2 max-h-80 overflow-auto rounded-lg border border-[var(--border)] bg-[var(--background)] p-3 font-mono text-xs leading-relaxed"
              >
                {logs || "Waiting for output…"}
              </pre>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
