/**
 * One app: what it is, whether it is up, and every time it has been built.
 *
 * This is the page a student lives on. The app is the thing they created and
 * the thing they share a link to; its deployments are the attempts to run it,
 * and they matter mainly when one of them fails. So the top of the page is the
 * app — status, URL, controls, configuration — and the history sits below it,
 * each entry opening the build log that explains itself.
 *
 * Nothing here acts on "the app" directly, because an app has no lifecycle of
 * its own. Start, stop and restart act on whichever deployment is current;
 * redeploy creates a new one.
 */

"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import EnvVarEditor from "@/components/EnvVarEditor";
import RequireAuth from "@/components/RequireAuth";
import StatusBadge from "@/components/StatusBadge";
import {
  Alert,
  Badge,
  Button,
  Card,
  Mono,
  SectionTitle,
  Skeleton,
  cx,
  duration,
  relativeTime,
} from "@/components/ui";
import {
  AlertIcon,
  ArrowLeft,
  BoxIcon,
  ChevronRight,
  DockerIcon,
  ExternalIcon,
  LayersIcon,
  PlayIcon,
  RestartIcon,
  RocketIcon,
  StopIcon,
  TrashIcon,
} from "@/components/Icons";
import { appIsBusy, appState, deleteApp, getApp, type AppDetail } from "@/lib/apps";
import {
  buildRepository,
  canStart,
  isRunning,
  methodMeta,
  restartDeployment,
  startDeployment,
  stopDeployment,
  type Deployment,
} from "@/lib/deployments";

const POLL_MS = 3000;

export default function AppDetailPage() {
  return <RequireAuth studentOnly>{() => <Detail />}</RequireAuth>;
}

