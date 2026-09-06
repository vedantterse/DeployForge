/**
 * One deployment, in full: state, controls, history, logs, configuration.
 *
 * This is where a student goes when something did not work, so the two logs
 * are first-class and kept apart. The build log explains why no image was
 * produced; the runtime log explains why the image that was produced will not
 * stay up. Conflating them is what makes platforms like this frustrating.
 */

"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import EnvVarEditor from "@/components/EnvVarEditor";
import LogPane from "@/components/LogPane";
import RequireAuth from "@/components/RequireAuth";
import StatusBadge from "@/components/StatusBadge";
import Timeline from "@/components/Timeline";
import {
  Alert,
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
  ArrowLeft,
  BoxIcon,
  DockerIcon,
  ExternalIcon,
  LayersIcon,
  PlayIcon,
  RestartIcon,
  RocketIcon,
  StopIcon,
  TerminalIcon,
  TrashIcon,
} from "@/components/Icons";
import {
  buildRepository,
  canStart,
  methodMeta,
  deleteDeployment,
  getBuildLogs,
  getDeployment,
  getEvents,
  getRuntimeLogs,
  isBusy,
  isRunning,
  restartDeployment,
  startDeployment,
  stopDeployment,
  type Deployment,
  type DeploymentEvent,
} from "@/lib/deployments";

const POLL_MS = 3000;

export default function DeploymentDetailPage() {
  return <RequireAuth studentOnly>{() => <Detail />}</RequireAuth>;
}

type Tab = "build" | "runtime";

