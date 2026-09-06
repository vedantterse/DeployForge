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
  Eyebrow,
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
    // The loader is async: every setState inside it runs after an await, not
    // during this effect. The rule cannot see through the call, so it is
    // silenced here rather than contorting the fetch to satisfy a heuristic.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  async function suspend(d: Deployment) {
    const reason = window.prompt(
      `Suspend ${d.target_label}?

It is stopped, its owner cannot start it again, and they cannot delete it to get a clean one. Give a reason they will see:`,
      "",
    );
    // `null` means the admin cancelled; an empty string is a deliberate blank.
    if (reason === null) return;
    await act(d.id, "suspend", (id) => suspendDeployment(id, reason.trim() || undefined));
  }

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
        <Eyebrow>Everything deployed</Eyebrow>
        <h1 className="mt-3 text-[2rem] font-semibold leading-tight">Projects</h1>
        <p className="mt-1 text-sm text-[var(--text-muted)]">
          Every deployment on the platform, whoever owns it. Suspending stops a
          project and prevents its owner restarting or re-adding it.
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
            className="w-full rounded-full border border-[var(--hairline-strong)] bg-[var(--surface-2)] py-2.5 pl-10 pr-4 text-sm shadow-[var(--bevel)] placeholder:text-[var(--text-dim)] transition-[border-color,background-color] duration-[var(--t-hover)] focus:border-[var(--accent-line)] focus:bg-[var(--surface-3)] focus:outline-none"
          />
        </div>

        <div className="flex rounded-full border border-[var(--hairline)] bg-[var(--surface-2)] p-1 shadow-[var(--bevel)]">
          {(["all", "running", "failed", "suspended"] as Filter[]).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cx(
                "rounded-full px-3.5 py-1.5 text-xs font-medium capitalize",
                "transition-[background-color,color] duration-[var(--t-hover)] ease-[var(--ease-out)]",
                filter === f
                  ? "bg-[var(--solid)] text-[var(--solid-text)]"
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
                      {d.suspended_by_admin && d.suspension_reason && (
                        <p className="mt-2 rounded-[var(--r-sm)] bg-[var(--danger-soft)] px-3 py-2 text-xs text-[var(--danger)]">
                          <span className="font-semibold">Suspended:</span>{" "}
                          {d.suspension_reason}
                        </p>
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
                          disabled={busy}
                          onClick={() => suspend(d)}
                          title="Stop this app and stop the owner restarting, deleting or re-adding it"
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