function Detail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [app, setApp] = useState<AppDetail | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async (): Promise<AppDetail | null> => {
    try {
      const next = await getApp(id);
      setApp(next);
      return next;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load this app.");
      return null;
    }
  }, [id]);

  // Poll only while a build or a start is actually in flight.
  useEffect(() => {
    let active = true;

    async function tick() {
      const next = await load();
      if (!active || !next) return;
      if (appIsBusy(next)) timer.current = setTimeout(tick, POLL_MS);
    }
    tick();

    return () => {
      active = false;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [load]);

  async function act(name: string, fn: (id: string) => Promise<Deployment>) {
    if (!app?.current) return;
    setPending(name);
    setError("");
    try {
      await fn(app.current.id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setPending(null);
    }
  }

  /** Build the app again. The new deployment replaces the current one. */
  async function redeploy() {
    if (!app) return;
    setPending("redeploy");
    setError("");
    try {
      const { deployment_id } = await buildRepository(app.id);
      router.push(`/deployments/${deployment_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the build.");
      setPending(null);
    }
  }

  async function remove() {
    if (!app) return;
    setPending("delete");
    setError("");
    try {
      await deleteApp(app.id);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete this app.");
      setPending(null);
      setConfirmingDelete(false);
    }
  }

  if (!app) {
    return (
      <div className="space-y-5">
        <Skeleton className="h-9 w-64" />
        <Skeleton className="h-44" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  const current = app.current;
  const state = appState(app);
  const running = !!current && isRunning(current.status);
  const busy = appIsBusy(app) || pending !== null;
  const method = current ? methodMeta(current) : null;

  return (
    <div className="space-y-8">
      <Link
        href="/dashboard"
        className="inline-flex items-center gap-2 text-sm text-[var(--text-dim)] transition-colors duration-[var(--t-hover)] hover:text-[var(--text)]"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        My apps
      </Link>

      {error && <Alert>{error}</Alert>}

      {current?.suspended_by_admin && (
        <Alert tone="danger" title="Suspended by an administrator">
          {current.suspension_reason ??
            "This app has been suspended. Contact an administrator to have it resumed."}
        </Alert>
      )}

      {/* --- The app itself --------------------------------------------- */}
      <Card className="overflow-hidden">
        <div className="flex flex-col gap-5 p-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="truncate text-[1.6rem] font-semibold leading-tight">
                {app.target_label}
              </h1>
              <Badge tone={state.tone}>{state.label}</Badge>
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-[var(--text-dim)]">
              {method && (
                <span className="inline-flex items-center gap-1.5">
                  {current?.build_method === "compose" ? (
                    <LayersIcon className="h-3.5 w-3.5" />
                  ) : current?.build_method === "docker" ? (
                    <DockerIcon className="h-3.5 w-3.5" />
                  ) : (
                    <BoxIcon className="h-3.5 w-3.5" />
                  )}
                  {method.label} — {method.detail}
                </span>
              )}
              <span>
                {app.deployment_count === 0
                  ? "Never deployed"
                  : `${app.deployment_count} deployment${app.deployment_count === 1 ? "" : "s"}`}
              </span>
              {app.last_deployed_at && (
                <span>Last deployed {relativeTime(app.last_deployed_at)}</span>
              )}
            </div>

            {/* The URL is the app's, not one build's — it survives a redeploy. */}
            {running && current?.url ? (
              <a
                href={current.url}
                target="_blank"
                rel="noreferrer"
                className={cx(
                  "group/url mt-4 inline-flex items-center gap-2 rounded-full border border-[var(--ok)]/25 bg-[var(--ok-soft)]",
                  "px-4 py-2 font-[family-name:var(--font-jetbrains-mono)] text-sm font-medium text-[var(--ok)]",
                  "transition-colors duration-[var(--t-hover)] ease-[var(--ease-out)] hover:bg-[var(--ok)] hover:text-[var(--bg-deep)]",
                )}
              >
                {current.url.replace(/^https?:\/\//, "")}
                <ExternalIcon className="h-3.5 w-3.5 opacity-60 transition-opacity group-hover/url:opacity-100" />
              </a>
            ) : (
              current?.subdomain && (
                <p className="mt-4 text-xs text-[var(--text-dim)]">
                  Will answer at{" "}
                  <Mono>{current.url?.replace(/^https?:\/\//, "")}</Mono> once
                  started.
                </p>
              )
            )}
          </div>

          <div className="flex shrink-0 flex-wrap items-center gap-2">
            {current && canStart(current) && (
              <Button
                variant="primary"
                loading={pending === "start"}
                disabled={busy}
                onClick={() => act("start", startDeployment)}
              >
                <PlayIcon className="h-3.5 w-3.5" />
                Start
              </Button>
            )}
            {running && (
              <>
                <Button
                  loading={pending === "restart"}
                  disabled={busy}
                  onClick={() => act("restart", restartDeployment)}
                >
                  <RestartIcon className="h-3.5 w-3.5" />
                  Restart
                </Button>
                <Button
                  loading={pending === "stop"}
                  disabled={busy}
                  onClick={() => act("stop", stopDeployment)}
                >
                  <StopIcon className="h-3 w-3" />
                  Stop
                </Button>
              </>
            )}
            <Button
              loading={pending === "redeploy"}
              disabled={busy || current?.suspended_by_admin}
              onClick={redeploy}
              title="Build this app again from the latest commit"
            >
              <RocketIcon className="h-3.5 w-3.5" />
              Redeploy
            </Button>
          </div>
        </div>
      </Card>

      {/* --- Configuration ------------------------------------------------ */}
      <section>
        <SectionTitle hint="Injected at build time and at run time, into every deployment of this app. Values are encrypted at rest; restart for changes to take effect.">
          Environment variables
        </SectionTitle>
        <Card className="p-5">
          <EnvVarEditor repositoryId={app.id} />
        </Card>
      </section>

      {/* --- History ------------------------------------------------------ */}
      <section>
        <SectionTitle hint="Every build of this app, newest first. Open one to read its log.">
          Deployments
        </SectionTitle>

        {app.deployments.length === 0 ? (
          <Card className="p-8 text-center">
            <p className="text-sm text-[var(--text-muted)]">
              This app has never been built.
            </p>
            <div className="mt-4 flex justify-center">
              <Button variant="primary" onClick={redeploy} loading={pending === "redeploy"}>
                <RocketIcon className="h-3.5 w-3.5" />
                Build it now
              </Button>
            </div>
          </Card>
        ) : (
          <div className="space-y-2">
            {app.deployments.map((d, i) => (
              <DeploymentRow
                key={d.id}
                deployment={d}
                isCurrent={d.id === current?.id}
                index={i}
              />
            ))}
          </div>
        )}
      </section>

      {/* --- Removal ------------------------------------------------------ */}
      <section>
        <SectionTitle hint="Stops everything this app is running, deletes its history, and disconnects the repository so it can be added again.">
          Delete this app
        </SectionTitle>
        <Card className="flex flex-wrap items-center justify-between gap-4 border-[var(--danger)]/20 p-5">
          <p className="text-sm text-[var(--text-muted)]">
            {confirmingDelete
              ? `This removes ${app.target_label} and all ${app.deployment_count} of its deployments. It cannot be undone.`
              : "The repository stays on GitHub. Only what DeployForge built is removed."}
          </p>
          {confirmingDelete ? (
            <div className="flex items-center gap-2">
              <Button onClick={() => setConfirmingDelete(false)} disabled={pending === "delete"}>
                Cancel
              </Button>
              <Button
                variant="danger"
                loading={pending === "delete"}
                onClick={remove}
              >
                <TrashIcon className="h-3.5 w-3.5" />
                Delete permanently
              </Button>
            </div>
          ) : (
            <Button
              variant="danger"
              onClick={() => setConfirmingDelete(true)}
              disabled={current?.suspended_by_admin}
              title={
                current?.suspended_by_admin
                  ? "A suspended app cannot be deleted"
                  : undefined
              }
            >
              <TrashIcon className="h-3.5 w-3.5" />
              Delete app
            </Button>
          )}
        </Card>
      </section>
    </div>
  );
}

/**
 * One build in the history.
 *
 * Deliberately quieter than the app above it: a build matters when it failed
 * or when it is the one currently serving, and the row says which without
 * competing with the app's own controls.
 */
function DeploymentRow({
  deployment,
  isCurrent,
  index,
}: {
  deployment: Deployment;
  isCurrent: boolean;
  index: number;
}) {
  const failed = deployment.status === "failed";

  return (
    <Link
      href={`/deployments/${deployment.id}`}
      className={cx(
        "rise group block rounded-[var(--r-sm)] border p-4 transition-colors duration-[var(--t-hover)]",
        isCurrent
          ? "border-[var(--accent-line)] bg-[var(--surface-2)]"
          : "border-[var(--hairline)] hover:border-[var(--hairline-strong)] hover:bg-[var(--surface-2)]",
      )}
      {...({ style: { "--delay": `${Math.min(index, 8) * 45}ms` } } as object)}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 flex-wrap items-center gap-2.5">
          <StatusBadge status={deployment.status} />
          {isCurrent && <Badge tone="accent">Current</Badge>}
          {deployment.commit_sha && (
            <Mono title={deployment.commit_sha}>
              {deployment.commit_sha.slice(0, 7)}
            </Mono>
          )}
          <span className="text-xs text-[var(--text-dim)]">
            {relativeTime(deployment.created_at)}
          </span>
          {deployment.build_started_at && deployment.build_finished_at && (
            <span className="text-xs text-[var(--text-dim)]">
              built in{" "}
              {duration(deployment.build_started_at, deployment.build_finished_at)}
            </span>
          )}
        </div>
        <ChevronRight className="h-4 w-4 shrink-0 text-[var(--text-dim)] transition-transform duration-[var(--t-hover)] ease-[var(--ease-spring)] group-hover:translate-x-0.5" />
      </div>

      {failed && deployment.error_message && (
        <p className="mt-3 line-clamp-2 flex items-start gap-2 text-xs leading-relaxed text-[var(--danger)]">
          <AlertIcon className="mt-px h-3.5 w-3.5 shrink-0" />
          {deployment.error_message}
        </p>
      )}
    </Link>
  );
}