function Detail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [deployment, setDeployment] = useState<Deployment | null>(null);
  const [events, setEvents] = useState<DeploymentEvent[]>([]);
  const [buildLog, setBuildLog] = useState("");
  const [runtimeLog, setRuntimeLog] = useState("");
  const [tab, setTab] = useState<Tab>("build");
  const [error, setError] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async (): Promise<Deployment | null> => {
    try {
      const [d, e] = await Promise.all([getDeployment(id), getEvents(id)]);
      setDeployment(d);
      setEvents(e);
      return d;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load this app.");
      return null;
    }
  }, [id]);

  // Logs are fetched separately from the record so a large log does not slow
  // the status polling that drives the buttons.
  const loadLogs = useCallback(
    async (d: Deployment) => {
      if (d.has_logs) {
        try {
          setBuildLog((await getBuildLogs(id)).logs);
        } catch {
          /* a missing log is not an error worth showing */
        }
      }
      if (d.container_name) {
        try {
          setRuntimeLog((await getRuntimeLogs(id)).logs);
        } catch {
          /* same */
        }
      }
    },
    [id],
  );

  useEffect(() => {
    let active = true;

    async function tick() {
      const d = await load();
      if (!active || !d) return;
      await loadLogs(d);
      if (!active) return;
      // Keep polling while work is in flight, or while a running app's log
      // is on screen and still growing.
      if (isBusy(d.status) || (isRunning(d.status) && tab === "runtime")) {
        timer.current = setTimeout(tick, POLL_MS);
      }
    }
    tick();

    return () => {
      active = false;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [load, loadLogs, tab]);

  async function act(name: string, fn: () => Promise<unknown>) {
    setPending(name);
    setError("");
    try {
      await fn();
      const d = await load();
      if (d) await loadLogs(d);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
      await load();
    } finally {
      setPending(null);
    }
  }

  async function remove() {
    if (
      !window.confirm(
        "Delete this deployment? Its container is stopped and removed. The built image stays in the registry.",
      )
    ) {
      return;
    }
    await act("delete", async () => {
      await deleteDeployment(id);
      router.push("/dashboard");
    });
  }

  if (!deployment) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-32" />
        <Skeleton className="h-80" />
      </div>
    );
  }

  const running = isRunning(deployment.status);
  const busy = isBusy(deployment.status) || pending !== null;
  const isDocker = deployment.build_method === "docker";
  const isCompose = deployment.build_method === "compose";
  const method = methodMeta(deployment);

  return (
    <div className="space-y-8">
      <Link
        href="/dashboard"
        className="inline-flex items-center gap-2 text-sm text-[var(--text-muted)] transition-colors hover:text-[var(--text)]"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to my apps
      </Link>

      {/* --- Header ------------------------------------------------------ */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-[1.75rem] font-semibold leading-tight">
              {deployment.target_label}
            </h1>
            <StatusBadge status={deployment.status} />
          </div>
          <p className="mt-1.5 text-sm text-[var(--text-muted)]">
            {method.detail}
            {" · updated "}
            {relativeTime(deployment.updated_at)}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            loading={pending === "build"}
            disabled={busy}
            onClick={() =>
              act("build", () => buildRepository(deployment.repository_id))
            }
            title="Fetch the latest commit and build it again"
          >
            <RocketIcon className="h-4 w-4" />
            Rebuild
          </Button>
          {canStart(deployment) && (
            <Button
              variant="primary"
              loading={pending === "start"}
              disabled={busy}
              onClick={() => act("start", () => startDeployment(id))}
            >
              <PlayIcon className="h-3 w-3" />
              Start
            </Button>
          )}
          {running && (
            <>
              <Button
                loading={pending === "restart"}
                disabled={busy}
                onClick={() => act("restart", () => restartDeployment(id))}
              >
                <RestartIcon className="h-4 w-4" />
                Restart
              </Button>
              <Button
                loading={pending === "stop"}
                disabled={busy}
                onClick={() => act("stop", () => stopDeployment(id))}
              >
                <StopIcon className="h-3 w-3" />
                Stop
              </Button>
            </>
          )}
          <Button variant="danger" loading={pending === "delete"} onClick={remove}>
            <TrashIcon className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {error && <Alert>{error}</Alert>}

      {deployment.suspended_by_admin && (
        <Alert tone="warn" title="Suspended by an administrator">
          {deployment.suspension_reason ??
            "This app has been stopped by an administrator and cannot be started again until they lift the suspension."}
        </Alert>
      )}

      {deployment.status === "failed" && deployment.error_message && (
        <Alert title="This deployment failed">{deployment.error_message}</Alert>
      )}

      {/* --- Live URL ---------------------------------------------------- */}
      {running && deployment.url && (
        <div className="bezel border-[var(--ok)]/25 bg-[var(--ok-soft)]">
          <div className="bg-[var(--surface)] p-6">
            <div className="flex flex-wrap items-center justify-between gap-5">
              <div className="min-w-0">
                <span className="inline-flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.16em] text-[var(--ok)]">
                  <span className="live-dot inline-block h-1.5 w-1.5 rounded-full bg-[var(--ok)]" />
                  Live
                </span>
                <a
                  href={deployment.url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-2.5 flex min-w-0 items-center gap-2.5 font-[family-name:var(--font-jetbrains-mono)] text-[19px] font-medium underline-offset-[6px] transition-colors duration-[var(--t-hover)] hover:text-[var(--ok)] hover:underline"
                >
                  <span className="truncate">
                    {deployment.url.replace(/^https?:\/\//, "")}
                  </span>
                  <ExternalIcon className="h-4 w-4 shrink-0 opacity-50" />
                </a>
                <p className="mt-2 text-xs text-[var(--text-dim)]">
                  Running for{" "}
                  {relativeTime(deployment.runtime_started_at).replace(" ago", "")}
                  {deployment.app_port && ` · container port ${deployment.app_port}`}
                </p>
              </div>
              <a href={deployment.url} target="_blank" rel="noreferrer">
                <Button
                  variant="primary"
                  size="lg"
                  trailing={<ExternalIcon className="h-3.5 w-3.5" />}
                >
                  Open app
                </Button>
              </a>
            </div>
          </div>
        </div>
      )}

      {/* --- Facts ------------------------------------------------------- */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Fact label="Repository" value={deployment.full_name} />
        <Fact
          label="Commit"
          value={deployment.commit_sha ? deployment.commit_sha.slice(0, 7) : "—"}
          mono
          title={deployment.commit_sha ?? undefined}
        />
        <Fact
          label="Build time"
          value={duration(deployment.build_started_at, deployment.build_finished_at)}
        />
        <Fact
          label="Method"
          value={method.label}
          icon={
            isCompose ? (
              <LayersIcon className="h-3.5 w-3.5" />
            ) : isDocker ? (
              <DockerIcon className="h-3.5 w-3.5" />
            ) : (
              <BoxIcon className="h-3.5 w-3.5" />
            )
          }
        />
      </div>

      {deployment.image_ref && (
        <Card className="px-4 py-3">
          <p className="text-xs font-medium uppercase tracking-wider text-[var(--text-dim)]">
            Image in registry
          </p>
          <Mono className="mt-1 block break-all text-[var(--text)]">
            {deployment.image_ref}
          </Mono>
        </Card>
      )}

      {isCompose && deployment.compose_services && (
        <Card className="px-4 py-3">
          <p className="text-xs font-medium uppercase tracking-wider text-[var(--text-dim)]">
            Services in this stack
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {deployment.compose_services.map((service) => (
              <span
                key={service}
                className={cx(
                  "rounded-full border px-2.5 py-0.5 text-xs font-medium",
                  deployment.container_name?.includes(`-${service}-`)
                    ? "border-[var(--ok)]/30 bg-[var(--ok-soft)] text-[var(--ok)]"
                    : "border-[var(--hairline-strong)] bg-[var(--surface-2)] text-[var(--text-muted)]",
                )}
              >
                {service}
                {deployment.container_name?.includes(`-${service}-`) && " · routed"}
              </span>
            ))}
          </div>
          <p className="mt-2 text-xs text-[var(--text-dim)]">
            All services run together on a private network. Only the routed one
            is reachable from outside.
          </p>
        </Card>
      )}

      {/* --- Logs -------------------------------------------------------- */}
      <section>
        <SectionTitle
          hint="The build log says why an image could not be made. The runtime log says why the app will not stay up."
          action={
            <div className="flex rounded-full border border-[var(--hairline)] bg-[var(--surface-2)] p-1 shadow-[var(--bevel)]">
              {(["build", "runtime"] as Tab[]).map((t) => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className={cx(
                    "rounded-full px-3.5 py-1.5 text-xs font-medium",
                    "transition-[background-color,color] duration-[var(--t-hover)] ease-[var(--ease-out)]",
                    tab === t
                      ? "bg-[var(--solid)] text-[var(--solid-text)]"
                      : "text-[var(--text-muted)] hover:text-[var(--text)]",
                  )}
                >
                  {t === "build" ? "Build log" : "Runtime log"}
                </button>
              ))}
            </div>
          }
        >
          <span className="inline-flex items-center gap-2">
            <TerminalIcon />
            Logs
          </span>
        </SectionTitle>

        {tab === "build" ? (
          <LogPane
            text={buildLog}
            streaming={isBusy(deployment.status)}
            empty="This deployment has not been built yet."
          />
        ) : (
          <LogPane
            text={runtimeLog}
            streaming={running}
            empty="No container output. Start the app to see what it prints."
          />
        )}
      </section>

      {/* --- History ----------------------------------------------------- */}
      <section>
        <SectionTitle hint="Every step this deployment has been through.">
          History
        </SectionTitle>
        <Card className="p-5">
          <Timeline events={events} />
        </Card>
      </section>

      {/* --- Configuration ----------------------------------------------- */}
      <section>
        <SectionTitle hint="Injected at build time and at run time. Values are encrypted at rest; restart the app for changes to take effect.">
          Environment variables
        </SectionTitle>
        <Card className="p-5">
          <EnvVarEditor repositoryId={deployment.repository_id} />
        </Card>
      </section>
    </div>
  );
}

function Fact({
  label,
  value,
  mono = false,
  icon,
  title,
}: {
  label: string;
  value: string;
  mono?: boolean;
  icon?: React.ReactNode;
  title?: string;
}) {
  return (
    <Card className="px-4 py-3">
      <p className="text-xs font-medium uppercase tracking-wider text-[var(--text-dim)]">
        {label}
      </p>
      <p
        title={title}
        className={cx(
          "mt-1 flex items-center gap-1.5 truncate text-sm font-medium",
          mono && "font-[family-name:var(--font-jetbrains-mono)]",
        )}
      >
        {icon}
        {value}
      </p>
    </Card>
  );
}
