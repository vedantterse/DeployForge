/**
 * Every app on the platform, with the admin's controls attached.
 *
 * Suspending is deliberately separate from stopping: a stop is something the
 * owner can undo a second later, which is useless when the reason for stopping
 * was the owner. A suspended app stays down until an admin lifts it.
 */

"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import RequireAuth from "@/components/RequireAuth";
import StatusBadge from "@/components/StatusBadge";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Mono,
  SectionTitle,
  Skeleton,
  cx,
  relativeTime,
} from "@/components/ui";
import {
  BoxIcon,
  DockerIcon,
  ExternalIcon,
  PlayIcon,
  SearchIcon,
  ServerIcon,
  StopIcon,
  TrashIcon,
} from "@/components/Icons";
import {
  adminDeleteDeployment,
  getAllDeployments,
  resumeDeployment,
  suspendDeployment,
} from "@/lib/admin";
import { isBusy, isRunning, type Deployment } from "@/lib/deployments";

type Filter = "all" | "running" | "failed" | "suspended";

export default function AdminDeploymentsPage() {
  return <RequireAuth adminOnly>{() => <AllDeployments />}</RequireAuth>;
}

function AllDeployments() {
  const [rows, setRows] = useState<Deployment[] | null>(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [pending, setPending] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setRows(await getAllDeployments());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load deployments.");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function act(id: string, name: string, fn: (id: string) => Promise<unknown>) {
    setPending(`${id}:${name}`);
    setError("");
    try {
      await fn(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed.");
    } finally {
      setPending(null);
    }
  }

  async function remove(d: Deployment) {
    if (
      !window.confirm(
        `Delete ${d.target_label} belonging to ${d.user_email}? Its container is stopped and removed.`,
      )
    ) {
      return;
    }
    await act(d.id, "delete", adminDeleteDeployment);
  }

  const filtered = useMemo(() => {
    if (!rows) return null;
    const q = query.trim().toLowerCase();
    return rows.filter((d) => {
      if (filter === "running" && !isRunning(d.status)) return false;
      if (filter === "failed" && d.status !== "failed") return false;
      if (filter === "suspended" && !d.suspended_by_admin) return false;
      if (!q) return true;
      return (
        d.target_label.toLowerCase().includes(q) ||
        (d.user_email ?? "").toLowerCase().includes(q) ||
        (d.subdomain ?? "").toLowerCase().includes(q)
      );
    });
  }, [rows, query, filter]);

  const counts = useMemo(
    () => ({
      all: rows?.length ?? 0,
      running: rows?.filter((d) => isRunning(d.status)).length ?? 0,
      failed: rows?.filter((d) => d.status === "failed").length ?? 0,
      suspended: rows?.filter((d) => d.suspended_by_admin).length ?? 0,
    }),
    [rows],
  );

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">All apps</h1>
        <p className="mt-1 text-sm text-[var(--text-muted)]">
          Every deployment on the platform, whoever owns it.
        </p>
      </div>

      {error && <Alert>{error}</Alert>}

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-56 flex-1">
          <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-dim)]" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by app, owner or URL…"
            className="w-full rounded-[var(--radius-sm)] border border-[var(--border-strong)] bg-[var(--surface-2)] py-2 pl-9 pr-3 text-sm placeholder:text-[var(--text-dim)] focus:border-[var(--accent)] focus:outline-none"
          />
        </div>

        <div className="flex rounded-[var(--radius-sm)] border border-[var(--border-strong)] bg-[var(--surface-2)] p-1">
          {(["all", "running", "failed", "suspended"] as Filter[]).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cx(
                "rounded-[calc(var(--radius-sm)-2px)] px-3 py-1.5 text-xs font-medium capitalize transition-colors",
                filter === f
                  ? "bg-[var(--accent)] text-[var(--accent-text)]"
                  : "text-[var(--text-muted)] hover:text-[var(--text)]",
              )}
            >
              {f} <span className="tabular opacity-70">{counts[f]}</span>
            </button>
          ))}
        </div>
      </div>

      <section>
        <SectionTitle>
          <span className="inline-flex items-center gap-2">
            <ServerIcon />
            Deployments
          </span>
        </SectionTitle>

        {filtered === null ? (
          <div className="space-y-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-24" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={<BoxIcon className="h-10 w-10" />}
            title={rows?.length === 0 ? "Nothing deployed yet" : "No matches"}
          >
            {rows?.length === 0
              ? "When students deploy apps, they appear here."
              : "Try a different search or filter."}
          </EmptyState>
        ) : (
          <div className="space-y-3">
            {filtered.map((d) => {
              const running = isRunning(d.status);
              const busy = isBusy(d.status) || pending?.startsWith(d.id);
              return (
                <Card key={d.id} className="p-5">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2.5">
                        <span className="truncate font-medium">
                          {d.target_label}
                        </span>
                        <StatusBadge status={d.status} />
                        {d.suspended_by_admin && (
                          <Badge tone="danger">Suspended</Badge>
                        )}
                      </div>
                      <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-[var(--text-dim)]">
                        <span className="text-[var(--text-muted)]">
                          {d.user_email}
                        </span>
                        <span className="inline-flex items-center gap-1.5">
                          {d.build_method === "docker" ? (
                            <DockerIcon className="h-3.5 w-3.5" />
                          ) : (
                            <BoxIcon className="h-3.5 w-3.5" />
                          )}
                          {d.build_method === "docker" ? "Dockerfile" : "Buildpack"}
                        </span>
                        <span>updated {relativeTime(d.updated_at)}</span>
                      </div>
                      {running && d.url && (
                        <a
                          href={d.url}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-2 inline-flex items-center gap-1.5 text-xs text-[var(--ok)] hover:underline"
                        >
                          {d.url.replace(/^https?:\/\//, "")}
                          <ExternalIcon className="h-3 w-3" />
                        </a>
                      )}
                      {d.image_ref && (
                        <Mono className="mt-1 block truncate">{d.image_ref}</Mono>
                      )}
                    </div>

                    <div className="flex shrink-0 items-center gap-2">
                      {d.suspended_by_admin ? (
                        <Button
                          size="sm"
                          variant="primary"
                          loading={pending === `${d.id}:resume`}
                          disabled={busy}
                          onClick={() => act(d.id, "resume", resumeDeployment)}
                        >
                          <PlayIcon className="h-3 w-3" />
                          Resume
                        </Button>
                      ) : (
                        <Button
                          size="sm"
                          loading={pending === `${d.id}:suspend`}
                          disabled={busy || !running}
                          onClick={() => act(d.id, "suspend", suspendDeployment)}
                          title={
                            running
                              ? "Stop this app and prevent the owner restarting it"
                              : "Only a running app can be suspended"
                          }
                        >
                          <StopIcon className="h-3 w-3" />
                          Suspend
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="danger"
                        loading={pending === `${d.id}:delete`}
                        onClick={() => remove(d)}
                      >
                        <TrashIcon className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
