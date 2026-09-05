/**
 * The admin console: who is on the platform, what they are running, and the
 * health of the machine they share.
 *
 * Infrastructure status sits at the top because it changes how everything
 * below should be read — when Docker is down, every failed build on the page
 * has the same cause, and an admin should see that before investigating
 * thirty students individually.
 */

"use client";

import { useCallback, useEffect, useState } from "react";

import RequireAuth from "@/components/RequireAuth";
import StatusBadge from "@/components/StatusBadge";
import {
  Alert,
  Badge,
  Button,
  Card,
  Dot,
  Metric,
  SectionTitle,
  Skeleton,
  cx,
  relativeTime,
} from "@/components/ui";
import {
  AlertIcon,
  BoxIcon,
  CheckIcon,
  ExternalIcon,
  GitHubIcon,
  ServerIcon,
  ShieldIcon,
  UsersIcon,
} from "@/components/Icons";
import {
  getOverview,
  getPlatformStatus,
  getStats,
  updateUser,
  type PlatformStats,
  type PlatformStatus,
  type UserWithDeployments,
} from "@/lib/admin";
import { isRunning } from "@/lib/deployments";

export default function AdminPage() {
  return <RequireAuth adminOnly>{() => <Console />}</RequireAuth>;
}

function Console() {
  const [users, setUsers] = useState<UserWithDeployments[] | null>(null);
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [status, setStatus] = useState<PlatformStatus | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [o, s] = await Promise.all([getOverview(), getStats()]);
      setUsers(o);
      setStats(s);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the console.");
    }
    // Status probes real infrastructure and can be slow; never block the page.
    getPlatformStatus().then(setStatus).catch(() => undefined);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Accounts</h1>
        <p className="mt-1 text-sm text-[var(--text-muted)]">
          Everyone on the platform, what they have deployed, and what they are
          allowed to run.
        </p>
      </div>

      {error && <Alert>{error}</Alert>}

      <InfrastructurePanel status={status} />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="Accounts" value={stats?.users ?? "—"} />
        <Metric
          label="Running apps"
          value={stats?.running ?? "—"}
          tone={stats && stats.running > 0 ? "ok" : "neutral"}
        />
        <Metric label="Total deployments" value={stats?.deployments ?? "—"} />
        <Metric
          label="Failed"
          value={stats?.failed ?? "—"}
          tone={stats && stats.failed > 0 ? "danger" : "neutral"}
        />
      </div>

      <section>
        <SectionTitle hint="Newest accounts first. Raise a student's limit to let them run more apps at once.">
          <span className="inline-flex items-center gap-2">
            <UsersIcon />
            Accounts
          </span>
        </SectionTitle>

        {users === null ? (
          <div className="space-y-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-32" />
            ))}
          </div>
        ) : (
          <div className="space-y-3">
            {users.map((u) => (
              <UserRow key={u.id} user={u} onChanged={load} onError={setError} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

/* --- Infrastructure ----------------------------------------------------- */

function InfrastructurePanel({ status }: { status: PlatformStatus | null }) {
  if (!status) return <Skeleton className="h-24" />;

  const parts: { key: keyof PlatformStatus; label: string; hint: string }[] = [
    { key: "docker", label: "Docker", hint: "builds and containers" },
    { key: "registry", label: "Registry", hint: "image storage" },
    { key: "router", label: "Router", hint: "app URLs" },
    { key: "buildpacks", label: "Buildpacks", hint: "repos with no Dockerfile" },
  ];
  const degraded = parts.filter((p) => !status[p.key]);

  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="inline-flex items-center gap-2 font-semibold tracking-tight">
          <ServerIcon />
          Infrastructure
        </h2>
        {degraded.length === 0 ? (
          <Badge tone="ok">
            <CheckIcon className="h-3 w-3" />
            All systems up
          </Badge>
        ) : (
          <Badge tone="warn">
            <AlertIcon className="h-3 w-3" />
            {degraded.length} degraded
          </Badge>
        )}
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {parts.map((part) => {
          const up = status[part.key] as boolean;
          return (
            <div
              key={part.key}
              className="rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2.5"
            >
              <div className="flex items-center gap-2">
                <Dot tone={up ? "ok" : "danger"} pulse={up} />
                <span className="text-sm font-medium">{part.label}</span>
              </div>
              <p className="mt-0.5 pl-4 text-xs text-[var(--text-dim)]">
                {up ? part.hint : "unavailable"}
              </p>
            </div>
          );
        })}
      </div>

      {Object.entries(status.detail).length > 0 && (
        <div className="mt-4 space-y-2">
          {Object.entries(status.detail).map(([key, message]) => (
            <p
              key={key}
              className="rounded-[var(--radius-sm)] bg-[var(--warn-soft)] px-3 py-2 text-xs text-[var(--warn)]"
            >
              <span className="font-semibold capitalize">{key}:</span> {message}
            </p>
          ))}
        </div>
      )}
    </Card>
  );
}

/* --- Accounts ----------------------------------------------------------- */

function UserRow({
  user,
  onChanged,
  onError,
}: {
  user: UserWithDeployments;
  onChanged: () => void;
  onError: (m: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [quota, setQuota] = useState(user.max_deployments);

  async function change(changes: Parameters<typeof updateUser>[1]) {
    setBusy(true);
    onError("");
    try {
      await updateUser(user.id, changes);
      onChanged();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Could not update the account.");
      setQuota(user.max_deployments);
    } finally {
      setBusy(false);
    }
  }

  const running = user.deployments.filter((d) => isRunning(d.status)).length;
  const atLimit = running >= user.max_deployments;

  return (
    <Card className={cx(!user.is_active && "opacity-60")}>
      <div className="flex flex-wrap items-start justify-between gap-4 p-5">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="truncate font-medium">{user.email}</span>
            {user.role === "admin" && (
              <Badge tone="accent">
                <ShieldIcon className="h-3 w-3" />
                Admin
              </Badge>
            )}
            {!user.is_active && <Badge tone="danger">Disabled</Badge>}
          </div>

          <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-[var(--text-dim)]">
            {user.github_username ? (
              <span className="inline-flex items-center gap-1.5">
                <GitHubIcon className="h-3.5 w-3.5" />
                {user.github_username}
              </span>
            ) : (
              <span>GitHub not connected</span>
            )}
            <span>{user.repository_count} targets</span>
            <span
              className={cx(
                "tabular",
                atLimit && running > 0 && "text-[var(--warn)]",
              )}
            >
              {running} / {user.max_deployments} running
            </span>
            <span>joined {relativeTime(user.created_at)}</span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
            Limit
            <input
              type="number"
              min={0}
              max={50}
              value={quota}
              disabled={busy}
              onChange={(e) => setQuota(Number(e.target.value))}
              onBlur={() => {
                if (quota !== user.max_deployments) {
                  change({ max_deployments: quota });
                }
              }}
              className="tabular w-16 rounded-[var(--radius-sm)] border border-[var(--border-strong)] bg-[var(--surface-2)] px-2 py-1 text-center text-sm focus:border-[var(--accent)] focus:outline-none"
            />
          </label>

          <Button
            size="sm"
            variant={user.is_active ? "secondary" : "primary"}
            loading={busy}
            onClick={() => change({ is_active: !user.is_active })}
          >
            {user.is_active ? "Disable" : "Enable"}
          </Button>

          {user.deployments.length > 0 && (
            <Button size="sm" variant="ghost" onClick={() => setOpen((o) => !o)}>
              {open ? "Hide" : `${user.deployments.length} apps`}
            </Button>
          )}
        </div>
      </div>

      {open && (
        <div className="border-t border-[var(--border)] bg-[var(--surface-2)]/50 px-5 py-4">
          <div className="space-y-2">
            {user.deployments.map((d) => (
              <div
                key={d.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-sm)] bg-[var(--surface)] px-3 py-2.5"
              >
                <span className="flex min-w-0 items-center gap-2.5">
                  <BoxIcon className="h-4 w-4 shrink-0 text-[var(--text-dim)]" />
                  <span className="truncate text-sm">{d.target_label}</span>
                  <StatusBadge status={d.status} />
                </span>
                {isRunning(d.status) && d.url && (
                  <a
                    href={d.url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 text-xs text-[var(--ok)] hover:underline"
                  >
                    {d.url.replace(/^https?:\/\//, "")}
                    <ExternalIcon className="h-3 w-3" />
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
